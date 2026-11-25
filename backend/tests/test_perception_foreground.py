"""The person in front is "you"; people in the background are ignored."""
import types

import numpy as np

from fitshot.qa import perception


def _face(size: float, x: float = 0.0):
    return types.SimpleNamespace(
        bbox=np.array([x, 0, x + size, size], np.float32), kps=np.zeros((5, 2), np.float32),
        normed_embedding=np.zeros(512, np.float32), det_score=0.9,
    )


def test_small_background_faces_are_left_out(monkeypatch):
    found = [_face(40, 300), _face(120), _face(110, 500)]
    monkeypatch.setattr(perception, "_face_app", lambda: types.SimpleNamespace(get=lambda image: found))
    image = np.zeros((400, 700, 3), np.uint8)
    faces = perception.detect_faces(image)
    assert [int(f.bbox[2] - f.bbox[0]) for f in faces] == [120, 110]  # two people up front, no passer-by
    assert len(perception.detect_faces(image, include_background=True)) == 3


def _person(x0: float, x1: float, y0: float, y1: float) -> np.ndarray:
    person = np.zeros((33, 3), np.float32)
    person[:, 0] = np.linspace(x0, x1, 33)
    person[:, 1] = np.linspace(y0, y1, 33)
    person[:, 2] = 1.0
    return person


def test_the_biggest_person_comes_first_and_only_their_clothes_count(monkeypatch):
    background = _person(10, 40, 50, 120)
    front = _person(200, 320, 20, 380)
    monkeypatch.setattr(perception, "detect_poses", lambda rgb: [front, background])
    from PIL import Image

    full = Image.fromarray(np.full((400, 400), 255, np.uint8))
    monkeypatch.setattr(perception, "_cloth", lambda: types.SimpleNamespace(predict=lambda image: [full, full, full]))
    masks = perception.segment_clothes(np.zeros((400, 400, 3), np.uint8))
    assert masks["upper"][200, 260] == 1  # the person in front
    assert masks["upper"][80, 20] == 0  # the person in the background


def test_poses_are_sorted_biggest_first(monkeypatch):
    small, big = _person(10, 40, 50, 120), _person(200, 320, 20, 380)

    def landmarks(person):
        return [types.SimpleNamespace(x=p[0] / 400, y=p[1] / 400, visibility=p[2]) for p in person]

    result = types.SimpleNamespace(pose_landmarks=[landmarks(small), landmarks(big)])
    monkeypatch.setattr(perception, "_pose", lambda: types.SimpleNamespace(detect=lambda image: result))
    monkeypatch.setattr(perception, "_mp_image", lambda rgb: None)
    people = perception.detect_poses(np.zeros((400, 400, 3), np.uint8))
    assert people[0][0, 0] > 150  # the big person in front is first
