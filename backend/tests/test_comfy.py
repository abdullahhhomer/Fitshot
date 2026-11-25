"""Checks the ComfyUI graphs against the installed node definitions."""
import json

import numpy as np
import pytest

from fitshot.config import ROOT
from fitshot.generators.comfy_graph import (
    POSE_KEYPOINTS,
    draw_skeleton,
    face_refine_graph,
    skin_graph,
    shot_graph,
    skeleton_from_mediapipe,
    working_size,
)
from fitshot.generators.comfyui import clean_garment

OBJECT_INFO = ROOT / "comfyui" / "object_info.json"


def validate(graph, info):
    for node_id, node in graph.items():
        spec = info[node["class_type"]]
        required = spec["input"].get("required", {})
        optional = spec["input"].get("optional", {})
        missing = set(required) - set(node["inputs"])
        assert not missing, f"{node_id} {node['class_type']} is missing {missing}"
        for name, value in node["inputs"].items():
            assert name in required or name in optional, f"{node['class_type']} has no input {name}"
            expected = (required.get(name) or optional.get(name))[0]
            if isinstance(value, list):
                source = graph[value[0]]
                produced = info[source["class_type"]]["output"][value[1]]
                assert produced == expected, f"{node['class_type']}.{name}: {produced} != {expected}"


@pytest.mark.skipif(not OBJECT_INFO.exists(), reason="ComfyUI node definitions are not available")
def test_graphs_match_installed_nodes():
    info = json.loads(OBJECT_INFO.read_text(encoding="utf-8"))
    validate(skin_graph("b.png", "m.png", "p.png", "prompt", 1), info)
    validate(shot_graph("r.png", "l.png", "p.png", "prompt", 896, 1152, 1), info)
    validate(face_refine_graph("c.png", "r.png", "prompt", 1), info)


def test_working_size_keeps_aspect_and_sdxl_grid():
    width, height = working_size(1536, 2048)
    assert width % 8 == 0 and height % 8 == 0
    assert abs(width / height - 0.75) < 0.01
    assert 900_000 < width * height < 1_200_000


@pytest.mark.parametrize("pose", POSE_KEYPOINTS)
def test_every_pose_has_a_full_skeleton(pose):
    points = POSE_KEYPOINTS[pose]
    assert len(points) == 18
    assert all(0 < x < 1 and 0 < y < 1 for x, y in points)
    assert draw_skeleton(points, 896, 1152).any()


def test_hidden_mediapipe_joints_are_not_drawn():
    person = np.zeros((33, 3))
    person[:, :2] = [100, 100]
    assert not skeleton_from_mediapipe(person, 200, 200).any()


def test_clean_garment_centers_product_on_white():
    image = np.full((400, 600, 3), 235, np.uint8)
    image[150:250, 200:400] = (150, 30, 40)
    result = clean_garment(image)
    assert result.shape == (512, 512, 3)
    assert (result[2, 2] == 255).all()
    assert abs(int(result[256, 256, 0]) - 150) < 5


def test_blend_keeps_everything_outside_the_region_identical():
    from fitshot.generators.comfyui import blend_region

    base = np.random.default_rng(3).integers(0, 255, (1152, 896, 3), dtype=np.uint8)
    region = np.zeros((1024, 768), np.uint8)
    region[300:700, 200:560] = 1
    generated = np.full((1024, 768, 3), 40, np.uint8)
    out = blend_region(base, generated, region)
    assert out.shape == base.shape
    assert (out[:200] == base[:200]).all() and (out[-200:] == base[-200:]).all()
    assert abs(int(out[560, 448, 0]) - 40) <= 1


def test_try_on_pads_phone_photos_instead_of_stretching():
    from fitshot.generators.catvton import pad_to_aspect

    photo = np.random.default_rng(4).integers(0, 255, (1600, 900, 3), dtype=np.uint8)
    canvas, (x0, y0, x1, y1) = pad_to_aspect(photo, 0.75)
    assert abs(canvas.shape[1] / canvas.shape[0] - 0.75) < 0.01
    assert (canvas[y0:y1, x0:x1] == photo).all()


def test_arm_guard_keeps_hands_and_the_bare_forearm_out_of_a_short_sleeve_edit():
    from fitshot.generators.comfyui import _arm_guard

    person = np.zeros((33, 3), np.float32)
    joints = {11: (60, 60), 13: (55, 110), 15: (52, 160), 17: (50, 175), 19: (53, 178), 21: (56, 170)}
    for i, (x, y) in joints.items():
        person[i] = (x, y, 1.0)
    short = _arm_guard(person, 200, 260, "short")
    long = _arm_guard(person, 200, 260, "long")
    assert short[170, 52] and long[170, 52]  # the hand is always guarded
    assert short[122, 54] and not long[122, 54]  # the forearm only when the new sleeves are short
    assert not short[70, 59]  # the shoulder stays editable for the new sleeve


def test_bare_arms_are_made_once_per_photo_and_sleeve_length(monkeypatch):
    from fitshot.generators import comfyui

    calls = []
    monkeypatch.setattr(comfyui.ComfyUIGenerator, "_bare_arms", lambda self, image, sleeves: calls.append(sleeves) or image + 1)
    comfyui._BARE.clear()
    gen = comfyui.ComfyUIGenerator()
    photo = np.zeros((40, 30, 3), np.uint8)
    first = gen.bare_arms(photo, "short")
    assert (gen.bare_arms(photo, "short") == first).all()
    gen.bare_arms(photo, "long")
    assert calls == ["short", "long"]


def test_two_looks_of_one_photo_share_a_single_bare_arms_run(monkeypatch):
    import threading
    import time

    from fitshot.generators import comfyui

    calls = []

    def slow(self, image, sleeves):
        calls.append(1)
        time.sleep(0.2)
        return image

    monkeypatch.setattr(comfyui.ComfyUIGenerator, "_bare_arms", slow)
    comfyui._BARE.clear()
    photo = np.full((40, 30, 3), 7, np.uint8)
    threads = [threading.Thread(target=comfyui.ComfyUIGenerator().bare_arms, args=(photo, "short")) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1
