"""Garment fidelity: color, pattern and logo."""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab
from skimage.feature import local_binary_pattern

from .perception import segment_clothes, segment_object
from .types import (
    COLOR_DELTA_E,
    LOGO_INLIERS,
    PATTERN_CONTRAST,
    PATTERN_MIN_CONTRAST,
    PATTERN_SIMILARITY,
    GateResult,
    grade_higher,
    grade_lower,
)

CATEGORY_MASKS = {
    "top": ("upper",),
    "outerwear": ("upper",),
    "bottom": ("lower",),
    "dress": ("full", "upper", "lower"),
}
MIN_COVERAGE = 0.02
RANK = {"pass": 0, "review": 1, "fail": 2}


def _largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return mask
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == largest).astype(np.uint8)


def _filled(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(_largest_component(mask), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
    return filled


@lru_cache(maxsize=64)
def _cached_flat_mask(data: bytes, height: int, width: int) -> bytes:
    rgb = np.frombuffer(data, np.uint8).reshape(height, width, 3)
    size = max(7, min(height, width) // 28) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    learned = _filled(cv2.morphologyEx(segment_object(rgb), cv2.MORPH_CLOSE, kernel))
    backup = _background_difference_mask(rgb)
    # High-contrast patterns can split the learned mask into a small fragment.
    fragmented = backup.mean() < 0.9 and backup.mean() > 1.6 * learned.mean()
    mask = backup if fragmented or not 0.05 <= learned.mean() <= 0.98 else learned
    return mask.tobytes()


def flat_garment_mask(rgb: np.ndarray) -> np.ndarray:
    """Find a flat-lay garment, including white fabric on a light background."""
    height, width = rgb.shape[:2]
    data = _cached_flat_mask(rgb.tobytes(), height, width)
    return np.frombuffer(data, np.uint8).reshape(height, width).copy()


def _background_difference_mask(rgb: np.ndarray) -> np.ndarray:
    """Fallback for when the segmentation model finds no clear object."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    edge = max(4, min(rgb.shape[:2]) // 40)
    border = np.concatenate(
        [
            lab[:edge].reshape(-1, 3),
            lab[-edge:].reshape(-1, 3),
            lab[:, :edge].reshape(-1, 3),
            lab[:, -edge:].reshape(-1, 3),
        ]
    )
    distance = np.linalg.norm(lab - np.median(border, axis=0), axis=2)
    scaled = np.clip(distance * 4, 0, 255).astype(np.uint8)
    _, mask = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Scale with the image so the gaps between printed stripes close up.
    size = max(7, min(rgb.shape[:2]) // 28) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = _largest_component((mask > 0).astype(np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
    return filled if filled.mean() >= 0.05 else np.ones_like(mask)


def worn_garment_mask(rgb: np.ndarray, category: str) -> np.ndarray:
    masks = segment_clothes(rgb)
    for name in CATEGORY_MASKS.get(category, ("upper",)):
        if masks[name].mean() >= MIN_COVERAGE:
            return masks[name]
    combined = np.maximum.reduce(list(masks.values()))
    return combined


def palette(rgb: np.ndarray, mask: np.ndarray, k: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Return dominant CIELAB colors and their weights inside the mask."""
    pixels = rgb[mask > 0]
    if len(pixels) > 20000:
        step = len(pixels) // 20000
        pixels = pixels[::step]
    lab = rgb2lab(pixels.reshape(-1, 1, 3) / 255.0).reshape(-1, 3).astype(np.float32)
    k = min(k, len(np.unique(lab.round(), axis=0)))
    cv2.setRNGSeed(7)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(lab, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    weights = np.bincount(labels.ravel(), minlength=k) / len(labels)
    keep = weights >= 0.05
    return centers[keep], weights[keep] / weights[keep].sum()


def palette_distance(
    a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]
) -> float:
    """Symmetric weighted Delta E 2000, with lightness relaxed for shading and folds."""

    def directed(src, src_weights, dst) -> float:
        grid = deltaE_ciede2000(src[:, None, :], dst[None, :, :], kL=2)
        return float((grid.min(axis=1) * src_weights).sum())

    return max(directed(a[0], a[1], b[0]), directed(b[0], b[1], a[0]))


def _texture(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, float]:
    ys, xs = np.where(mask > 0)
    crop = rgb[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop_mask = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    scale = 256 / max(crop.shape[:2])
    size = (max(round(crop.shape[1] * scale), 8), max(round(crop.shape[0] * scale), 8))
    gray = cv2.cvtColor(cv2.resize(crop, size, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    small_mask = cv2.resize(crop_mask, size, interpolation=cv2.INTER_NEAREST)
    inner = cv2.erode(small_mask, np.ones((5, 5), np.uint8)) > 0
    if not inner.any():
        inner = small_mask > 0

    histograms = []
    for radius in (1, 2, 3):
        points = 8 * radius
        codes = local_binary_pattern(gray, points, radius, method="uniform")
        hist, _ = np.histogram(codes[inner], bins=points + 2, range=(0, points + 2))
        histograms.append(hist / max(hist.sum(), 1))

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge_density = float((np.hypot(gx, gy)[inner] > 40).mean())
    return np.concatenate(histograms) / len(histograms), edge_density


def pattern_similarity(ref, ref_mask, out, out_mask) -> float:
    ref_hist, ref_edges = _texture(ref, ref_mask)
    out_hist, out_edges = _texture(out, out_mask)
    bhattacharyya = float(np.sqrt(ref_hist * out_hist).sum())
    edge_ratio = (min(ref_edges, out_edges) + 0.02) / (max(ref_edges, out_edges) + 0.02)
    return 0.6 * bhattacharyya + 0.4 * edge_ratio


def lightness_spread(rgb: np.ndarray, mask: np.ndarray) -> float:
    """Spread between the light and dark parts of the garment (CIELAB L, 10th to 90th percentile)."""
    inner = cv2.erode(mask.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    if inner.sum() < 50:
        inner = mask > 0
    lightness = rgb2lab(rgb[inner].reshape(-1, 1, 3) / 255.0)[..., 0].ravel()
    return float(np.percentile(lightness, 90) - np.percentile(lightness, 10))


def logo_inliers(ref: np.ndarray, box: dict, out: np.ndarray, out_mask: np.ndarray) -> int:
    """Count geometrically consistent SIFT matches for the marked logo region."""
    height, width = ref.shape[:2]
    x0, y0 = int(box["x"] * width), int(box["y"] * height)
    x1, y1 = int((box["x"] + box["w"]) * width), int((box["y"] + box["h"]) * height)
    logo = cv2.cvtColor(ref[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    if logo.size == 0:
        return 0
    if max(logo.shape) < 200:
        factor = 200 / max(logo.shape)
        logo = cv2.resize(logo, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)

    sift = cv2.SIFT_create(nfeatures=3000)
    target = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY)
    search = cv2.dilate(out_mask, np.ones((15, 15), np.uint8)) * 255
    kp_logo, des_logo = sift.detectAndCompute(logo, None)
    kp_out, des_out = sift.detectAndCompute(target, search)
    if des_logo is None or des_out is None or len(kp_out) < 2:
        return 0

    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(des_logo, des_out, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < 4:
        return 0
    src = np.float32([kp_logo[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_out[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    _, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=5)
    return int(inliers.sum()) if inliers is not None else 0


def check_garment(
    ref: np.ndarray,
    out: np.ndarray,
    category: str,
    scene: str,
    logo_box: dict | None = None,
) -> list[GateResult]:
    ref_mask = flat_garment_mask(ref)
    out_mask = worn_garment_mask(out, category)
    if out_mask.mean() < MIN_COVERAGE:
        return [
            GateResult(
                "garment_color",
                "fail",
                None,
                "The garment could not be found in the output.",
                "Make sure the model is clearly wearing the exact garment from the reference.",
            )
        ]

    ref_palette = palette(ref, ref_mask)
    delta = palette_distance(ref_palette, palette(out, out_mask))
    color_status = grade_lower(delta, COLOR_DELTA_E[scene])
    hex_colors = _hex_colors(ref_palette[0])
    results = [
        GateResult(
            "garment_color",
            color_status,
            round(delta, 2),
            f"Color difference is Delta E {delta:.1f}.",
            f"Match the garment's exact colors: {', '.join(hex_colors)}.",
        )
    ]

    similarity = pattern_similarity(ref, ref_mask, out, out_mask)
    pattern_status = grade_higher(similarity, PATTERN_SIMILARITY)
    pattern_reason = f"Pattern and texture similarity is {similarity:.2f}."
    ref_spread = lightness_spread(ref, ref_mask)
    if ref_spread >= PATTERN_MIN_CONTRAST:
        kept = lightness_spread(out, out_mask) / ref_spread
        faded = grade_higher(kept, PATTERN_CONTRAST)
        if RANK[faded] > RANK[pattern_status]:
            pattern_status = faded
            pattern_reason = f"The pattern looks faded: it keeps {kept:.0%} of the original light-to-dark contrast."
    results.append(
        GateResult(
            "garment_pattern",
            pattern_status,
            round(similarity, 3),
            pattern_reason,
            "Preserve the garment's exact pattern, scale and fabric texture, with full-strength contrast between its colors.",
        )
    )

    if logo_box:
        inliers = logo_inliers(ref, logo_box, out, out_mask)
        results.append(
            GateResult(
                "garment_logo",
                grade_higher(inliers, LOGO_INLIERS),
                float(inliers),
                f"{inliers} logo features matched.",
                "Reproduce the logo exactly, with the same text, shape and placement.",
            )
        )
    return results


def _hex_colors(lab_centers: np.ndarray) -> list[str]:
    from skimage.color import lab2rgb

    rgb = (lab2rgb(lab_centers.reshape(-1, 1, 3)).reshape(-1, 3) * 255).round().astype(int)
    return [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in rgb]
