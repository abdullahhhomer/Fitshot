"""Nano Banana generation through the Gemini API."""
from __future__ import annotations

import io
import time

import numpy as np
from google import genai
from google.genai import errors, types
from PIL import Image

from ..config import settings
from ..imaging import limit_side, to_pil
from .base import (
    DressRequest,
    GenerationError,
    GenerationResult,
    ShotRequest,
    dress_prompt,
    shot_prompt,
)

TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}
NO_QUOTA = (
    "Your Gemini key has no image quota: Google's free tier allows 0 image requests for "
    f"{settings.gemini_image_model}. Turn on billing for the key in Google AI Studio, then restart FitShot. "
    "CatVTON and ComfyUI are free alternatives."
)
# Set when Google answers that this key's image quota is zero. Kept until FitShot restarts.
_no_quota = False


def _is_zero_quota(exc: errors.APIError) -> bool:
    return exc.code == 429 and "limit: 0" in (exc.message or "")


class NanoBananaGenerator:
    name = "nano_banana"

    def __init__(self) -> None:
        self.model = settings.gemini_image_model
        self._client: genai.Client | None = None

    def status(self) -> tuple[bool, str]:
        if not settings.gemini_api_key:
            return False, "Add GEMINI_API_KEY to the .env file."
        if _no_quota:
            return False, NO_QUOTA
        return True, self.model

    @property
    def client(self) -> genai.Client:
        if not settings.gemini_api_key:
            raise GenerationError("GEMINI_API_KEY is not configured.")
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    def _generate(self, prompt: str, images: list[np.ndarray]) -> GenerationResult:
        contents = [prompt, *[to_pil(limit_side(image, 1536)) for image in images]]
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=settings.aspect_ratio, image_size=settings.image_size
            ),
        )
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                return GenerationResult(
                    _first_image(response), settings.image_price, self.name, self.model
                )
            except errors.APIError as exc:
                if _is_zero_quota(exc):
                    # Waiting or retrying cannot help: this key may never generate images.
                    global _no_quota
                    _no_quota = True
                    raise GenerationError(NO_QUOTA, retryable=False) from exc
                retryable = exc.code in TRANSIENT_CODES
                if not retryable or attempt == 2:
                    raise GenerationError(f"Gemini error {exc.code}: {exc.message}", retryable) from exc
                time.sleep(2 ** (attempt + 1) * 2)
        raise GenerationError("Gemini request failed.", retryable=True)

    def create_shot(self, request: ShotRequest) -> GenerationResult:
        return self._generate(shot_prompt(request), [request.reference])

    def dress(self, request: DressRequest) -> GenerationResult:
        images = [request.base_shot, request.garment]
        if request.back is not None:
            images.append(request.back)
        return self._generate(dress_prompt(request), images)


def _first_image(response: types.GenerateContentResponse) -> np.ndarray:
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.inline_data and part.inline_data.data:
                with Image.open(io.BytesIO(part.inline_data.data)) as image:
                    return np.asarray(image.convert("RGB")).copy()
    reason = "unknown"
    if response.candidates and response.candidates[0].finish_reason:
        reason = str(response.candidates[0].finish_reason)
    raise GenerationError(f"Gemini returned no image (finish reason: {reason}).")
