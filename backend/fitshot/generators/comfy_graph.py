"""ComfyUI API graphs and OpenPose skeleton rendering."""
from __future__ import annotations

import math

import cv2
import numpy as np

CHECKPOINT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
OPENPOSE = "openpose_sdxl.safetensors"
INSTANTID = "ip-adapter.bin"
INSTANTID_CONTROLNET = "instantid_controlnet.safetensors"

REQUIRED_MODELS = {
    ("CheckpointLoaderSimple", "ckpt_name"): (CHECKPOINT,),
    ("ControlNetLoader", "control_net_name"): (OPENPOSE, INSTANTID_CONTROLNET),
    ("InstantIDModelLoader", "instantid_file"): (INSTANTID,),
}

NEGATIVE = (
    "deformed, distorted, disfigured, bad anatomy, extra limbs, extra fingers, fused fingers, "
    "cartoon, illustration, 3d render, text, logo, watermark, blurry, low quality"
)

# OpenPose order: nose, neck, right arm, left arm, right leg, left leg, eyes, ears.
LIMBS = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10),
    (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17),
]
COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
    (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
    (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85),
]
MEDIAPIPE_TO_OPENPOSE = {
    0: 0, 2: 12, 3: 14, 4: 16, 5: 11, 6: 13, 7: 15, 8: 24, 9: 26, 10: 28,
    11: 23, 12: 25, 13: 27, 14: 5, 15: 2, 16: 8, 17: 7,
}

_FRONT = [
    (0.500, 0.115), (0.500, 0.190), (0.410, 0.205), (0.380, 0.335), (0.370, 0.455),
    (0.590, 0.205), (0.620, 0.335), (0.630, 0.455), (0.450, 0.480), (0.445, 0.690),
    (0.440, 0.900), (0.550, 0.480), (0.555, 0.690), (0.560, 0.900), (0.485, 0.100),
    (0.515, 0.100), (0.465, 0.110), (0.535, 0.110),
]


def _with(points, changes: dict[int, tuple[float, float]]):
    result = list(points)
    for index, value in changes.items():
        result[index] = value
    return result


_TURN = _with(
    _FRONT,
    {
        0: (0.475, 0.115), 2: (0.430, 0.205), 3: (0.405, 0.335), 4: (0.400, 0.455),
        5: (0.570, 0.205), 6: (0.590, 0.335), 7: (0.590, 0.455), 8: (0.460, 0.480),
        11: (0.535, 0.480), 14: (0.460, 0.100), 15: (0.495, 0.100), 16: (0.445, 0.112),
    },
)
POSE_KEYPOINTS = {
    "front": _FRONT,
    "three_quarter_left": _TURN,
    "three_quarter_right": [(1 - x, y) for x, y in _TURN],
    "walking": _with(
        _FRONT,
        {3: (0.395, 0.335), 4: (0.420, 0.445), 6: (0.610, 0.335), 7: (0.590, 0.450),
         9: (0.435, 0.670), 10: (0.455, 0.870), 12: (0.570, 0.695), 13: (0.600, 0.905)},
    ),
    "hand_on_hip": _with(_FRONT, {6: (0.695, 0.335), 7: (0.570, 0.455)}),
    "relaxed": _with(
        _FRONT,
        {2: (0.410, 0.215), 5: (0.590, 0.198), 8: (0.455, 0.472), 11: (0.555, 0.488),
         12: (0.585, 0.690), 13: (0.610, 0.895)},
    ),
}


def working_size(width: int, height: int, megapixels: float = 1.0) -> tuple[int, int]:
    """Closest SDXL-friendly size that keeps the image's aspect ratio."""
    scale = math.sqrt(megapixels * 1_048_576 / (width * height))
    return max(round(width * scale / 8) * 8, 64), max(round(height * scale / 8) * 8, 64)


def draw_skeleton(points: list[tuple[float, float] | None], width: int, height: int) -> np.ndarray:
    canvas = np.zeros((height, width, 3), np.uint8)
    thickness = max(round(width / 170), 3)
    pixels = [None if p is None else (round(p[0] * width), round(p[1] * height)) for p in points]
    for index, (a, b) in enumerate(LIMBS):
        if pixels[a] is None or pixels[b] is None:
            continue
        color = tuple(int(c * 0.6) for c in COLORS[index % len(COLORS)])
        cv2.line(canvas, pixels[a], pixels[b], color, thickness, cv2.LINE_AA)
    for index, point in enumerate(pixels):
        if point is not None:
            cv2.circle(canvas, point, thickness, COLORS[index], -1, cv2.LINE_AA)
    return canvas


def skeleton_from_mediapipe(person: np.ndarray, width: int, height: int, min_visibility: float = 0.5) -> np.ndarray:
    """Render an OpenPose image from MediaPipe landmarks given in pixels at this size."""

    def point(index: int) -> tuple[float, float] | None:
        x, y, visibility = person[index]
        return None if visibility < min_visibility else (x / width, y / height)

    points: list[tuple[float, float] | None] = [None] * 18
    for open_index, mp_index in MEDIAPIPE_TO_OPENPOSE.items():
        points[open_index] = point(mp_index)
    left, right = point(11), point(12)
    if left and right:
        points[1] = ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)
    return draw_skeleton(points, width, height)


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}

    def add(self, class_type: str, **inputs) -> str:
        node_id = str(len(self.nodes) + 1)
        self.nodes[node_id] = {"class_type": class_type, "inputs": inputs}
        return node_id


def skin_graph(base: str, mask: str, pose: str, prompt: str, seed: int, denoise: float = 0.6) -> dict:
    """SDXL refine of arms that were pre-painted in skin tone, holding the arm pose with OpenPose.

    Starting from the prefill (not from noise) keeps the person's own skin tone; the model only
    adds shading, texture and anatomy.
    """
    g = Graph()
    ckpt = g.add("CheckpointLoaderSimple", ckpt_name=CHECKPOINT)
    base_image = g.add("LoadImage", image=base)
    mask_image = g.add("LoadImage", image=mask)
    pose_image = g.add("LoadImage", image=pose)
    region = g.add("ImageToMask", image=[mask_image, 0], channel="red")
    positive = g.add("CLIPTextEncode", text=prompt, clip=[ckpt, 1])
    negative = g.add(
        "CLIPTextEncode", text=f"{NEGATIVE}, sleeve, fabric, cloth, gloves, arm warmers, bandage", clip=[ckpt, 1]
    )
    control = g.add("ControlNetLoader", control_net_name=OPENPOSE)
    conditioned = g.add(
        "ControlNetApplyAdvanced",
        positive=[positive, 0], negative=[negative, 0], control_net=[control, 0],
        image=[pose_image, 0], strength=0.8, start_percent=0.0, end_percent=0.9,
    )
    latent = g.add("VAEEncode", pixels=[base_image, 0], vae=[ckpt, 2])
    masked = g.add("SetLatentNoiseMask", samples=[latent, 0], mask=[region, 0])
    sampled = g.add(
        "KSampler",
        model=[ckpt, 0], seed=seed, steps=8, cfg=1.6, sampler_name="dpmpp_sde", scheduler="karras",
        positive=[conditioned, 0], negative=[conditioned, 1], latent_image=[masked, 0], denoise=denoise,
    )
    decoded = g.add("VAEDecode", samples=[sampled, 0], vae=[ckpt, 2])
    g.add("PreviewImage", images=[decoded, 0])
    return g.nodes


def face_refine_graph(crop: str, reference: str, prompt: str, seed: int) -> dict:
    """Re-render an enlarged face crop with InstantID, keeping its pose and light."""
    g = Graph()
    ckpt = g.add("CheckpointLoaderSimple", ckpt_name=CHECKPOINT)
    crop_image = g.add("LoadImage", image=crop)
    reference_image = g.add("LoadImage", image=reference)
    positive = g.add("CLIPTextEncode", text=prompt, clip=[ckpt, 1])
    negative = g.add("CLIPTextEncode", text=NEGATIVE, clip=[ckpt, 1])
    instantid = g.add("InstantIDModelLoader", instantid_file=INSTANTID)
    analysis = g.add("InstantIDFaceAnalysis", provider="CPU")
    id_control = g.add("ControlNetLoader", control_net_name=INSTANTID_CONTROLNET)
    identity = g.add(
        "ApplyInstantID",
        instantid=[instantid, 0], insightface=[analysis, 0], control_net=[id_control, 0],
        image=[reference_image, 0], model=[ckpt, 0], positive=[positive, 0], negative=[negative, 0],
        weight=0.9, start_at=0.0, end_at=1.0, image_kps=[crop_image, 0],
    )
    latent = g.add("VAEEncode", pixels=[crop_image, 0], vae=[ckpt, 2])
    sampled = g.add(
        "KSampler",
        model=[identity, 0], seed=seed, steps=8, cfg=2.0, sampler_name="dpmpp_sde", scheduler="karras",
        positive=[identity, 1], negative=[identity, 2], latent_image=[latent, 0], denoise=0.55,
    )
    decoded = g.add("VAEDecode", samples=[sampled, 0], vae=[ckpt, 2])
    g.add("PreviewImage", images=[decoded, 0])
    return g.nodes


def shot_graph(reference: str, face_layout: str, pose: str, prompt: str, width: int, height: int, seed: int) -> dict:
    """SDXL text-to-image with InstantID for identity and OpenPose for the body."""
    g = Graph()
    ckpt = g.add("CheckpointLoaderSimple", ckpt_name=CHECKPOINT)
    reference_image = g.add("LoadImage", image=reference)
    layout_image = g.add("LoadImage", image=face_layout)
    pose_image = g.add("LoadImage", image=pose)
    positive = g.add("CLIPTextEncode", text=prompt, clip=[ckpt, 1])
    negative = g.add("CLIPTextEncode", text=NEGATIVE, clip=[ckpt, 1])
    instantid = g.add("InstantIDModelLoader", instantid_file=INSTANTID)
    analysis = g.add("InstantIDFaceAnalysis", provider="CPU")
    id_control = g.add("ControlNetLoader", control_net_name=INSTANTID_CONTROLNET)
    identity = g.add(
        "ApplyInstantID",
        instantid=[instantid, 0], insightface=[analysis, 0], control_net=[id_control, 0],
        image=[reference_image, 0], model=[ckpt, 0], positive=[positive, 0], negative=[negative, 0],
        weight=0.8, start_at=0.0, end_at=1.0, image_kps=[layout_image, 0],
    )
    pose_control = g.add("ControlNetLoader", control_net_name=OPENPOSE)
    conditioned = g.add(
        "ControlNetApplyAdvanced",
        positive=[identity, 1], negative=[identity, 2], control_net=[pose_control, 0],
        image=[pose_image, 0], strength=0.8, start_percent=0.0, end_percent=0.9,
    )
    latent = g.add("EmptyLatentImage", width=width, height=height, batch_size=1)
    sampled = g.add(
        "KSampler",
        model=[identity, 0], seed=seed, steps=8, cfg=2.0, sampler_name="dpmpp_sde", scheduler="karras",
        positive=[conditioned, 0], negative=[conditioned, 1], latent_image=[latent, 0], denoise=1.0,
    )
    decoded = g.add("VAEDecode", samples=[sampled, 0], vae=[ckpt, 2])
    g.add("PreviewImage", images=[decoded, 0])
    return g.nodes
