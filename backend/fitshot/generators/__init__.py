"""Image generators, all exposed through the same interface."""
from __future__ import annotations

from .base import GenerationError, Generator


def get_generator(name: str) -> Generator:
    if name == "nano_banana":
        from .nano_banana import NanoBananaGenerator

        return NanoBananaGenerator()
    if name == "comfyui":
        from .comfyui import ComfyUIGenerator

        return ComfyUIGenerator()
    if name == "catvton":
        from .catvton import CatVTONGenerator

        return CatVTONGenerator()
    if name in ("fashn", "fashn_hosted"):
        from .fashn import FashnGenerator

        return FashnGenerator("local" if name == "fashn" else "hosted")
    raise GenerationError(f"Unknown generator: {name}")


GENERATOR_NAMES = ("fashn", "fashn_hosted", "catvton", "comfyui", "nano_banana")
# Generators that put a garment on a person. ComfyUI only makes brand model photos now:
# FASHN VTON 1.5 replaced its IP-Adapter dressing, which drifted in color.
DRESSERS = ("fashn", "fashn_hosted", "catvton", "nano_banana")
