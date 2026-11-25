"""Runs every QA gate and combines them into one publish decision."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from .body import check_body, check_identity, check_skin, hand_crops
from .garment import check_garment
from .judge import Judge
from .perception import detect_faces, detect_hand_boxes
from .types import GateResult, QAReport, Status

log = logging.getLogger(__name__)


@dataclass
class QAInput:
    garment: np.ndarray
    output: np.ndarray
    base_shot: np.ndarray
    reference: np.ndarray
    centroid: np.ndarray
    category: str
    scene: str
    logo_box: dict | None = None
    # Checks people taught FitShot for this garment (see learning.py).
    notes: list[str] = field(default_factory=list)


def combine(gates: list[GateResult]) -> Status:
    statuses = {gate.status for gate in gates}
    if "fail" in statuses:
        return "fail"
    return "review" if "review" in statuses else "pass"


HAND_CHANGED_SHARE = 0.15  # share of hand-box pixels allowed to differ (sleeve cuffs, hems)


def hands_unchanged(base: np.ndarray, output: np.ndarray) -> bool:
    """True when every hand in the output is copied unchanged from the approved shot.

    The dressing step protects the hands, so the person already judged them when they
    approved the shot. Asking the vision model again only adds noise.
    """
    if base.shape != output.shape:
        return False
    boxes = detect_hand_boxes(output, margin=0.05)
    if not boxes:
        return False
    for x0, y0, x1, y1 in boxes:
        if x1 <= x0 or y1 <= y0:
            return False
        diff = np.abs(base[y0:y1, x0:x1].astype(np.int16) - output[y0:y1, x0:x1].astype(np.int16)).max(axis=2)
        if float((diff > 6).mean()) > HAND_CHANGED_SHARE:
            return False
    return True


def _judge_gates(qa: QAInput, judge: Judge | None) -> tuple[list[GateResult], bool]:
    """A skipped or failed judge can never produce a pass."""
    if judge is None:
        reason = "Vision review did not run because no API key is configured."
        return [
            GateResult("garment_structure", "review", None, reason),
            GateResult("hands", "review", None, reason),
        ], False
    inherited = hands_unchanged(qa.base_shot, qa.output)
    try:
        verdict = judge.review(qa.garment, qa.output, [] if inherited else hand_crops(qa.output), qa.notes)
    except Exception as exc:
        log.warning("Vision judge failed: %s", exc)
        reason = f"Vision review failed: {type(exc).__name__}."
        return [
            GateResult("garment_structure", "review", None, reason),
            GateResult("hands", "review", None, reason),
        ], True

    garment_reason = "; ".join(verdict.garment_issues) or "Structure matches the product."
    gates = [
        GateResult(
            "garment_structure",
            "pass" if verdict.garment_ok else "fail",
            None,
            garment_reason,
            f"Fix these garment details: {garment_reason}",
        )
    ]
    if inherited:
        gates.append(GateResult("hands", "pass", None, "Hands are unchanged from the approved shot you checked."))
    elif not verdict.hands_visible:
        gates.append(GateResult("hands", "pass", None, "No hands are visible."))
    else:
        hand_reason = "; ".join(verdict.hand_issues) or "Hands look natural."
        gates.append(
            GateResult(
                "hands",
                "pass" if verdict.hands_ok else "fail",
                None,
                hand_reason,
                f"Keep the hands anatomically correct. Fix: {hand_reason}",
            )
        )
    return gates, True


def run_qa(qa: QAInput, judge: Judge | None) -> QAReport:
    out_faces = detect_faces(qa.output)
    # Skin is compared with the approved shot: the person already accepted that shot's
    # skin tone against the reference, so this check asks whether dressing changed it.
    base_faces = detect_faces(qa.base_shot)

    gates = check_garment(qa.garment, qa.output, qa.category, qa.scene, qa.logo_box)
    if not base_faces:
        # The person's body photo has no face (their face came in a separate close-up),
        # so the only identity question is whether a face was invented.
        gates.append(
            GateResult("identity", "pass", None, "Your body photo has no face, and none was added.")
            if not out_faces
            else GateResult("identity", "review", None, "A face appeared that is not in your body photo.", "Keep the photo without a face.")
        )
    else:
        gates.append(check_identity(out_faces, qa.centroid))
    if not base_faces and not out_faces:
        gates.append(GateResult("skin_tone", "pass", None, "No face in the photo to compare skin tone against."))
    else:
        gates.append(
            check_skin(
                qa.base_shot,
                base_faces[0] if base_faces else None,
                qa.output,
                out_faces[0] if out_faces else None,
                qa.scene,
            )
        )
    gates.append(check_body(qa.base_shot, qa.output))

    # Skip the paid call when a local check has already failed.
    if combine(gates) == "fail":
        return QAReport("fail", gates, judge_called=False)

    judge_gates, called = _judge_gates(qa, judge)
    gates.extend(judge_gates)
    return QAReport(combine(gates), gates, judge_called=called)
