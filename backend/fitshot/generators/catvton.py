"""Free local try-on: CatVTON dresses the approved shot, ComfyUI creates shots."""
from __future__ import annotations

import io
import random

import cv2

import httpx
import numpy as np
from PIL import Image

from ..config import settings
from ..imaging import resize_to
from .base import DressRequest, GenerationError, GenerationResult, ShotRequest
from .gpu import GPU, release_gpu
from .comfyui import ComfyUIGenerator, _png, blend_region, clean_garment, garment_region

WIDTH, HEIGHT = 768, 1024
MODEL = "CatVTON mix-48k-1024"


class CatVTONGenerator:
    name = "catvton"

    def __init__(self) -> None:
        self.url = settings.catvton_url.rstrip("/")
        self.comfy = ComfyUIGenerator()

    def status(self) -> tuple[bool, str]:
        try:
            httpx.get(f"{self.url}/health", timeout=2).raise_for_status()
        except httpx.HTTPError:
            return False, f"The CatVTON service is not running at {settings.catvton_url}."
        return True, MODEL

    def create_shot(self, request: ShotRequest) -> GenerationResult:
        # CatVTON only changes clothing, so ComfyUI creates the model shots.
        return self.comfy.create_shot(request)

    def dress(self, request: DressRequest) -> GenerationResult:
        # CatVTON works at 3:4. Pad other shapes (a phone photo, say) instead of stretching them.
        # Shorter new sleeves: ComfyUI first bares the arms the old sleeves covered.
        base_shot = self.comfy.bare_arms(request.base_shot, request.sleeves)
        canvas, (x0, y0, x1, y1) = pad_to_aspect(base_shot, WIDTH / HEIGHT)
        person = resize_to(canvas, WIDTH, HEIGHT)
        region = garment_region(
            person, request.category, generous=True, keep_body=request.keep_body, sleeves=request.sleeves
        )
        if region.mean() < 0.01:
            raise GenerationError("Could not find a clothing area to edit in the base shot.")

        with GPU:
            response = self._try_on(person, request, region)

        with Image.open(io.BytesIO(response.content)) as image:
            generated = resize_to(np.asarray(image.convert("RGB")), WIDTH, HEIGHT)

        canvas_h, canvas_w = canvas.shape[:2]
        generated = resize_to(generated, canvas_w, canvas_h)[y0:y1, x0:x1]
        region = cv2.resize(region, (canvas_w, canvas_h), interpolation=cv2.INTER_NEAREST)[y0:y1, x0:x1]
        output = blend_region(base_shot, generated, region)
        return GenerationResult(output, settings.comfyui_usd_per_image, self.name, MODEL)

    def _try_on(self, person: np.ndarray, request: DressRequest, region: np.ndarray) -> httpx.Response:
        release_gpu("catvton")
        try:
            response = httpx.post(
                f"{self.url}/tryon",
                files={
                    "person": ("person.png", _png(person), "image/png"),
                    "garment": ("garment.png", _png(clean_garment(request.garment, (WIDTH, HEIGHT))), "image/png"),
                    "mask": ("mask.png", _png(region * 255), "image/png"),
                },
                data={
                    "steps": str(int(request.options.get("steps", 30))),
                    "guidance": str(float(request.options.get("guidance", 2.5))),
                    "seed": str(random.randrange(2**31)),
                },
                timeout=600,
            )
        except httpx.HTTPError as exc:
            raise GenerationError(f"Could not reach CatVTON: {type(exc).__name__}.", retryable=True) from exc
        if response.status_code != 200:
            raise GenerationError(f"CatVTON failed ({response.status_code}): {response.text[:300]}")
        return response


def pad_to_aspect(image: np.ndarray, aspect: float) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Pad with edge pixels to width/height == aspect. Returns the canvas and the original's box in it."""
    height, width = image.shape[:2]
    if abs(width / height - aspect) < 0.01:
        return image, (0, 0, width, height)
    if width / height < aspect:
        extra = round(height * aspect) - width
        left = extra // 2
        canvas = cv2.copyMakeBorder(image, 0, 0, left, extra - left, cv2.BORDER_REPLICATE)
        return canvas, (left, 0, left + width, height)
    extra = round(width / aspect) - height
    top = extra // 2
    canvas = cv2.copyMakeBorder(image, top, extra - top, 0, 0, cv2.BORDER_REPLICATE)
    return canvas, (0, top, width, top + height)
