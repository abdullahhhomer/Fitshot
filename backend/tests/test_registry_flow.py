"""The AI model registry and the Fitting Room flow it feeds."""
import numpy as np
import pytest

from fitshot import api as api_module
from fitshot import db, registry
from tests.test_api import ScriptedGenerator, client, make_model, make_product, png, run_all  # noqa: F401
from skimage import data

# Saved before the test client replaces it with a scripted stand-in.
REAL_REQUIRE_DRESSER = api_module.require_dresser


@pytest.fixture()
def models(client, monkeypatch):
    """Every catalog model counts as ready unless a test says otherwise."""
    state = {"ready": set(registry.CATALOG)}
    monkeypatch.setattr(
        registry, "runtime",
        lambda adapter, row: ("ready", "ok") if adapter.id in state["ready"] else ("unavailable", "Start its service."),
    )
    with db.connect() as conn:
        conn.execute("DELETE FROM ai_models")
    return state


def test_a_model_is_added_validated_made_default_and_removed(client, models):
    listing = client.get("/api/ai-models").json()
    assert listing["added"] == []
    assert {m["id"] for m in listing["catalog"]} >= {"fashn", "fashn_hosted", "catvton", "leffa"}

    added = client.post("/api/ai-models", json={"id": "fashn_hosted"})
    assert added.status_code == 201, added.text
    assert added.json()["available"] and added.json()["is_default"]  # the first model becomes the default
    assert client.get("/api/status").json()["generators"]["fashn_hosted"]["ready"]
    assert client.post("/api/ai-models", json={"id": "fashn_hosted"}).status_code == 409  # already added

    client.post("/api/ai-models", json={"id": "nano_banana"})
    assert client.post("/api/ai-models/nano_banana/default").json()["is_default"]
    assert client.get("/api/status").json()["default_generator"] == "nano_banana"

    removed = client.delete("/api/ai-models/nano_banana")
    assert removed.status_code == 200 and removed.json()["deleted"] == []
    status = client.get("/api/status").json()
    assert not status["generators"]["nano_banana"]["ready"]  # gone from the Fitting Room
    assert status["default_generator"] == "fashn_hosted"  # the default moves to a model still added


def test_an_unsupported_model_cannot_be_added(client, models):
    response = client.post("/api/ai-models", json={"id": "leffa"})
    assert response.status_code == 409 and "no adapter" in response.json()["detail"]


def test_a_model_that_fails_validation_is_not_offered(client, models):
    models["ready"].discard("catvton")
    added = client.post("/api/ai-models", json={"id": "catvton"}).json()
    assert added["status"] == "unavailable" and not added["available"]
    assert "Start its service" in added["detail"]
    assert not client.get("/api/status").json()["generators"]["catvton"]["ready"]
    assert client.post("/api/ai-models/catvton/default").status_code == 409

    with pytest.raises(api_module.HTTPException) as refused:
        REAL_REQUIRE_DRESSER("catvton")  # what a try-on request meets: no silent swap to another model
    assert refused.value.status_code == 409 and "Choose another model" in refused.value.detail


def test_a_model_in_use_cannot_be_removed(client, models, monkeypatch):
    client.post("/api/ai-models", json={"id": "nano_banana"})
    model = make_model(client)
    job = client.post(
        "/api/jobs",
        json={"product_ids": [make_product(client)["id"]], "model_id": model["id"], "scene": "studio",
              "generator": "nano_banana", "num_images": 1},
    )
    assert job.status_code == 201, job.text
    response = client.delete("/api/ai-models/nano_banana")
    assert response.status_code == 409 and "still using" in response.json()["detail"]


def test_only_files_that_belong_to_the_model_alone_are_deleted(tmp_path, monkeypatch):
    project = tmp_path / "Fitshot"
    weights, cache, venv = project / "fashn" / "weights", project / "fashn" / "hf-cache", project / "catvton" / ".venv"
    for folder in (weights, cache, venv):
        folder.mkdir(parents=True)
        (folder / "f.bin").write_bytes(b"x" * 10)
    monkeypatch.setattr(registry, "PROJECT", project)
    found = registry.removable_files(registry.CATALOG["fashn"], {"path": "fashn/weights"})
    assert sorted(p.name for p in found) == ["hf-cache", "weights"]  # never the shared Python environment
    outside = registry.removable_files(registry.CATALOG["fashn"], {"path": str(tmp_path)})
    assert all(project.resolve() in p.parents for p in outside)  # nothing outside the project


def test_built_in_people_are_listed_with_their_framing(client, monkeypatch):
    monkeypatch.setattr(api_module, "person_framing", lambda image: "full")
    model = make_model(client)
    people = client.get("/api/people").json()
    assert [p["model_id"] for p in people] == [model["id"]]
    assert people[0]["framing"] == "full" and "dress" in people[0]["fits"]
    assert client.get("/api/live-photos").json() == []  # brand photos are not live photos


def _person(visible: set[int]) -> np.ndarray:
    person = np.zeros((33, 3), np.float32)
    for i in visible:
        person[i, 2] = 1.0
    return person


def test_full_body_mode_needs_the_feet_in_the_photo(client, monkeypatch):
    upper_body = _person({0, 11, 12})
    monkeypatch.setattr(api_module, "detect_poses", lambda image: [upper_body])
    monkeypatch.setattr(api_module, "person_framing", lambda image: "half")
    photo = {"photo": ("me.png", png(data.astronaut()), "image/png")}
    full = client.post("/api/selfies", data={"consent": "true", "mode": "full"}, files=photo)
    assert full.status_code == 422 and "head to feet" in full.json()["detail"]
    half = client.post("/api/selfies", data={"consent": "true", "mode": "half"}, files=photo)
    assert half.status_code == 201, half.text
    live = client.get("/api/live-photos").json()
    assert live[0]["framing"] == "half" and live[0]["fits"] == ["top", "outerwear"]


def test_trousers_need_a_full_body_photo_and_settings_are_checked(client, monkeypatch):
    monkeypatch.setattr(api_module, "detect_poses", lambda image: [_person({0, 11, 12})])
    monkeypatch.setattr(api_module, "person_framing", lambda image: "half")
    me = client.post(
        "/api/selfies", data={"consent": "true", "mode": "half"},
        files={"photo": ("me.png", png(data.astronaut()), "image/png")},
    ).json()
    shot = client.get("/api/live-photos").json()[0]["shot_id"]
    trousers = client.post(
        "/api/products", data={"sku": "TR-1", "name": "Trousers", "category": "bottom"},
        files={"front": ("t.png", png(data.coffee()), "image/png")},
    ).json()
    body = {"product_ids": [trousers["id"]], "model_id": me["id"], "scene": "studio", "generator": "fashn",
            "num_images": 1, "shot_id": shot}
    response = client.post("/api/jobs", json=body)
    assert response.status_code == 409 and "full-body photo" in response.json()["detail"]

    top = make_product(client)
    body["product_ids"] = [top["id"]]
    assert client.post("/api/jobs", json={**body, "settings": {"steps": 99}}).status_code == 400
    assert client.post("/api/jobs", json={**body, "settings": {"photo_type": "folded"}}).status_code == 400
    ok = client.post("/api/jobs", json={**body, "settings": {"steps": 20, "photo_type": "model"}})
    assert ok.status_code == 201, ok.text


def test_results_keep_every_try_on_with_its_model_and_settings(client, monkeypatch):
    model = make_model(client)
    product = make_product(client)
    for steps in (20, 40):
        response = client.post(
            "/api/jobs",
            json={"product_ids": [product["id"]], "model_id": model["id"], "scene": "studio", "generator": "fashn",
                  "num_images": 1, "settings": {"steps": steps}},
        )
        assert response.status_code == 201, response.text
    run_all(ScriptedGenerator())
    results = client.get("/api/results").json()
    assert len(results) == 2  # a second try-on never overwrites the first
    assert {r["settings"]["steps"] for r in results} == {20, 40}
    assert results[0]["person_name"] == "Ava" and results[0]["generator"] == "fashn"
