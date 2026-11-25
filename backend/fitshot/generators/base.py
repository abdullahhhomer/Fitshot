"""Generator interface and the shared catalog prompts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

SCENES = {
    "studio": "a seamless pure white photo studio backdrop with soft, even, shadowless lighting",
    "street": "a clean, modern city street in soft daylight with a gently blurred background",
    "beach": "a calm sandy beach in soft natural daylight with a gently blurred ocean background",
}

# Back views are excluded because a front photo cannot show the garment's back.
POSES = {
    "front": "standing facing the camera, arms relaxed at the sides",
    "three_quarter_left": "standing in a three-quarter turn to the left, arms relaxed",
    "three_quarter_right": "standing in a three-quarter turn to the right, arms relaxed",
    "walking": "walking naturally toward the camera, mid-stride",
    "hand_on_hip": "standing facing the camera with one hand resting on the hip",
    "relaxed": "standing with weight on one leg in a relaxed editorial pose",
}

CATEGORIES = {
    "top": "top",
    "outerwear": "jacket or outerwear",
    "bottom": "trousers, shorts or skirt",
    "dress": "dress",
}


class GenerationError(RuntimeError):
    """A generation failed. `retryable` marks temporary provider errors."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class QuotaWait(GenerationError):
    """A free quota is used up for now. The item waits and is tried again later, instead of failing."""

    def __init__(self, message: str, wait_seconds: int):
        super().__init__(message, retryable=False)
        self.wait_seconds = wait_seconds


@dataclass
class ShotRequest:
    reference: np.ndarray
    scene: str
    pose: str


@dataclass
class DressRequest:
    base_shot: np.ndarray
    garment: np.ndarray
    category: str
    scene: str
    reference: np.ndarray
    back: np.ndarray | None = None
    hints: list[str] = field(default_factory=list)
    # A real person's own photo: keep their body outline instead of making room for a new cut.
    keep_body: bool = False
    # How far the new garment's sleeves reach: none, short, elbow, long, or None if unknown.
    sleeves: str | None = None
    # Model-specific settings chosen in the Fitting Room (steps, guidance, photo type).
    options: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    image: np.ndarray
    usd: float
    provider: str
    model: str


class Generator(Protocol):
    name: str

    def status(self) -> tuple[bool, str]: ...

    def create_shot(self, request: ShotRequest) -> GenerationResult: ...

    def dress(self, request: DressRequest) -> GenerationResult: ...


def shot_prompt(request: ShotRequest) -> str:
    return (
        "The image shows the reference for a synthetic adult fashion model. Create a "
        "photorealistic full-body e-commerce catalog photograph of this exact same adult. "
        "Keep the face, hair, skin tone and body type identical. "
        f"Pose: {POSES[request.pose]}. Setting: {SCENES[request.scene]}. "
        "Outfit: a plain fitted white crew-neck t-shirt, plain grey straight trousers and "
        "simple white sneakers. Show the full body from head to feet with space around it. "
        "Natural anatomy and hands, sharp focus, 85mm lens. One person only. No text, "
        "logos or watermarks."
    )


def dress_prompt(request: DressRequest) -> str:
    fixes = ""
    if request.hints:
        fixes = " The previous attempt failed inspection. Fix: " + " ".join(request.hints)
    back = " Image 3 shows the back of the same product." if request.back is not None else ""
    return (
        "Image 1 is an approved catalog photo of a model. Image 2 is the real product, a "
        f"{CATEGORIES[request.category]}.{back} Edit image 1 so the model wears this exact "
        "product, fitted naturally to the body with realistic folds and shadows. "
        "Reproduce the product's exact color, pattern, pattern scale, fabric, logo, text, "
        "neckline, sleeves, hem, buttons and pockets. Do not redesign or add anything. "
        "Change only the clothing area needed for this product. Keep the face, hair, skin "
        "tone, hands, body proportions, pose, background, lighting and framing unchanged. "
        f"One person only. No added text or watermarks.{fixes}"
    )
