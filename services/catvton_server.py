"""Local CatVTON try-on service used by FitShot's "catvton" generator.

Runs in its own environment (catvton/.venv) so its packages cannot break ComfyUI.
CatVTON is licensed CC BY-NC-SA 4.0: non-commercial use only.
Start it with run-catvton.cmd. It listens on 127.0.0.1:8190 only.
"""
from __future__ import annotations

import io
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "catvton"
WEIGHTS = CODE / "weights"
os.environ.setdefault("HF_HOME", str(ROOT.parent / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(CODE))

import torch  # noqa: E402
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from PIL import Image, UnidentifiedImageError  # noqa: E402

from model.pipeline import CatVTONPipeline  # noqa: E402

WIDTH, HEIGHT = 768, 1024
app = FastAPI(title="FitShot CatVTON")
_lock = threading.Lock()
_pipeline: CatVTONPipeline | None = None


def pipeline() -> CatVTONPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = CatVTONPipeline(
            base_ckpt=str(WEIGHTS / "base"),
            attn_ckpt=str(WEIGHTS / "catvton"),
            attn_ckpt_version="mix",
            weight_dtype=torch.bfloat16,
            device="cuda",
            skip_safety_check=True,
        )
    return _pipeline


def _image(upload: UploadFile, mode: str) -> Image.Image:
    try:
        with Image.open(io.BytesIO(upload.file.read())) as image:
            return image.convert(mode)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, f"{upload.filename} is not a valid image.") from exc


@app.get("/health")
def health():
    return {"cuda": torch.cuda.is_available(), "loaded": _pipeline is not None, "size": [WIDTH, HEIGHT]}


@app.post("/free")
def free():
    """Drop the model so ComfyUI has the GPU and RAM; the next try-on loads it again."""
    global _pipeline
    with _lock:
        _pipeline = None
        import gc

        gc.collect()
        torch.cuda.empty_cache()
    return {"loaded": False}


@app.post("/tryon")
def tryon(
    person: UploadFile = File(),
    garment: UploadFile = File(),
    mask: UploadFile = File(),
    steps: int = Form(30, ge=10, le=60),
    guidance: float = Form(2.5, ge=1.0, le=7.0),
    seed: int = Form(0),
):
    person_image = _image(person, "RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
    mask_image = _image(mask, "L").resize((WIDTH, HEIGHT), Image.NEAREST)
    garment_image = _image(garment, "RGB")
    with _lock:
        generator = torch.Generator(device="cuda").manual_seed(seed)
        result = pipeline()(
            image=person_image,
            condition_image=garment_image,
            mask=mask_image,
            num_inference_steps=steps,
            guidance_scale=guidance,
            height=HEIGHT,
            width=WIDTH,
            generator=generator,
        )[0]
        torch.cuda.empty_cache()
    buffer = io.BytesIO()
    result.save(buffer, "PNG")
    return Response(buffer.getvalue(), media_type="image/png")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8190, log_level="warning")
