"""Local ComfyUI generator: SDXL with InstantID, IP-Adapter and OpenPose."""
from __future__ import annotations

import hashlib
import io
import random
import threading
import time
import uuid
from collections import OrderedDict

import cv2
import httpx
import numpy as np
from PIL import Image

from ..config import settings
from ..imaging import limit_side, resize_to
from .base import (
    POSES,
    DressRequest,
    GenerationError,
    GenerationResult,
    ShotRequest,
    shot_prompt,
)
from .gpu import GPU, release_gpu
from .comfy_graph import (
    CHECKPOINT,
    POSE_KEYPOINTS,
    REQUIRED_MODELS,
    draw_skeleton,
    face_refine_graph,
    shot_graph,
    skeleton_from_mediapipe,
    skin_graph,
    working_size,
)

JOB_TIMEOUT = 600
FACE_PROMPT = (
    "close-up photo of the same adult's face, natural skin texture, sharp focus, "
    "soft studio light, neutral expression"
)
_status_cache: tuple[float, bool, str] | None = None


def _png(image: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, "PNG")
    return buffer.getvalue()


class ComfyClient:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def _call(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return httpx.request(method, f"{self.url}{path}", timeout=kwargs.pop("timeout", 60), **kwargs)
        except httpx.HTTPError as exc:
            raise GenerationError(f"Could not reach ComfyUI: {type(exc).__name__}.", retryable=True) from exc

    def upload(self, image: np.ndarray) -> str:
        data = _png(image)
        name = f"fitshot_{hashlib.sha1(data).hexdigest()[:20]}.png"
        response = self._call(
            "POST", "/upload/image",
            files={"image": (name, data, "image/png")},
            data={"overwrite": "true", "type": "input"},
        )
        if response.status_code != 200:
            raise GenerationError(f"ComfyUI rejected an upload ({response.status_code}).")
        return response.json()["name"]

    def run(self, graph: dict) -> np.ndarray:
        with GPU:
            return self._run(graph)

    def _run(self, graph: dict) -> np.ndarray:
        release_gpu("comfyui")
        response = self._call("POST", "/prompt", json={"prompt": graph, "client_id": self.client_id})
        if response.status_code != 200:
            raise GenerationError(f"ComfyUI rejected the workflow: {response.text[:400]}")
        prompt_id = response.json()["prompt_id"]

        deadline = time.monotonic() + JOB_TIMEOUT
        while time.monotonic() < deadline:
            history = self._call("GET", f"/history/{prompt_id}").json().get(prompt_id)
            if history:
                return self._result(history)
            time.sleep(1)
        self._call("POST", "/interrupt")
        raise GenerationError("ComfyUI timed out.", retryable=True)

    def _result(self, history: dict) -> np.ndarray:
        status = history.get("status", {})
        if status.get("status_str") == "error":
            detail = "unknown error"
            for kind, message in status.get("messages", []):
                if kind == "execution_error":
                    detail = f"{message.get('node_type')}: {message.get('exception_message', '').strip()[:300]}"
            raise GenerationError(f"ComfyUI failed in {detail}")
        for output in history.get("outputs", {}).values():
            for item in output.get("images", []):
                response = self._call("GET", "/view", params={k: item[k] for k in ("filename", "subfolder", "type")})
                if response.status_code == 200:
                    with Image.open(io.BytesIO(response.content)) as image:
                        return np.asarray(image.convert("RGB")).copy()
        raise GenerationError("ComfyUI finished without an image.")


_BARE: OrderedDict[tuple, np.ndarray] = OrderedDict()
_BARE_LOCK = threading.Lock()
_BARE_MAKING: dict[tuple, threading.Lock] = {}


def garment_region(
    base: np.ndarray, category: str, generous: bool = False, keep_body: bool = False, sleeves: str | None = None
) -> np.ndarray:
    """Mask the area a garment may occupy, keeping the face and hands untouched.

    With generous=True the mask covers the whole torso down past the hips, so a garment
    with a different length or cut than the base clothing has room and leaves nothing behind.
    With keep_body=True (a real person's photo) the mask follows the clothing they wear and
    their own torso, without the convex hull, so the try-on cannot redraw them wider.
    sleeves (none, short, elbow, long) keeps bare arms out of the mask where the new sleeves end.
    """
    from ..qa.garment import worn_garment_mask
    from ..qa.perception import detect_faces, detect_hand_boxes, detect_poses

    height, width = base.shape[:2]
    clothing = worn_garment_mask(base, category).astype(np.uint8)
    mask = clothing.copy()
    people = detect_poses(base)
    if people:
        person = people[0]
        limb = max(round(width * 0.06), 8)
        joints: list[tuple[int, int]] = []
        if category == "outerwear":
            joints = [(11, 13), (12, 14)] if sleeves != "none" else []
            if sleeves in (None, "long"):
                joints += [(13, 15), (14, 16)]
        elif category == "dress":
            joints = [(23, 25), (24, 26), (11, 23), (12, 24)]
        for a, b in joints:
            if person[a, 2] >= 0.5 and person[b, 2] >= 0.5:
                cv2.line(mask, tuple(person[a, :2].astype(int)), tuple(person[b, :2].astype(int)), 1, limb)
        if generous and category in ("top", "outerwear", "dress"):
            spread = 0.0 if keep_body else 1.0
            arms = sleeves != "none"
            mask = np.maximum(mask, _torso_region(person, category, width, height, limb, spread, arms))

    if generous and not keep_body and mask.any():
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest = max(contours, key=cv2.contourArea)
        cv2.fillPoly(mask, [cv2.convexHull(largest)], 1)

    grow = max(round(width * 0.012) | 1, 3)
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
    for x0, y0, x1, y1 in detect_hand_boxes(base, margin=0.1):
        # Protect the hand itself, but still replace the old clothing inside its box,
        # otherwise patches of the base garment survive next to the hands.
        mask[y0:y1, x0:x1] &= clothing[y0:y1, x0:x1]
    if people:
        # Bare forearms and hands are never part of the garment, even when the hand
        # detector misses a hand. Only old clothing inside this guard stays editable.
        guard = _arm_guard(people[0], width, height, sleeves)
        mask[guard > 0] &= clothing[guard > 0]
    if keep_body and category == "top":
        # A top never redraws the trousers, so hands resting on them stay intact.
        from ..qa.perception import segment_clothes

        lower = segment_clothes(base)["lower"]
        lower = cv2.erode(lower, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
        mask[lower > 0] = 0
    for face in detect_faces(base):
        x0, y0, x1, y1 = face.bbox
        center = (int((x0 + x1) / 2), int((y0 + y1) / 2))
        axes = (int((x1 - x0) * 0.75), int((y1 - y0) * 0.8))
        keep = np.zeros_like(mask)
        cv2.ellipse(keep, center, axes, 0, 0, 360, 1, -1)
        # Protect the face down to the chin only. Below it, a hood, scarf or collar from the
        # old clothing must still be replaced, or it stays wrapped around the new garment.
        keep[min(height, int(y1 + (y1 - y0) * 0.08)) :] = 0
        mask[keep > 0] = 0
    return mask


def blend_region(base_shot: np.ndarray, generated: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Paste the generated clothing into the approved shot at the shot's full resolution.

    Every pixel outside the feathered region (face, hands, background) stays exactly as
    the person approved it, instead of being softened by a downscale and upscale.
    """
    full_h, full_w = base_shot.shape[:2]
    feather = max(round(region.shape[1] * 0.012) | 1, 3)
    alpha = cv2.GaussianBlur(region.astype(np.float32), (feather, feather), 0)
    alpha = cv2.resize(alpha, (full_w, full_h), interpolation=cv2.INTER_LINEAR)[..., None]
    layer = resize_to(generated, full_w, full_h).astype(np.float32)
    merged = layer * alpha + base_shot.astype(np.float32) * (1 - alpha)
    return np.clip(merged, 0, 255).round().astype(np.uint8)


def _torso_region(
    person: np.ndarray, category: str, width: int, height: int, limb: int, spread: float = 1.0, arms: bool = True
) -> np.ndarray:
    """Torso polygon from the shoulders to below the hips, plus the upper arms for sleeves.

    spread scales how far the polygon reaches past the shoulder and hip joints; 0 stays inside the body.
    """
    region = np.zeros((height, width), np.uint8)
    if min(person[[11, 12, 23, 24], 2]) < 0.5:
        return region
    left_shoulder, right_shoulder = person[11, :2], person[12, :2]
    left_hip, right_hip = person[23, :2], person[24, :2]
    torso = float(np.linalg.norm((left_hip + right_hip) / 2 - (left_shoulder + right_shoulder) / 2))
    drop = np.array([0.0, torso * (0.35 if category == "outerwear" else 0.15)])
    if category == "dress":
        drop = np.array([0.0, torso * 1.1])

    def widen(a: np.ndarray, b: np.ndarray, amount: float) -> tuple[np.ndarray, np.ndarray]:
        direction = (a - b) / max(float(np.linalg.norm(a - b)), 1.0)
        return a + direction * amount, b - direction * amount

    top_a, top_b = widen(left_shoulder, right_shoulder, torso * 0.12 * spread)
    low_a, low_b = widen(left_hip, right_hip, torso * 0.18 * spread)
    polygon = np.array([top_a, top_b, low_b + drop, low_a + drop]).round().astype(np.int32)
    cv2.fillPoly(region, [polygon], 1)
    for a, b in ((11, 13), (12, 14)) if arms else ():
        if person[a, 2] >= 0.5 and person[b, 2] >= 0.5:
            cv2.line(region, tuple(person[a, :2].astype(int)), tuple(person[b, :2].astype(int)), 1, limb)
    return region


# Where the new sleeve ends, as a fraction of the way from shoulder to elbow (above 1: past the elbow).
SLEEVE_END = {"none": 0.0, "short": 0.6, "elbow": 1.2}


def _point(a: np.ndarray, b: np.ndarray, fraction: float) -> tuple[int, int]:
    return tuple((a + (b - a) * fraction).round().astype(int))


def _sleeve_start(person: np.ndarray, side: tuple[int, int, int], sleeves: str) -> tuple[int, int]:
    shoulder, elbow, wrist = (person[i, :2] for i in side)
    end = SLEEVE_END[sleeves]
    return _point(shoulder, elbow, end) if end <= 1 else _point(elbow, wrist, end - 1)


ARM_SIDES = ((11, 13, 15), (12, 14, 16))
HAND_POINTS = ((15, 17, 19, 21), (16, 18, 20, 22))


def _arm_guard(person: np.ndarray, width: int, height: int, sleeves: str | None) -> np.ndarray:
    """Hands, plus the arm below where the new sleeves end."""
    guard = np.zeros((height, width), np.uint8)
    limb = max(round(width * 0.08), 10)
    for side, hand in zip(ARM_SIDES, HAND_POINTS):
        wrist = person[side[2]]
        if wrist[2] < 0.5:
            continue
        points = [person[i, :2] for i in hand if person[i, 2] >= 0.5]
        reach = max([float(np.linalg.norm(p - wrist[:2])) for p in points] + [width * 0.03])
        cv2.circle(guard, tuple(wrist[:2].round().astype(int)), int(reach * 1.6), 1, -1)
        for p in points:
            cv2.circle(guard, tuple(p.round().astype(int)), int(reach * 0.9), 1, -1)
        if sleeves in SLEEVE_END and min(person[list(side), 2]) >= 0.5:
            cv2.line(guard, _sleeve_start(person, side, sleeves), tuple(wrist[:2].round().astype(int)), 1, limb)
    return guard


def old_sleeves(base: np.ndarray, sleeves: str | None) -> np.ndarray:
    """Old clothing on the arms that the new garment's shorter sleeves will not cover."""
    from ..qa.perception import detect_poses, segment_clothes

    height, width = base.shape[:2]
    region = np.zeros((height, width), np.uint8)
    people = detect_poses(base)
    if sleeves not in SLEEVE_END or not people:
        return region
    person = people[0]
    limb = max(round(width * 0.09), 10)
    for side in ARM_SIDES:
        if min(person[list(side), 2]) < 0.5:
            continue
        elbow, wrist = person[side[1], :2], person[side[2], :2]
        # Run a little past the wrist to catch the cuff.
        cv2.line(region, _sleeve_start(person, side, sleeves), _point(elbow, wrist, 1.15), 1, limb)
    worn = segment_clothes(base)
    region &= np.maximum(worn["upper"], worn["full"])
    grow = max(round(width * 0.012) | 1, 3)
    return cv2.dilate(region, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))


def skin_tone(image: np.ndarray, person: np.ndarray) -> np.ndarray:
    """Median colour of the bare hands, or the middle of the face if the hands are hidden."""
    from ..qa.perception import detect_faces, segment_clothes

    height, width = image.shape[:2]
    sample = np.zeros((height, width), np.uint8)
    for hand in HAND_POINTS:
        wrist = person[hand[0]]
        points = [person[i, :2] for i in hand[1:] if person[i, 2] >= 0.5]
        if wrist[2] < 0.5 or not points:
            continue
        center = np.mean(points + [wrist[:2]], axis=0)
        reach = max(float(np.linalg.norm(p - wrist[:2])) for p in points)
        cv2.circle(sample, tuple(center.round().astype(int)), max(int(reach * 0.45), 2), 1, -1)
    worn = segment_clothes(image)
    sample[np.maximum.reduce(list(worn.values())) > 0] = 0
    if sample.sum() < 30:
        faces = detect_faces(image)
        if faces:
            x0, y0, x1, y1 = (int(v) for v in faces[0].bbox)
            sample[:] = 0
            sample[y0 + (y1 - y0) // 3 : y0 + 2 * (y1 - y0) // 3, x0 + (x1 - x0) // 4 : x1 - (x1 - x0) // 4] = 1
    if sample.sum() < 30:
        return np.array([200, 160, 135], np.uint8)
    return np.median(image[sample > 0], axis=0).astype(np.uint8)


def prefill_arms(image: np.ndarray, region: np.ndarray, person: np.ndarray) -> np.ndarray:
    """Fill the old sleeves with the surrounding background, then paint arm shapes in skin tone."""
    filled = cv2.inpaint(image, region, 9, cv2.INPAINT_TELEA)
    shoulders = float(np.linalg.norm(person[11, :2] - person[12, :2]))
    thickness = max(int(shoulders * 0.17), 6)
    arms = np.zeros_like(region)
    for side in ARM_SIDES:
        if min(person[list(side), 2]) < 0.5:
            continue
        wrist = tuple(person[side[2], :2].round().astype(int))
        cv2.line(arms, _sleeve_start(person, side, "none"), wrist, 1, thickness)
    arms &= region
    filled[arms > 0] = skin_tone(image, person)
    soft = cv2.GaussianBlur(filled, (0, 0), max(thickness / 6, 1))
    filled[region > 0] = soft[region > 0]
    return filled


SKIN_TEXT = (
    "photo of a person's bare arms, natural skin with the same skin tone as their hands and face, "
    "realistic anatomy, sharp focus, same lighting as the rest of the photo"
)


def clean_garment(garment: np.ndarray, size: tuple[int, int] = (512, 512)) -> np.ndarray:
    """Center the product on white so IP-Adapter sees the garment, not the backdrop."""
    from ..qa.garment import flat_garment_mask

    mask = flat_garment_mask(garment)
    ys, xs = np.where(mask > 0)
    crop = garment[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1].copy()
    crop[mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1] == 0] = 255
    out_w, out_h = size
    scale = min(out_w * 0.92 / crop.shape[1], out_h * 0.92 / crop.shape[0])
    fitted = cv2.resize(
        crop,
        (max(round(crop.shape[1] * scale), 1), max(round(crop.shape[0] * scale), 1)),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
    )
    canvas = np.full((out_h, out_w, 3), 255, np.uint8)
    top, left = (out_h - fitted.shape[0]) // 2, (out_w - fitted.shape[1]) // 2
    canvas[top : top + fitted.shape[0], left : left + fitted.shape[1]] = fitted
    return canvas


def face_layout(reference: np.ndarray, pose: str, width: int, height: int) -> np.ndarray:
    """Place the reference face at the pose's head, so InstantID targets that spot."""
    from ..qa.perception import detect_faces

    faces = detect_faces(reference)
    if not faces:
        raise GenerationError("The reference photo has no detectable face.")
    x0, y0, x1, y1 = faces[0].bbox
    pad = (x1 - x0) * 0.45
    ref_h, ref_w = reference.shape[:2]
    crop = reference[max(int(y0 - pad), 0) : min(int(y1 + pad), ref_h), max(int(x0 - pad), 0) : min(int(x1 + pad), ref_w)]

    target_w = max(round(width * 0.17), 96)
    target_h = round(target_w * crop.shape[0] / crop.shape[1])
    head = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    nose_x, nose_y = POSE_KEYPOINTS[pose][0]
    left = int(np.clip(nose_x * width - target_w / 2, 0, width - target_w))
    top = int(np.clip(nose_y * height - target_h / 2, 0, height - target_h))
    canvas = np.full((height, width, 3), 128, np.uint8)
    canvas[top : top + target_h, left : left + target_w] = head
    return canvas


class ComfyUIGenerator:
    name = "comfyui"

    def __init__(self) -> None:
        self.client = ComfyClient(settings.comfyui_url)

    def status(self) -> tuple[bool, str]:
        global _status_cache
        now = time.monotonic()
        if _status_cache and now - _status_cache[0] < 8:
            return _status_cache[1], _status_cache[2]
        ready, detail = self._check()
        _status_cache = (now, ready, detail)
        return ready, detail

    def _check(self) -> tuple[bool, str]:
        base = settings.comfyui_url.rstrip("/")
        try:
            missing = []
            for (node, field), names in REQUIRED_MODELS.items():
                response = httpx.get(f"{base}/object_info/{node}", timeout=2)
                response.raise_for_status()
                if node not in response.json():
                    return False, f"ComfyUI is missing the {node} node."
                options = response.json()[node]["input"]["required"][field][0]
                missing += [name for name in names if name not in options]
        except httpx.HTTPError:
            return False, f"ComfyUI is not running at {settings.comfyui_url}."
        if missing:
            return False, f"ComfyUI is missing models: {', '.join(missing)}."
        return True, CHECKPOINT

    def _result(self, image: np.ndarray) -> GenerationResult:
        return GenerationResult(image, settings.comfyui_usd_per_image, self.name, CHECKPOINT)

    def create_shot(self, request: ShotRequest) -> GenerationResult:
        width, height = 896, 1152
        pose = draw_skeleton(list(POSE_KEYPOINTS[request.pose]), width, height)
        layout = face_layout(request.reference, request.pose, width, height)
        graph = shot_graph(
            self.client.upload(limit_side(request.reference, 1024)),
            self.client.upload(layout),
            self.client.upload(pose),
            f"{shot_prompt(request)} Pose: {POSES[request.pose]}.",
            width, height, random.randrange(2**48),
        )
        shot = self.client.run(graph)
        return self._result(self._refine_face(shot, request.reference))

    def _refine_face(self, image: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """A full-body face is only ~100 px wide, too small for InstantID to hold identity.

        Enlarge the face, re-render it with InstantID, then blend it back in.
        """
        from ..qa.perception import detect_faces

        faces = detect_faces(image)
        if len(faces) != 1:
            return image
        height, width = image.shape[:2]
        x0, y0, x1, y1 = faces[0].bbox
        side = min(int(max(x1 - x0, y1 - y0) * 2.2), width, height)
        left = int(np.clip((x0 + x1) / 2 - side / 2, 0, width - side))
        top = int(np.clip((y0 + y1) / 2 - side / 2, 0, height - side))
        crop = image[top : top + side, left : left + side]

        graph = face_refine_graph(
            self.client.upload(resize_to(crop, 1024, 1024)),
            self.client.upload(limit_side(reference, 1024)),
            FACE_PROMPT,
            random.randrange(2**48),
        )
        refined = resize_to(self.client.run(graph), side, side)

        mask = np.zeros((side, side), np.float32)
        center = (int((x0 + x1) / 2 - left), int((y0 + y1) / 2 - top))
        axes = (max(int((x1 - x0) * 0.62), 1), max(int((y1 - y0) * 0.75), 1))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
        blur = max(int((x1 - x0) * 0.25) | 1, 3)
        alpha = cv2.GaussianBlur(mask, (blur, blur), 0)[..., None]
        blended = refined.astype(np.float32) * alpha + crop.astype(np.float32) * (1 - alpha)
        output = image.copy()
        output[top : top + side, left : left + side] = np.clip(blended, 0, 255).astype(np.uint8)
        return output

    def dress(self, request: DressRequest) -> GenerationResult:
        raise GenerationError(
            "ComfyUI now only makes brand model photos. Try garments on with FASHN VTON 1.5 or CatVTON."
        )

    def bare_arms(self, image: np.ndarray, sleeves: str | None) -> np.ndarray:
        """When the new sleeves are shorter than the clothing in the photo, first turn the arm
        area they will not cover into bare skin. Otherwise the try-on fills it with fabric.

        The result is reused for every garment with the same sleeve length on the same photo,
        which saves a ComfyUI run and a GPU model swap per look.
        """
        key = (hashlib.sha1(image.tobytes()).hexdigest(), image.shape, sleeves)
        with _BARE_LOCK:
            # Two looks of the same photo starting together: the second waits for the first.
            making = _BARE_MAKING.setdefault(key, threading.Lock())
        with making:
            with _BARE_LOCK:
                if key in _BARE:
                    _BARE.move_to_end(key)
                    return _BARE[key]
            bare = self._bare_arms(image, sleeves)
            with _BARE_LOCK:
                _BARE[key] = bare
                _BARE_MAKING.pop(key, None)
                while len(_BARE) > 8:
                    _BARE.popitem(last=False)
        return bare

    def _bare_arms(self, image: np.ndarray, sleeves: str | None) -> np.ndarray:
        from ..qa.perception import detect_poses

        full_h, full_w = image.shape[:2]
        width, height = working_size(full_w, full_h)
        small = resize_to(image, width, height)
        region = old_sleeves(small, sleeves)
        people = detect_poses(small)
        if region.mean() < 0.002 or not people:
            return image
        graph = skin_graph(
            self.client.upload(prefill_arms(small, region, people[0])),
            self.client.upload(np.dstack([region * 255] * 3)),
            self.client.upload(skeleton_from_mediapipe(people[0], width, height)),
            SKIN_TEXT,
            random.randrange(2**48),
        )
        generated = resize_to(self.client.run(graph), width, height)
        return blend_region(image, generated, region)
