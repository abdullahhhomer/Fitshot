import cv2
import numpy as np
import pytest
from skimage import data

from fitshot.qa.body import check_body, check_identity, check_skin
from fitshot.qa.garment import (
    flat_garment_mask,
    lightness_spread,
    logo_inliers,
    palette,
    palette_distance,
    pattern_similarity,
)
from fitshot.qa.gate import QAInput, _judge_gates, combine
from fitshot.qa.judge import Verdict
from fitshot.qa.perception import detect_faces
from fitshot.qa.types import PATTERN_CONTRAST, PATTERN_MIN_CONTRAST, GateResult, grade_higher


def shirt(color=(190, 30, 40), stripes=None, size=512, bg=(245, 245, 245)):
    image = np.full((size, size, 3), bg, np.uint8)
    points = np.array([[150, 90], [362, 90], [450, 190], [385, 235], [355, 200],
                       [355, 450], [157, 450], [157, 200], [127, 235], [62, 190]])
    mask = np.zeros((size, size), np.uint8)
    cv2.fillPoly(mask, [points], 1)
    fabric = np.full((size, size, 3), color, np.uint8)
    if stripes is not None:
        fabric[(np.arange(size) // 14) % 2 == 0] = stripes
    image[mask > 0] = fabric[mask > 0]
    return image, mask


def add_logo(image, text="FITSHOT"):
    out = image.copy()
    cv2.rectangle(out, (190, 180), (325, 270), (255, 255, 255), -1)
    cv2.putText(out, text[:3], (200, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (10, 10, 10), 3)
    cv2.putText(out, text[3:], (200, 258), cv2.FONT_HERSHEY_DUPLEX, 0.9, (10, 10, 120), 2)
    cv2.circle(out, (305, 200), 12, (10, 120, 10), 3)
    return out


@pytest.fixture(scope="module")
def portrait():
    return data.astronaut()


@pytest.fixture(scope="module")
def portrait_face(portrait):
    return detect_faces(portrait)[0]


def test_flat_mask_finds_garment():
    image, truth = shirt()
    mask = flat_garment_mask(image)
    iou = (mask & truth).sum() / (mask | truth).sum()
    assert iou > 0.95


def test_color_distance_separates_right_and_wrong_color():
    red, mask = shirt((190, 30, 40))
    near, _ = shirt((184, 34, 44))
    blue, _ = shirt((30, 50, 190))
    assert palette_distance(palette(red, mask), palette(near, mask)) < 5
    assert palette_distance(palette(red, mask), palette(blue, mask)) > 25


def test_color_distance_catches_an_added_stripe_color():
    plain, mask = shirt((190, 30, 40))
    striped, _ = shirt((190, 30, 40), stripes=(20, 160, 60))
    assert palette_distance(palette(plain, mask), palette(striped, mask)) > 15


def test_pattern_similarity_prefers_the_same_pattern():
    striped, mask = shirt((30, 40, 120), stripes=(235, 235, 235))
    noisy = np.clip(striped.astype(int) + np.random.default_rng(1).integers(-6, 7, striped.shape), 0, 255).astype(np.uint8)
    solid, _ = shirt((30, 40, 120))
    assert pattern_similarity(striped, mask, noisy, mask) > pattern_similarity(striped, mask, solid, mask) + 0.15


def test_faded_stripes_lose_their_contrast():
    striped, mask = shirt((30, 40, 120), stripes=(240, 240, 240))
    faded, _ = shirt((185, 188, 200), stripes=(235, 235, 235))
    solid, _ = shirt((30, 40, 120))
    reference = lightness_spread(striped, mask)
    assert reference >= PATTERN_MIN_CONTRAST
    assert lightness_spread(solid, mask) < PATTERN_MIN_CONTRAST
    assert grade_higher(lightness_spread(faded, mask) / reference, PATTERN_CONTRAST) == "fail"
    assert grade_higher(lightness_spread(striped, mask) / reference, PATTERN_CONTRAST) == "pass"


def test_logo_matching_survives_scale_and_rejects_a_different_logo():
    base, mask = shirt((30, 40, 120))
    real = add_logo(base)
    box = {"x": 190 / 512, "y": 180 / 512, "w": 135 / 512, "h": 90 / 512}
    moved = cv2.warpAffine(real, np.float32([[0.92, 0, 25], [0, 0.92, 20]]), (512, 512), borderValue=(245, 245, 245))
    moved_mask = cv2.warpAffine(mask, np.float32([[0.92, 0, 25], [0, 0.92, 20]]), (512, 512), flags=cv2.INTER_NEAREST)
    fake = add_logo(base, "ZQXWVK")
    assert logo_inliers(real, box, moved, moved_mask) >= 12
    assert logo_inliers(real, box, fake, mask) < logo_inliers(real, box, moved, moved_mask) / 2


def test_identity_accepts_same_face_and_rejects_missing_face(portrait, portrait_face):
    same = detect_faces(cv2.convertScaleAbs(portrait, alpha=0.92, beta=6))
    assert check_identity(same, portrait_face.embedding).status == "pass"
    assert check_identity([], portrait_face.embedding).status == "fail"


def test_identity_rejects_a_different_embedding(portrait, portrait_face):
    other = detect_faces(portrait)[0]
    rng = np.random.default_rng(3)
    random_vector = rng.normal(size=512)
    other.embedding = random_vector / np.linalg.norm(random_vector)
    assert check_identity([other], portrait_face.embedding).status == "fail"


def test_skin_tolerates_scene_color_cast(portrait, portrait_face):
    warm = np.clip(portrait.astype(np.float32) * [1.12, 1.0, 0.86], 0, 255).astype(np.uint8)
    warm_face = detect_faces(warm)[0]
    assert check_skin(portrait, portrait_face, warm, warm_face, "beach").status == "pass"


def test_skin_flags_a_real_tone_change_on_the_face(portrait, portrait_face):
    changed = portrait.copy()
    x0, y0, x1, y1 = portrait_face.bbox.astype(int)
    changed[y0:y1, x0:x1] = np.clip(changed[y0:y1, x0:x1].astype(np.float32) * [0.48, 0.42, 0.40], 0, 255).astype(np.uint8)
    result = check_skin(portrait, portrait_face, changed, portrait_face, "studio")
    assert result.status in {"review", "fail"}


def test_body_passes_for_identical_pose(portrait):
    assert check_body(portrait, portrait).status == "pass"


def test_combine_uses_the_worst_status():
    gate = lambda s: GateResult("x", s, None, "")
    assert combine([gate("pass"), gate("pass")]) == "pass"
    assert combine([gate("pass"), gate("review")]) == "review"
    assert combine([gate("review"), gate("fail")]) == "fail"


def _qa_input():
    image = np.zeros((64, 64, 3), np.uint8)
    return QAInput(image, image, image, image, np.zeros(512), "top", "studio")


def test_missing_judge_can_never_pass():
    gates, called = _judge_gates(_qa_input(), None)
    assert not called
    assert all(g.status == "review" for g in gates)


def test_crashing_judge_can_never_pass():
    class Broken:
        def review(self, *_):
            raise RuntimeError("quota")

    gates, called = _judge_gates(_qa_input(), Broken())
    assert called
    assert all(g.status == "review" for g in gates)


def test_judge_flags_bad_hands():
    class SixFingers:
        def review(self, *_):
            return Verdict(garment_ok=True, hands_visible=True, hands_ok=False, hand_issues=["six fingers on left hand"])

    gates, _ = _judge_gates(_qa_input(), SixFingers())
    hands = next(g for g in gates if g.name == "hands")
    assert hands.status == "fail"
    assert "six fingers" in hands.hint


def test_taught_checks_are_added_to_the_inspector_prompt():
    from fitshot.qa.judge import PROMPT, prompt_with

    assert prompt_with([]) == PROMPT
    assert "- Is the collar there?" in prompt_with(["Is the collar there?"])


def test_a_key_without_image_quota_stops_nano_banana_for_good(monkeypatch):
    from google.genai import errors

    from fitshot.generators import nano_banana
    from fitshot.generators.base import GenerationError

    class NoQuota:
        class models:
            @staticmethod
            def generate_content(**_):
                raise errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded, limit: 0, model: x", "status": "RESOURCE_EXHAUSTED"}})

    monkeypatch.setattr(nano_banana.settings, "gemini_api_key", "test")
    monkeypatch.setattr(nano_banana, "_no_quota", False)
    generator = nano_banana.NanoBananaGenerator()
    generator._client = NoQuota()
    with pytest.raises(GenerationError) as caught:
        generator._generate("prompt", [])
    assert not caught.value.retryable
    assert "billing" in str(caught.value)
    ready, reason = generator.status()
    assert not ready and "no image quota" in reason
