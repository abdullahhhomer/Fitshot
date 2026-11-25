"""Lazy, thread-safe wrappers around the CV models. Everything runs on CPU."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import lru_cache

import cv2
import mediapipe as mp
import numpy as np
from insightface.app import FaceAnalysis
from mediapipe.tasks.python import BaseOptions, vision
from rembg import new_session

from ..config import settings
from ..imaging import to_pil

# One lock per model: a model is not used by two threads at once, but different models
# (faces, pose, clothes) can run side by side on different cores.
_locks = {name: threading.RLock() for name in ("face", "pose", "hands", "cloth", "object")}
CPU = ["CPUExecutionProvider"]


@dataclass
class Face:
    bbox: np.ndarray
    keypoints: np.ndarray
    embedding: np.ndarray
    score: float


@lru_cache(maxsize=1)
def _face_app() -> FaceAnalysis:
    app = FaceAnalysis(
        name="buffalo_l",
        root=str(settings.models_dir / "insightface"),
        allowed_modules=["detection", "recognition"],
        providers=CPU,
    )
    app.prepare(ctx_id=-1, det_size=(640, 640))
    return app


@lru_cache(maxsize=1)
def _pose() -> vision.PoseLandmarker:
    data = (settings.models_dir / "mediapipe" / "pose_landmarker_full.task").read_bytes()
    return vision.PoseLandmarker.create_from_options(
        vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=data),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=2,
        )
    )


@lru_cache(maxsize=1)
def _hands() -> vision.HandLandmarker:
    data = (settings.models_dir / "mediapipe" / "hand_landmarker.task").read_bytes()
    return vision.HandLandmarker.create_from_options(
        vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=data),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=4,
        )
    )


@lru_cache(maxsize=1)
def _cloth():
    return new_session("u2net_cloth_seg", providers=CPU)


@lru_cache(maxsize=1)
def _object():
    return new_session("isnet-general-use", providers=CPU)


def segment_object(rgb: np.ndarray) -> np.ndarray:
    """Return a binary mask of the main object, even when it matches the backdrop."""
    with _locks["object"]:
        mask = _object().predict(to_pil(rgb))[0]
    height, width = rgb.shape[:2]
    resized = cv2.resize(np.asarray(mask.convert("L")), (width, height), interpolation=cv2.INTER_LINEAR)
    return (resized > 127).astype(np.uint8)


def _mp_image(rgb: np.ndarray) -> mp.Image:
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))


# A face smaller than this share of the main face's area belongs to someone in the background.
BACKGROUND_FACE_AREA = 0.3


def _area(face: Face) -> float:
    return float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))


def detect_faces(rgb: np.ndarray, include_background: bool = False) -> list[Face]:
    """Return faces, largest first. Small faces of people in the background are left out,
    so a passer-by never counts as a second person or gets compared as "you"."""
    with _locks["face"]:
        found = _face_app().get(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    faces = [
        Face(f.bbox.copy(), f.kps.copy(), f.normed_embedding.copy(), float(f.det_score))
        for f in found
    ]
    faces.sort(key=_area, reverse=True)
    if include_background or not faces:
        return faces
    main = _area(faces[0])
    return [face for face in faces if _area(face) >= BACKGROUND_FACE_AREA * main]


def _pose_extent(person: np.ndarray) -> float:
    seen = person[person[:, 2] >= 0.3]
    if len(seen) < 2:
        return 0.0
    return float(np.ptp(seen[:, 0]) * np.ptp(seen[:, 1]))


def detect_poses(rgb: np.ndarray) -> list[np.ndarray]:
    """Return one (33, 3) array per person (x and y in pixels, plus visibility), biggest
    person first: the one in front of the camera, not someone in the background."""
    height, width = rgb.shape[:2]
    with _locks["pose"]:
        result = _pose().detect(_mp_image(rgb))
    people = [
        np.array([[p.x * width, p.y * height, p.visibility or 0.0] for p in person])
        for person in result.pose_landmarks
    ]
    return sorted(people, key=_pose_extent, reverse=True)


def framing(rgb: np.ndarray) -> str | None:
    """'full' when the main person is visible head to feet, 'half' when only the upper body
    (shoulders) is, None when no person is found."""
    people = detect_poses(rgb)
    if not people:
        return None
    person = people[0]
    head = person[0, 2] >= 0.5
    feet = min(person[27, 2], person[28, 2]) >= 0.5
    if head and feet:
        return "full"
    if min(person[11, 2], person[12, 2]) >= 0.5:
        return "half"
    return None


def garment_photo_type(rgb: np.ndarray) -> str:
    """'model' when someone wears the garment in its photo, else 'flat-lay'. Shop photos of a
    worn garment often crop off the head, so this looks for a body, not a face."""
    for person in detect_poses(rgb):
        if min(person[[11, 12, 23, 24], 2]) >= 0.5:
            return "model"
    return "flat-lay"


def main_person_area(rgb: np.ndarray) -> np.ndarray | None:
    """A mask around the person in front, or None when nobody else is in the photo.

    Generous on every side so loose sleeves, hems and dresses stay inside it.
    """
    people = detect_poses(rgb)
    if len(people) < 2:
        return None
    person = people[0]
    seen = person[person[:, 2] >= 0.3]
    if len(seen) < 2:
        return None
    height, width = rgb.shape[:2]
    x0, y0 = seen[:, :2].min(axis=0)
    x1, y1 = seen[:, :2].max(axis=0)
    pad_x, pad_y = (x1 - x0) * 0.35, (y1 - y0) * 0.2
    area = np.zeros((height, width), np.uint8)
    area[
        max(0, int(y0 - pad_y)) : min(height, int(y1 + pad_y)),
        max(0, int(x0 - pad_x)) : min(width, int(x1 + pad_x)),
    ] = 1
    return area


def detect_hand_boxes(rgb: np.ndarray, margin: float = 0.35) -> list[tuple[int, int, int, int]]:
    height, width = rgb.shape[:2]
    with _locks["hands"]:
        result = _hands().detect(_mp_image(rgb))
    boxes = []
    for hand in result.hand_landmarks:
        xs = [p.x * width for p in hand]
        ys = [p.y * height for p in hand]
        pad = max(max(xs) - min(xs), max(ys) - min(ys)) * margin
        boxes.append(
            (
                max(int(min(xs) - pad), 0),
                max(int(min(ys) - pad), 0),
                min(int(max(xs) + pad), width),
                min(int(max(ys) + pad), height),
            )
        )
    return boxes


def segment_clothes(rgb: np.ndarray) -> dict[str, np.ndarray]:
    """Return binary masks for upper, lower and full-body clothing."""
    with _locks["cloth"]:
        masks = _cloth().predict(to_pil(rgb))
    height, width = rgb.shape[:2]
    resized = [
        cv2.resize(np.asarray(m.convert("L")), (width, height), interpolation=cv2.INTER_LINEAR)
        for m in masks
    ]
    masks = {name: (mask > 127).astype(np.uint8) for name, mask in zip(("upper", "lower", "full"), resized)}
    # With someone else in the photo, only the main person's clothes count.
    main = main_person_area(rgb)
    if main is not None:
        masks = {name: mask & main for name, mask in masks.items()}
    return masks
