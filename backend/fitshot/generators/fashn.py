"""FASHN VTON 1.5, on this PC (services/fashn_server.py) or through a Hugging Face Space.

On this PC it has no daily limit and photos stay here; it takes about 3 GB of GPU memory and
55 s per image on an RTX 5060 Laptop GPU. The Hugging Face route needs no GPU but has a daily
quota.

The model (Apache-2.0, https://huggingface.co/fashn-ai/fashn-vton-1.5) does its own pose
detection and human parsing and needs no mask, so FitShot only tells it the category and
whether the garment photo is a flat lay or worn by a model.

On the Hugging Face route, every try-on sends the person and garment photos to the Space.
"""
from __future__ import annotations

import logging
import random
import tempfile
import threading
from pathlib import Path

import cv2
import httpx
import numpy as np

from ..config import settings
from ..imaging import load_rgb, resize_to, save_rgb
from .base import DressRequest, GenerationError, GenerationResult, QuotaWait, ShotRequest
from .comfyui import ComfyUIGenerator, _png, blend_region
from .gpu import GPU, release_gpu

log = logging.getLogger(__name__)

MODEL = "FASHN VTON 1.5"
QUOTA_RECHECK_SECONDS = 3600
CATEGORY = {"top": "tops", "outerwear": "tops", "bottom": "bottoms", "dress": "one-pieces"}
CLOTHING_PARTS = {"tops": ("upper", "full"), "bottoms": ("lower", "full"), "one-pieces": ("upper", "lower", "full")}
# Below this mean difference (0-255) outside the clothing, the try-on kept the person in place,
# so the untouched parts (face, hands, background) can come from the sharper original photo.
ALIGNED = 12.0

_clients: dict[str, object] = {}
_clients_lock = threading.Lock()


def spaces() -> list[str]:
    return [s.strip() for s in settings.fashn_spaces.split(",") if s.strip()]


def photo_type(garment: np.ndarray) -> str:
    """'model' when someone is wearing the garment in its photo, else 'flat-lay'."""
    from ..qa.perception import garment_photo_type

    return garment_photo_type(garment)


def _client(space: str):
    from gradio_client import Client

    with _clients_lock:
        if space not in _clients:
            _clients[space] = Client(space, token=settings.hf_token or None, verbose=False)
        return _clients[space]


def _call(space: str, person: Path, garment: Path, category: str, kind: str, seed: int, steps: int, guidance: float) -> np.ndarray:
    from gradio_client import handle_file

    job = _client(space).submit(
        handle_file(str(person)), handle_file(str(garment)), category, kind,
        steps, guidance, seed, True,
        api_name="/try_on",
    )
    result = job.result(timeout=settings.fashn_timeout)
    path = result if isinstance(result, str) else result.get("path")
    return load_rgb(path)


def keep_original_outside_clothing(base: np.ndarray, generated: np.ndarray, category: str) -> np.ndarray:
    """Use the try-on only where clothing was or now is; keep the original photo elsewhere.

    FASHN works at 576x864, so this keeps the face, hands and background at the photo's own
    resolution. If the try-on shifted the person, the full try-on is used instead, since
    mixing the two would leave ghost edges.
    """
    from ..qa.perception import segment_clothes

    height, width = base.shape[:2]
    generated = resize_to(generated, width, height)
    parts = CLOTHING_PARTS[category]
    before, after = segment_clothes(base), segment_clothes(generated)
    region = np.maximum.reduce([before[p] for p in parts] + [after[p] for p in parts]).astype(np.uint8)
    grow = max(round(width * 0.02) | 1, 3)
    region = cv2.dilate(region, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
    outside = region == 0
    if not outside.any():
        return generated
    drift = float(np.abs(base.astype(np.int16) - generated.astype(np.int16))[outside].mean())
    if drift > ALIGNED:
        log.info("FASHN moved the person (difference %.1f); using its full image.", drift)
        return generated
    return blend_region(base, generated, region)


def local_ready() -> bool:
    try:
        health = httpx.get(f"{settings.fashn_url.rstrip('/')}/health", timeout=2).json()
    except (httpx.HTTPError, ValueError):
        return False
    return bool(health.get("weights"))


def _local(request: DressRequest, category: str, kind: str, seed: int, steps: int, guidance: float) -> np.ndarray:
    """Run FASHN on this PC, after asking ComfyUI and CatVTON to give up the GPU."""
    import io

    from PIL import Image

    with GPU:
        release_gpu("fashn")
        try:
            response = httpx.post(
                f"{settings.fashn_url.rstrip('/')}/tryon",
                files={
                    "person": ("person.png", _png(request.base_shot), "image/png"),
                    "garment": ("garment.png", _png(request.garment), "image/png"),
                },
                data={
                    "category": category, "garment_photo_type": kind, "steps": str(steps),
                    "guidance": str(guidance), "seed": str(seed),
                },
                timeout=settings.fashn_timeout,
            )
        except httpx.HTTPError as exc:
            raise GenerationError(f"Could not reach the local FASHN service: {type(exc).__name__}.", retryable=True) from exc
    if response.status_code != 200:
        detail = response.json().get("detail") if "json" in response.headers.get("content-type", "") else response.text
        raise GenerationError(f"Local FASHN failed ({response.status_code}): {str(detail)[:300]}", retryable=response.status_code == 503)
    log.info("Local FASHN: %ss, peak %s MiB", response.headers.get("X-Seconds"), response.headers.get("X-Peak-MiB"))
    with Image.open(io.BytesIO(response.content)) as image:
        return np.asarray(image.convert("RGB")).copy()


class FashnGenerator:
    """FASHN VTON 1.5. mode "local" runs on this PC's service; "hosted" on Hugging Face Spaces.
    They are separate models in the registry, so one never stands in for the other."""

    name = "fashn"

    def __init__(self, mode: str = "local") -> None:
        self.mode = mode
        self.name = "fashn" if mode == "local" else "fashn_hosted"
        self.comfy = ComfyUIGenerator()

    def status(self) -> tuple[bool, str]:
        if self.mode == "local":
            if local_ready():
                return True, f"{MODEL} on this PC"
            return False, f"The FASHN service is not running at {settings.fashn_url}. Start run-fashn.cmd."
        if not settings.hf_token:
            return False, "Add HF_TOKEN (a Hugging Face read token) to the .env file."
        if not spaces():
            return False, "Set FASHN_SPACES in the .env file."
        return True, f"{MODEL} on Hugging Face ({spaces()[0]})"

    def create_shot(self, request: ShotRequest) -> GenerationResult:
        # FASHN only dresses people; ComfyUI makes brand model photos.
        return self.comfy.create_shot(request)

    def dress(self, request: DressRequest) -> GenerationResult:
        from gradio_client.exceptions import AppError
        from gradio_client.utils import QueueError

        options = request.options or {}
        category = CATEGORY[request.category]
        detected = photo_type(request.garment)
        kind = options.get("photo_type") or detected
        if kind == "model" and detected == "flat-lay":
            # Model-worn mode cuts the garment out of a person. With nobody in the photo it
            # pastes the whole picture onto the body, so a flat-lay is always run as one.
            log.info("Garment photo shows no person; running it as flat-lay instead of model-worn.")
            kind = "flat-lay"
        seed = random.randrange(2**31)
        steps = int(options.get("steps", settings.fashn_steps))
        guidance = float(options.get("guidance", settings.fashn_guidance))
        if self.mode == "local":
            if not local_ready():
                raise GenerationError(
                    f"The FASHN service is not running at {settings.fashn_url}. Start run-fashn.cmd.", retryable=True
                )
            generated = _local(request, category, kind, seed, steps, guidance)
            image = keep_original_outside_clothing(request.base_shot, generated, category)
            return GenerationResult(image, 0.0, self.name, f"{MODEL} ({kind}) on this PC")
        busy: list[str] = []
        with tempfile.TemporaryDirectory(prefix="fitshot-fashn-") as folder:
            person, garment = Path(folder) / "person.png", Path(folder) / "garment.png"
            save_rgb(request.base_shot, person)
            save_rgb(request.garment, garment)
            for space in spaces():
                try:
                    generated = _call(space, person, garment, category, kind, seed, steps, guidance)
                except QueueError:
                    busy.append(space)
                    continue
                except AppError as exc:
                    message = str(exc)
                    if "quota" in message.lower() or "runs limit" in message.lower():
                        # The free quota resets 24 hours after the day's first use. Checking again
                        # costs nothing, so wait and retry every hour rather than fail.
                        raise QuotaWait(
                            "Waiting for your free Hugging Face quota (about 9 FASHN try-ons a day). "
                            "FitShot tries again every hour, so this look will be made when it resets.",
                            QUOTA_RECHECK_SECONDS,
                        ) from exc
                    log.warning("FASHN Space %s failed: %s", space, message[:300])
                    busy.append(space)
                    continue
                except Exception as exc:  # Network trouble or a sleeping Space: try the next one.
                    log.warning("FASHN Space %s unreachable: %s", space, exc)
                    with _clients_lock:
                        _clients.pop(space, None)
                    busy.append(space)
                    continue
                image = keep_original_outside_clothing(request.base_shot, generated, category)
                return GenerationResult(image, 0.0, self.name, f"{MODEL} ({kind}) via {space}")
        raise GenerationError(
            f"Every FASHN Space was busy or unreachable ({', '.join(busy)}). Try again in a few minutes.",
            retryable=True,
        )
