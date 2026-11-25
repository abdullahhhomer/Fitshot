"""FASHN VTON 1.5 through Hugging Face Spaces, tested without the network."""
import numpy as np
import pytest
from gradio_client.exceptions import AppError
from gradio_client.utils import QueueError

from fitshot.generators import fashn
from fitshot.generators.base import DressRequest, GenerationError

PERSON = np.full((120, 90, 3), 128, np.uint8)
GARMENT = np.full((60, 60, 3), 200, np.uint8)


@pytest.fixture()
def offline(monkeypatch):
    monkeypatch.setattr(fashn.settings, "hf_token", "hf_test")
    monkeypatch.setattr(fashn.settings, "fashn_spaces", "a/one,b/two")
    monkeypatch.setattr(fashn, "photo_type", lambda garment: "flat-lay")
    monkeypatch.setattr(fashn, "keep_original_outside_clothing", lambda base, generated, category: generated)
    calls = []
    return calls


def request(category="top"):
    return DressRequest(PERSON, GARMENT, category, "studio", PERSON)


def test_a_busy_space_falls_through_to_the_next(offline, monkeypatch):
    def call(space, person, garment, category, kind, seed, steps, guidance):
        offline.append((space, category, kind))
        if space == "a/one":
            raise QueueError("Queue is full! Please try again.")
        return PERSON

    monkeypatch.setattr(fashn, "_call", call)
    result = fashn.FashnGenerator("hosted").dress(request("dress"))
    assert [c[0] for c in offline] == ["a/one", "b/two"]
    assert offline[-1][1:] == ("one-pieces", "flat-lay")
    assert "b/two" in result.model and result.usd == 0.0


def test_a_used_up_quota_stops_with_a_clear_message(offline, monkeypatch):
    monkeypatch.setattr(fashn, "_call", lambda *a: (_ for _ in ()).throw(AppError("You have exceeded your GPU quota")))
    with pytest.raises(GenerationError) as caught:
        fashn.FashnGenerator("hosted").dress(request())
    assert not caught.value.retryable
    assert "quota" in str(caught.value)


def test_every_space_busy_can_be_retried(offline, monkeypatch):
    monkeypatch.setattr(fashn, "_call", lambda *a: (_ for _ in ()).throw(QueueError("full")))
    with pytest.raises(GenerationError) as caught:
        fashn.FashnGenerator("hosted").dress(request())
    assert caught.value.retryable


def test_no_token_means_not_ready(monkeypatch):
    monkeypatch.setattr(fashn.settings, "hf_token", "")
    ready, reason = fashn.FashnGenerator("hosted").status()
    assert not ready and "HF_TOKEN" in reason


def test_categories_map_to_fashn_names():
    assert fashn.CATEGORY == {"top": "tops", "outerwear": "tops", "bottom": "bottoms", "dress": "one-pieces"}


def test_the_local_model_runs_on_this_pc_with_its_settings(offline, monkeypatch):
    monkeypatch.setattr(fashn, "local_ready", lambda: True)
    monkeypatch.setattr(fashn, "photo_type", lambda garment: "model")  # someone wears it in the garment photo
    seen = {}
    monkeypatch.setattr(fashn, "_local", lambda request, category, kind, seed, steps, guidance: seen.update(
        category=category, kind=kind, steps=steps, guidance=guidance) or PERSON)
    monkeypatch.setattr(fashn, "_call", lambda *a: pytest.fail("the Hugging Face route must not be used"))
    req = request("bottom")
    req.options = {"steps": 20, "guidance": 2.0, "photo_type": "model"}
    result = fashn.FashnGenerator("local").dress(req)
    assert seen == {"category": "bottoms", "kind": "model", "steps": 20, "guidance": 2.0}
    assert "on this PC" in result.model


def test_the_local_model_never_falls_back_to_hugging_face(offline, monkeypatch):
    monkeypatch.setattr(fashn, "local_ready", lambda: False)
    monkeypatch.setattr(fashn, "_call", lambda *a: pytest.fail("the Hugging Face route must not be used"))
    with pytest.raises(GenerationError) as caught:
        fashn.FashnGenerator("local").dress(request())
    assert "run-fashn.cmd" in str(caught.value)
    ready, reason = fashn.FashnGenerator("local").status()
    assert not ready and "run-fashn.cmd" in reason


def test_model_worn_mode_is_never_used_on_a_flat_lay_photo(offline, monkeypatch):
    """Model-worn mode cuts the garment out of a person; on a flat-lay it would paste the whole photo."""
    monkeypatch.setattr(fashn, "local_ready", lambda: True)
    seen = {}
    monkeypatch.setattr(fashn, "_local", lambda request, category, kind, seed, steps, guidance: seen.update(kind=kind) or PERSON)
    req = request()
    req.options = {"photo_type": "model"}  # chosen by hand, but nobody is in the garment photo
    fashn.FashnGenerator("local").dress(req)
    assert seen["kind"] == "flat-lay"
