"""Turn a person's note about a photo into a lesson FitShot applies to that garment from then on.

A lesson has three parts:
- sleeves: a correction of the garment's sleeve length, used when the try-on area is planned.
- fix: an instruction added to the generator prompt (ComfyUI and Nano Banana read it; CatVTON
  has no prompt, so for it the lesson works through sleeves and the inspector).
- watch: a check the vision inspector makes on every later photo of the garment, so a photo
  with the same problem fails and is retried instead of reaching you.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from . import db
from .config import settings

log = logging.getLogger(__name__)
# Only the newest lessons are applied, so prompts and inspections stay focused.
MAX_LESSONS = 6

PROMPT = """A person reviewed an AI try-on photo of a garment and wrote what is wrong with it.
Garment: {name} ({category}).
Their note: "{text}"

Turn the note into a lesson for future photos of this garment:
- sleeves: only if the note says what the sleeve length should be (none, short, elbow or long); otherwise null.
- fix: one short instruction for the image generator, describing how the garment or photo should look. Empty if the note gives nothing to fix.
- watch: one short yes/no check an inspector can make on a photo to catch this problem. Empty if nothing can be checked.
- about: what the note is about.
Write fix and watch in plain English, even if the note is in another language. Return JSON only."""


class Lesson(BaseModel):
    sleeves: Literal["none", "short", "elbow", "long"] | None = None
    fix: str = ""
    watch: str = ""
    about: Literal["garment", "body", "face", "hands", "background", "other"] = "other"
    learned_by: Literal["gemini", "as written"] = "gemini"


def learn(text: str, name: str, category: str) -> Lesson:
    """Ask the vision model's text side to structure the note. Without a key, keep it as written."""
    if not settings.gemini_api_key:
        return Lesson(fix=text, watch=text, learned_by="as written")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_judge_model,
            contents=[PROMPT.format(name=name, category=category, text=text)],
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json", response_schema=Lesson
            ),
        )
        lesson = response.parsed if isinstance(response.parsed, Lesson) else Lesson.model_validate_json(response.text or "")
        lesson.learned_by = "gemini"
        return lesson
    except Exception as exc:  # A note is never lost because the model was busy.
        log.warning("Could not structure feedback: %s", exc)
        return Lesson(fix=text, watch=text, learned_by="as written")


class GarmentLessons(BaseModel):
    fixes: list[str] = Field(default_factory=list)
    watch: list[str] = Field(default_factory=list)


def garment_lessons(product_id: str) -> GarmentLessons:
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            "SELECT lesson FROM feedback WHERE product_id=? ORDER BY created_at DESC LIMIT ?",
            (product_id, MAX_LESSONS),
        )
    lessons = [Lesson.model_validate(json.loads(r["lesson"])) for r in rows]
    return GarmentLessons(
        fixes=[lesson.fix for lesson in lessons if lesson.fix],
        watch=[lesson.watch for lesson in lessons if lesson.watch],
    )
