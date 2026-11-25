"""Local FASHN VTON 1.5 service for FitShot (http://127.0.0.1:8191).

Runs in the CatVTON environment (catvton/.venv), which already has a CUDA build of PyTorch.
Set up once with scripts/setup_fashn.sh. Measured on an RTX 5060 Laptop GPU (8 GB):
about 3 GB of GPU memory for the model, 5.6 GB for the whole card at peak, 55 s per image
at 30 steps, 576x864 output.

One try-on runs at a time. FitShot asks this service to unload (POST /free) before ComfyUI
or CatVTON use the GPU, and asks them to unload before calling /tryon.
"""
from __future__ import annotations

import gc
import io
import logging
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FASHN = ROOT / "fashn"
# Keep every model file on this drive and never reach the network at run time.
os.environ.setdefault("HF_HOME", str(FASHN / "hf-cache"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import torch  # noqa: E402
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: E402

WEIGHTS = Path(os.environ.get("FASHN_WEIGHTS", FASHN / "weights"))
CATEGORIES = ("tops", "bottoms", "one-pieces")
PHOTO_TYPES = ("model", "flat-lay")

log = logging.getLogger("fashn")
app = FastAPI(title="FitShot FASHN VTON 1.5")
_lock = threading.Lock()
_pipeline = None


def pipeline():
    global _pipeline
    if _pipeline is None:
        from fashn_vton import TryOnPipeline

        if not (WEIGHTS / "model.safetensors").exists():
            raise HTTPException(503, f"FASHN weights are missing in {WEIGHTS}. Run scripts/setup_fashn.sh.")
        started = time.perf_counter()
        _pipeline = TryOnPipeline(weights_dir=str(WEIGHTS))
        log.warning("FASHN loaded in %.1fs", time.perf_counter() - started)
    return _pipeline


def _unload() -> None:
    global _pipeline
    _pipeline = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _image(upload: UploadFile) -> Image.Image:
    try:
        with Image.open(io.BytesIO(upload.file.read())) as image:
            # Phone photos often store their rotation separately; apply it.
            return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, f"{upload.filename} is not a valid image.") from exc


@app.get("/health")
def health():
    return {
        "cuda": torch.cuda.is_available(),
        "loaded": _pipeline is not None,
        "weights": (WEIGHTS / "model.safetensors").exists(),
    }


@app.post("/free")
def free():
    """Drop the model so ComfyUI or CatVTON have the GPU; the next try-on loads it again (about 9 s)."""
    with _lock:
        _unload()
    return {"loaded": False}


@app.post("/tryon")
def tryon(
    person: UploadFile = File(),
    garment: UploadFile = File(),
    category: str = Form("tops"),
    garment_photo_type: str = Form("model"),
    steps: int = Form(30, ge=10, le=50),
    guidance: float = Form(1.5, ge=1.0, le=3.0),
    seed: int = Form(42),
):
    if category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {', '.join(CATEGORIES)}.")
    if garment_photo_type not in PHOTO_TYPES:
        raise HTTPException(400, f"garment_photo_type must be one of {', '.join(PHOTO_TYPES)}.")
    person_image, garment_image = _image(person), _image(garment)
    with _lock:
        started = time.perf_counter()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        try:
            result = pipeline()(
                person_image, garment_image, category=category, garment_photo_type=garment_photo_type,
                num_timesteps=steps, guidance_scale=guidance, seed=seed,
            ).images[0]
        except torch.cuda.OutOfMemoryError as exc:
            # Never leave the GPU full: drop everything so the next call starts clean.
            _unload()
            raise HTTPException(503, "The GPU ran out of memory. Close other GPU programs and try again.") from exc
        except (MemoryError, OSError) as exc:
            # Windows error 1455: RAM plus the paging file are full while loading the weights.
            _unload()
            raise HTTPException(
                503,
                "Not enough memory to load FASHN right now. Close programs you are not using "
                "(for example the CatVTON window) and try again.",
            ) from exc
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        seconds = time.perf_counter() - started
        peak = torch.cuda.max_memory_allocated() // 2**20 if torch.cuda.is_available() else 0
    buffer = io.BytesIO()
    result.save(buffer, "PNG")
    return Response(
        buffer.getvalue(), media_type="image/png",
        headers={"X-Seconds": f"{seconds:.1f}", "X-Peak-MiB": str(peak)},
    )


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("FASHN_PORT", "8191")), log_level="warning")
