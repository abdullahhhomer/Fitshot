"""One GPU, three local models.

ComfyUI, CatVTON and FASHN do not fit in an 8 GB GPU together, so only one of them works at a
time (the GPU lock), and before it starts it asks the other two to unload (release_gpu).
Everything else (QA on the CPU, the Gemini judge, hosted generators) runs alongside.
"""
from __future__ import annotations

import threading

import httpx

from ..config import settings

GPU = threading.RLock()


def release_gpu(keep: str) -> None:
    """Ask every local GPU service except `keep` to unload its models. A service that is not running is skipped."""
    services = {
        "comfyui": (f"{settings.comfyui_url.rstrip('/')}/free", {"unload_models": True, "free_memory": True}),
        "catvton": (f"{settings.catvton_url.rstrip('/')}/free", None),
        "fashn": (f"{settings.fashn_url.rstrip('/')}/free", None),
    }
    for name, (url, body) in services.items():
        if name == keep:
            continue
        try:
            httpx.post(url, json=body, timeout=15)
        except httpx.HTTPError:
            pass
