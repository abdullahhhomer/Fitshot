"""Identity, skin tone and body-structure gates."""
from __future__ import annotations

import cv2
import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

from ..imaging import gray_world
from .perception import Face, detect_hand_boxes, detect_poses
from .types import (
    IDENTITY_COSINE,
    LIMB_DRIFT,
    SKIN_DELTA_E,
    GateResult,
    grade_higher,
    grade_lower,
)

LIMBS = [(11, 13), (13, 15), (12, 14), (14, 16), (23, 25), (25, 27), (24, 26), (26, 28)]
MIN_VISIBILITY = 0.6


def check_identity(faces: list[Face], centroid: np.ndarray) -> GateResult:
    hint = "Keep the model's face identical to the reference."
    if not faces:
        return GateResult("identity", "fail", None, "No face was detected.", hint)
    if len(faces) > 1:
        return GateResult(
            "identity", "fail", None, f"{len(faces)} faces detected, expected one.",
            "Show exactly one person.",
        )
    cosine = float(np.dot(faces[0].embedding, centroid))
    return GateResult(
        "identity",
        grade_higher(cosine, IDENTITY_COSINE),
        round(cosine, 3),
        f"Face similarity to the brand model is {cosine:.2f}.",
        hint,
    )


def _skin_lab(rgb: np.ndarray, face: Face) -> np.ndarray | None:
    balanced = gray_world(rgb)
    x0, y0, x1, y1 = face.bbox.astype(int)
    width, height = x1 - x0, y1 - y0
    crop = balanced[
        max(y0 + int(height * 0.25), 0) : max(y1 - int(height * 0.15), 1),
        max(x0 + int(width * 0.2), 0) : max(x1 - int(width * 0.2), 1),
    ]
    if crop.size == 0:
        return None
    ycrcb = cv2.cvtColor(crop, cv2.COLOR_RGB2YCrCb)
    skin = cv2.inRange(ycrcb, (30, 130, 75), (255, 180, 135)) > 0
    pixels = crop[skin] if skin.mean() >= 0.15 else crop.reshape(-1, 3)
    return rgb2lab(np.median(pixels, axis=0).reshape(1, 1, 3) / 255.0).reshape(3)


def check_skin(
    ref: np.ndarray, ref_face: Face | None, out: np.ndarray, out_face: Face | None, scene: str
) -> GateResult:
    hint = "Keep the model's natural skin tone unchanged."
    if ref_face is None or out_face is None:
        return GateResult("skin_tone", "review", None, "A face was missing, so skin was not compared.", hint)
    ref_lab, out_lab = _skin_lab(ref, ref_face), _skin_lab(out, out_face)
    if ref_lab is None or out_lab is None:
        return GateResult("skin_tone", "review", None, "The skin region was too small to compare.", hint)
    delta = float(deltaE_ciede2000(ref_lab, out_lab, kL=2))
    return GateResult(
        "skin_tone",
        grade_lower(delta, SKIN_DELTA_E[scene]),
        round(delta, 2),
        f"Skin tone difference is Delta E {delta:.1f}.",
        hint,
    )


def _limb_lengths(person: np.ndarray) -> dict[tuple[int, int], float]:
    shoulders = person[[11, 12]]
    hips = person[[23, 24]]
    if (hips[:, 2] >= MIN_VISIBILITY).all() and (shoulders[:, 2] >= MIN_VISIBILITY).all():
        unit = np.linalg.norm(shoulders[:, :2].mean(axis=0) - hips[:, :2].mean(axis=0))
    elif (shoulders[:, 2] >= MIN_VISIBILITY).all():
        unit = np.linalg.norm(shoulders[0, :2] - shoulders[1, :2])
    else:
        return {}
    if unit < 1:
        return {}
    return {
        (a, b): float(np.linalg.norm(person[a, :2] - person[b, :2]) / unit)
        for a, b in LIMBS
        if person[a, 2] >= MIN_VISIBILITY and person[b, 2] >= MIN_VISIBILITY
    }


def check_body(base: np.ndarray, out: np.ndarray) -> GateResult:
    hint = "Keep the exact body proportions and pose from the base photo."
    out_people = detect_poses(out)
    if len(out_people) > 1:
        return GateResult("body_pose", "fail", None, "More than one person was detected.", "Show exactly one person.")
    if not out_people:
        return GateResult("body_pose", "review", None, "No body pose was detected.", hint)

    base_people = detect_poses(base)
    if not base_people:
        return GateResult("body_pose", "review", None, "The base shot has no detectable pose.", hint)

    base_limbs, out_limbs = _limb_lengths(base_people[0]), _limb_lengths(out_people[0])
    shared = [k for k in base_limbs if k in out_limbs and base_limbs[k] > 0.05]
    if not shared:
        return GateResult("body_pose", "review", None, "Too few limbs were visible to compare.", hint)
    drift = max(abs(out_limbs[k] - base_limbs[k]) / base_limbs[k] for k in shared)
    return GateResult(
        "body_pose",
        grade_lower(drift, LIMB_DRIFT),
        round(drift, 3),
        f"Largest limb proportion change is {drift:.0%} across {len(shared)} limbs.",
        hint,
    )


def hand_crops(rgb: np.ndarray) -> list[np.ndarray]:
    return [rgb[y0:y1, x0:x1] for x0, y0, x1, y1 in detect_hand_boxes(rgb) if x1 > x0 and y1 > y0]
