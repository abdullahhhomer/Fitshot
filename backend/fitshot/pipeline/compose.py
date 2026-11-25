"""Restores the approved face after a garment edit."""
from __future__ import annotations

import cv2
import numpy as np

from ..imaging import resize_to
from ..qa.perception import Face, detect_faces

MAX_ALIGNMENT_ERROR = 0.12


def restore_face(output: np.ndarray, base: np.ndarray) -> tuple[np.ndarray, bool]:
    """Warp the base shot's face onto the output with a feathered mask.

    Returns the output unchanged when the faces cannot be aligned reliably,
    because a poor paste looks worse than a small identity drift.
    """
    base = resize_to(base, output.shape[1], output.shape[0])
    base_faces, out_faces = detect_faces(base), detect_faces(output)
    if len(base_faces) != 1 or len(out_faces) != 1:
        return output, False
    base_face, out_face = base_faces[0], out_faces[0]

    matrix, _ = cv2.estimateAffinePartial2D(
        base_face.keypoints.astype(np.float32),
        out_face.keypoints.astype(np.float32),
        method=cv2.LMEDS,
    )
    if matrix is None or _alignment_error(matrix, base_face, out_face) > MAX_ALIGNMENT_ERROR:
        return output, False

    height, width = output.shape[:2]
    warped = cv2.warpAffine(base, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    mask = _face_mask(out_face, width, height)
    warped = _match_tone(warped, output, mask)
    alpha = mask[..., None].astype(np.float32)
    blended = warped.astype(np.float32) * alpha + output.astype(np.float32) * (1 - alpha)
    return np.clip(blended, 0, 255).astype(np.uint8), True


def _alignment_error(matrix: np.ndarray, base_face: Face, out_face: Face) -> float:
    points = base_face.keypoints.reshape(-1, 1, 2).astype(np.float32)
    moved = cv2.transform(points, matrix).reshape(-1, 2)
    face_size = max(out_face.bbox[2] - out_face.bbox[0], 1.0)
    return float(np.linalg.norm(moved - out_face.keypoints, axis=1).max() / face_size)


def _face_mask(face: Face, width: int, height: int) -> np.ndarray:
    x0, y0, x1, y1 = face.bbox
    center = (int((x0 + x1) / 2), int((y0 + y1) / 2))
    axes = (max(int((x1 - x0) * 0.46), 1), max(int((y1 - y0) * 0.54), 1))
    mask = np.zeros((height, width), np.uint8)
    cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
    blur = max(int((x1 - x0) * 0.12) | 1, 3)
    return cv2.GaussianBlur(mask, (blur, blur), 0).astype(np.float32) / 255.0


def _match_tone(source: np.ndarray, target: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Shift the restored face toward the local light so the seam is not visible."""
    region = mask > 0.5
    if not region.any():
        return source
    src = cv2.cvtColor(source, cv2.COLOR_RGB2LAB).astype(np.float32)
    dst = cv2.cvtColor(target, cv2.COLOR_RGB2LAB).astype(np.float32)
    shift = np.clip(dst[region].mean(axis=0) - src[region].mean(axis=0), -18, 18)
    return cv2.cvtColor(np.clip(src + shift, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
