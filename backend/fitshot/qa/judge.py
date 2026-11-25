"""Vision-model review for checks classic CV handles poorly.

MediaPipe always fits 21 landmarks to a hand, so it cannot count an extra finger.
"""
from __future__ import annotations

import time
from typing import Literal, Protocol

import numpy as np
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field

from ..config import settings
from ..imaging import limit_side, to_pil

# Seconds to wait before each retry of a busy call; None means give up.
RETRY_WAITS = (2, 6, None)

PROMPT = """You are a strict e-commerce photo inspector.
Image 1 is the real product. Image 2 is an AI-generated catalog photo of a model wearing it.
Any further images are close-up crops of hands from image 2.

Check:
1. Garment structure: neckline, collar, sleeve length, hem, closures, pockets and visible
   design elements must match the real product. Ignore natural folds, lighting and fit.
2. Hands: every visible hand must have a natural shape and the right number of fingers.
   Fingers hidden by pose or clothing are fine. Report only defects you can actually see.

Return JSON only."""


def prompt_with(notes: list[str]) -> str:
    """Add the checks people taught FitShot for this garment. A failed one is a garment issue."""
    if not notes:
        return PROMPT
    lines = "\n".join(f"- {note}" for note in notes)
    return (
        f"{PROMPT}\n\nPeople found these problems on earlier photos of this garment. Check each one "
        f"in image 2. If any of them is present, set garment_ok to false and name it:\n{lines}"
    )


class Verdict(BaseModel):
    garment_ok: bool
    garment_issues: list[str] = Field(default_factory=list)
    hands_visible: bool
    hands_ok: bool
    hand_issues: list[str] = Field(default_factory=list)


class Judge(Protocol):
    def review(
        self, garment: np.ndarray, output: np.ndarray, hands: list[np.ndarray], notes: list[str] = ()
    ) -> Verdict: ...


class GeminiJudge:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def review(
        self, garment: np.ndarray, output: np.ndarray, hands: list[np.ndarray], notes: list[str] = ()
    ) -> Verdict:
        images = [to_pil(limit_side(garment, 1024)), to_pil(limit_side(output, 1280))]
        images += [to_pil(limit_side(hand, 512)) for hand in hands[:4]]
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=Verdict,
        )
        for wait in RETRY_WAITS:
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=[prompt_with(notes), *images], config=config
                )
                break
            except genai_errors.APIError as exc:
                # The free tier often answers "busy" or "rate limited" for a few seconds.
                if exc.code not in (429, 500, 503) or wait is None:
                    raise
                time.sleep(wait)
        if isinstance(response.parsed, Verdict):
            return response.parsed
        return Verdict.model_validate_json(response.text or "")


SLEEVES_PROMPT = """This is a product photo of one garment. How long are its sleeves?
none: sleeveless or strapless. short: they end above the elbow. elbow: they end at the elbow
or on the forearm. long: they reach the wrist. Return JSON only."""


class GarmentSleeves(BaseModel):
    sleeves: Literal["none", "short", "elbow", "long"]


def read_sleeves(api_key: str, model: str, garment: np.ndarray) -> str:
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        temperature=0, response_mime_type="application/json", response_schema=GarmentSleeves
    )
    for wait in RETRY_WAITS:
        try:
            response = client.models.generate_content(
                model=model, contents=[SLEEVES_PROMPT, to_pil(limit_side(garment, 768))], config=config
            )
            break
        except genai_errors.APIError as exc:
            if exc.code not in (429, 500, 503) or wait is None:
                raise
            time.sleep(wait)
    if isinstance(response.parsed, GarmentSleeves):
        return response.parsed.sleeves
    return GarmentSleeves.model_validate_json(response.text or "").sleeves


def default_judge() -> Judge | None:
    if not settings.gemini_api_key:
        return None
    return GeminiJudge(settings.gemini_api_key, settings.gemini_judge_model)
