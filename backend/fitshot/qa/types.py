"""Shared QA result types and provisional thresholds.

The thresholds are engineering starting points. They have not been calibrated
on labeled FitShot outputs yet.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Status = Literal["pass", "review", "fail"]


@dataclass
class GateResult:
    name: str
    status: Status
    score: float | None
    reason: str
    hint: str = ""


@dataclass
class QAReport:
    status: Status
    gates: list[GateResult] = field(default_factory=list)
    judge_called: bool = False

    @property
    def hints(self) -> list[str]:
        return [g.hint for g in self.gates if g.status == "fail" and g.hint]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "gates": [asdict(g) for g in self.gates],
            "calibrated": False,
        }


@dataclass(frozen=True)
class Limits:
    pass_at: float
    review_at: float


# Lower is better. Outdoor light legitimately shifts measured color.
COLOR_DELTA_E = {
    "studio": Limits(9, 15),
    "street": Limits(13, 21),
    "beach": Limits(15, 23),
}
SKIN_DELTA_E = {
    "studio": Limits(7, 12),
    "street": Limits(9, 15),
    "beach": Limits(11, 17),
}
LIMB_DRIFT = Limits(0.20, 0.35)

# Higher is better.
PATTERN_SIMILARITY = Limits(0.72, 0.58)
# Share of the reference's light-to-dark contrast kept in the output. Applies only to
# two-tone patterns (stripes, checks), where the reference spread exceeds PATTERN_MIN_CONTRAST.
PATTERN_CONTRAST = Limits(0.65, 0.45)
PATTERN_MIN_CONTRAST = 45.0
IDENTITY_COSINE = Limits(0.50, 0.35)
LOGO_INLIERS = Limits(12, 6)


def grade_lower(value: float, limits: Limits) -> Status:
    if value <= limits.pass_at:
        return "pass"
    return "review" if value <= limits.review_at else "fail"


def grade_higher(value: float, limits: Limits) -> Status:
    if value >= limits.pass_at:
        return "pass"
    return "review" if value >= limits.review_at else "fail"
