"""Small image helpers shared across the pipeline. Arrays are RGB uint8."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def load_rgb(path: str | Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(ImageOps.exif_transpose(image).convert("RGB")).copy()


def save_rgb(image: np.ndarray, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(path, quality=95)
    return path


def to_pil(image: np.ndarray) -> Image.Image:
    return Image.fromarray(image)


def resize_to(image: np.ndarray, width: int, height: int) -> np.ndarray:
    if image.shape[1] == width and image.shape[0] == height:
        return image
    shrinking = width < image.shape[1]
    interpolation = cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC
    return cv2.resize(image, (width, height), interpolation=interpolation)


def limit_side(image: np.ndarray, max_side: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = max_side / max(height, width)
    if scale >= 1:
        return image
    return resize_to(image, round(width * scale), round(height * scale))


def gray_world(image: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Neutralize the scene's color cast so skin and garment colors compare fairly."""
    pixels = image[mask > 0] if mask is not None and mask.any() else image.reshape(-1, 3)
    means = np.maximum(pixels.mean(axis=0), 1.0)
    gains = np.clip(means.mean() / means, 0.6, 1.6)
    return np.clip(image.astype(np.float32) * gains, 0, 255).astype(np.uint8)
