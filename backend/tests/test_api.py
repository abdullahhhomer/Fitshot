"""End-to-end API tests with a scripted generator. No paid calls are made."""
import csv
import io
import zipfile

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from skimage import data

from fitshot import api as api_module
from fitshot import db
from fitshot.config import settings
from fitshot.generators.base import GenerationError, GenerationResult
from fitshot.pipeline import worker as worker_module
from fitshot.qa import gate as gate_module
from fitshot.qa.judge import Verdict
from fitshot.qa.types import GateResult


def png(array) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, "PNG")
    return buffer.getvalue()


def garment(color=(190, 30, 40)):
    image = np.full((512, 512, 3), 245, np.uint8)
    points = np.array([[150, 90], [362, 90], [450, 190], [385, 235], [355, 200], [355, 450], [157, 450], [157, 200], [127, 235], [62, 190]])
    cv2.fillPoly(image, [points], color)
    return image


class ScriptedGenerator:
    """Returns the base shot, optionally failing or removing the face first."""

    name = "scripted"

    def __init__(self, script=("good",)):
        self.script = list(script)
        self.calls = 0
        self.hints = []

    def status(self):
        return True, "test"

    def dress(self, request):
        step = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        self.hints.append(list(request.hints))
        if step == "error":
            raise GenerationError("provider rejected the request")
        image = request.base_shot.copy()
        if step == "no_face":
            image[:] = 128
        return GenerationResult(image, 0.05, "scripted", "scripted-v1")


class PassingJudge:
    def review(self, *_):
        return Verdict(garment_ok=True, hands_visible=False, hands_ok=True)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(api_module, "MEDIA", tmp_path / "media")
    # Tests never call the real vision model (it would read sleeve lengths over the network).
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(api_module.worker, "start", lambda: None)
    monkeypatch.setattr(api_module.worker, "stop", lambda: None)
    monkeypatch.setattr(api_module.worker, "notify", lambda: None)
    monkeypatch.setattr(api_module, "require_generator", lambda name: ScriptedGenerator())
    # The scripted generator stands in for an added, validated try-on model.
    monkeypatch.setattr(api_module, "require_dresser", lambda name: ScriptedGenerator())
    with TestClient(api_module.app) as test_client:
        yield test_client


def make_model(client, shots=1):
    portrait = png(data.astronaut())
    response = client.post(
        "/api/models",
        data={"name": "Ava", "rights_confirmed": "true"},
        files={"reference": ("ref.png", portrait, "image/png")},
    )
    assert response.status_code == 201, response.text
    model = response.json()
    for _ in range(shots):
        shot = client.post(
            f"/api/models/{model['id']}/shots/upload",
            data={"scene": "studio", "pose": "front"},
            files={"image": ("shot.png", portrait, "image/png")},
        )
        assert shot.status_code == 201, shot.text
        decided = client.patch(f"/api/shots/{shot.json()['id']}", json={"status": "approved"})
        assert decided.status_code == 200, decided.text
    return model


def make_product(client, sku="SKU-1"):
    response = client.post(
        "/api/products",
        data={"sku": sku, "name": "Red tee", "category": "top"},
        files={"front": ("front.png", png(garment()), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def start(client, model, product, num_images=1):
    response = client.post(
        "/api/jobs",
        json={"product_ids": [product["id"]], "model_id": model["id"], "scene": "studio", "generator": "nano_banana", "num_images": num_images},
    )
    assert response.status_code == 201, response.text
    return response.json()


def run_all(generator, judge=None):
    while (item := worker_module.claim_next()) is not None:
        worker_module.process_item(item, generator=generator, judge=judge)


def test_model_requires_rights_confirmation(client):
    response = client.post(
        "/api/models",
        data={"name": "Ava", "rights_confirmed": "false"},
        files={"reference": ("ref.png", png(data.astronaut()), "image/png")},
    )
    assert response.status_code == 400


def test_model_rejects_image_without_a_face(client):
    response = client.post(
        "/api/models",
        data={"name": "Ava", "rights_confirmed": "true"},
        files={"reference": ("ref.png", png(garment()), "image/png")},
    )
    assert response.status_code == 422


def test_rejects_non_image_upload(client):
    response = client.post(
        "/api/products",
        data={"sku": "A", "name": "B", "category": "top"},
        files={"front": ("front.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400


def test_database_is_not_served(client):
    assert client.get("/media/../fitshot.db").status_code == 404
    assert client.get("/media/%2e%2e/fitshot.db").status_code == 404


def test_job_needs_an_approved_shot(client):
    model = make_model(client, shots=0)
    product = make_product(client)
    response = client.post(
        "/api/jobs",
        json={"product_ids": [product["id"]], "model_id": model["id"], "scene": "studio", "generator": "nano_banana"},
    )
    assert response.status_code == 409


def test_no_judge_routes_to_review_then_human_can_approve_and_export(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    run_all(ScriptedGenerator())

    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert detail["items"][0]["status"] == "review"
    assert client.get(f"/api/jobs/{job['id']}/export").status_code == 409

    item_id = detail["items"][0]["id"]
    assert client.post(f"/api/items/{item_id}/review", json={"decision": "approve"}).json()["status"] == "approved"
    export = client.get(f"/api/jobs/{job['id']}/export")
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        names = archive.namelist()
        rows = list(csv.DictReader(io.StringIO(archive.read("results.csv").decode())))
    assert "images/SKU-1_studio_front.png" in names
    assert rows[0]["ai_generated"] == "yes"


def test_failed_attempts_retry_with_hints_stop_at_cap_and_count_cost(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    generator = ScriptedGenerator(["no_face"])
    run_all(generator, PassingJudge())

    assert generator.calls == settings.max_attempts
    assert generator.hints[0] == []
    assert any("face" in hint.lower() for hint in generator.hints[1])

    detail = client.get(f"/api/jobs/{job['id']}").json()
    item = detail["items"][0]
    assert item["status"] == "review"
    assert item["attempts"] == settings.max_attempts
    assert detail["usd"] == pytest.approx(0.05 * settings.max_attempts)


def test_failure_then_recovery_keeps_the_better_image(client, monkeypatch):
    # The scripted output is the base photo, so it cannot contain the test garment.
    monkeypatch.setattr(
        gate_module,
        "check_garment",
        lambda *_: [GateResult("garment_color", "pass", 1.0, "stubbed")],
    )
    model = make_model(client)
    job = start(client, model, make_product(client))
    generator = ScriptedGenerator(["no_face", "good"])
    run_all(generator, PassingJudge())

    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    assert generator.calls == 2
    assert item["status"] == "passed"
    assert item["qa"]["attempt"] == 2
    identity = next(g for g in item["qa"]["gates"] if g["name"] == "identity")
    assert identity["status"] == "pass"


def test_provider_error_marks_item_failed_without_cost(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    run_all(ScriptedGenerator(["error"]), PassingJudge())
    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert detail["items"][0]["status"] == "failed"
    assert detail["usd"] == 0


def test_failed_retry_keeps_the_existing_photo(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    run_all(ScriptedGenerator())
    before = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    photo = settings.data_dir / before["url"].lstrip("/")
    assert photo.exists()

    assert client.post(f"/api/items/{before['id']}/retry").json()["url"] == before["url"]
    run_all(ScriptedGenerator(["error"]), PassingJudge())

    after = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    assert after["status"] == "review"
    assert after["url"] == before["url"]
    assert "previous photo was kept" in after["error"]
    assert photo.exists()


def test_retry_needs_a_ready_generator(client, monkeypatch):
    model = make_model(client)
    job = start(client, model, make_product(client))
    run_all(ScriptedGenerator())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]

    def not_ready(name):
        raise api_module.HTTPException(409, f"{name} is not ready")

    # A retry goes through the registry check, so an unavailable model refuses it.
    monkeypatch.setattr(api_module, "require_dresser", not_ready)
    assert client.post(f"/api/items/{item['id']}/retry").status_code == 409
    assert client.get(f"/api/jobs/{job['id']}").json()["items"][0]["status"] == "review"


def test_a_decision_can_be_undone(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    run_all(ScriptedGenerator())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    assert client.post(f"/api/items/{item['id']}/reopen").status_code == 409

    client.post(f"/api/items/{item['id']}/review", json={"decision": "approve"})
    assert client.post(f"/api/items/{item['id']}/reopen").json()["status"] == "review"
    assert client.get(f"/api/jobs/{job['id']}/export").status_code == 409


def test_interrupted_items_resume(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    assert worker_module.claim_next() is not None
    assert worker_module.claim_next() is None
    assert worker_module.reset_interrupted() == 1
    assert worker_module.claim_next()["job_id"] == job["id"]


def test_cloud_and_local_generators_use_separate_lanes(client):
    """The GPU lane never takes a cloud item and the cloud lane never takes a GPU item."""
    model = make_model(client)
    job = start(client, model, make_product(client))
    assert worker_module.claim_next(cloud=False) is None
    assert worker_module.claim_next(cloud=True)["job_id"] == job["id"]

    worker_module.reset_interrupted()
    with db.connect() as conn:
        conn.execute("UPDATE jobs SET generator='catvton' WHERE id=?", (job["id"],))
    assert worker_module.claim_next(cloud=True) is None
    assert worker_module.claim_next(cloud=False)["job_id"] == job["id"]


def bulk_files(rows, images):
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(["sku", "name", "category", "image"])
    writer.writerows(rows)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        for name, content in images.items():
            z.writestr(name, content)
    return {
        "csv_file": ("products.csv", text.getvalue().encode(), "text/csv"),
        "images_zip": ("images.zip", archive.getvalue(), "application/zip"),
    }


def test_bulk_creates_all_items(client):
    model = make_model(client, shots=2)
    rows = [[f"S{i}", f"Tee {i}", "top", f"nested/s{i}.png"] for i in range(3)]
    images = {f"nested/s{i}.png": png(garment()) for i in range(3)}
    response = client.post(
        "/api/jobs/bulk",
        data={"model_id": model["id"], "scene": "studio", "num_images": "2"},
        files=bulk_files(rows, images),
    )
    assert response.status_code == 201, response.text
    assert response.json()["total"] == 6


def test_bad_bulk_row_saves_nothing(client):
    model = make_model(client)
    rows = [["S1", "Tee", "top", "s1.png"], ["S2", "Tee", "top", "missing.png"]]
    response = client.post(
        "/api/jobs/bulk",
        data={"model_id": model["id"], "scene": "studio"},
        files=bulk_files(rows, {"s1.png": png(garment())}),
    )
    assert response.status_code == 400
    assert "line 3" in response.json()["detail"]
    assert client.get("/api/products").json() == []
    assert client.get("/api/jobs").json() == []


def test_export_neutralizes_spreadsheet_formulas(client):
    model = make_model(client)
    job = start(client, model, make_product(client, sku="=HYPERLINK(1)"))
    run_all(ScriptedGenerator())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    client.post(f"/api/items/{item['id']}/review", json={"decision": "approve"})
    export = client.get(f"/api/jobs/{job['id']}/export")
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        row = next(csv.DictReader(io.StringIO(archive.read("results.csv").decode())))
    assert row["sku"].startswith("'=")


def test_costs_report_accepted_image_cost(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    run_all(ScriptedGenerator(["no_face", "good"]), PassingJudge())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    if item["status"] == "review":
        client.post(f"/api/items/{item['id']}/review", json={"decision": "approve"})
    costs = client.get("/api/costs").json()
    assert costs["accepted_images"] == 1
    assert costs["usd_per_accepted"] >= 0.10


def test_fitting_room_tries_one_chosen_pose_and_lists_looks(client):
    model = make_model(client, shots=2)
    product = make_product(client)
    shots = client.get(f"/api/models/{model['id']}/shots").json()
    chosen = shots[-1]["id"]
    response = client.post(
        "/api/jobs",
        json={
            "product_ids": [product["id"]],
            "model_id": model["id"],
            "scene": "studio",
            "generator": "nano_banana",
            "num_images": 1,
            "shot_id": chosen,
        },
    )
    assert response.status_code == 201, response.text
    looks = client.get(f"/api/looks?model_id={model['id']}&scene=studio").json()
    assert [look["shot_id"] for look in looks] == [chosen]
    assert looks[0]["scene"] == "studio" and looks[0]["product_id"] == product["id"]
    assert client.get(f"/api/looks?model_id={model['id']}&scene=beach").json() == []


def test_fitting_room_refuses_a_pose_from_another_scene_or_model(client):
    model = make_model(client, shots=1)
    product = make_product(client)
    shot = client.get(f"/api/models/{model['id']}/shots").json()[0]["id"]
    response = client.post(
        "/api/jobs",
        json={"product_ids": [product["id"]], "model_id": model["id"], "scene": "beach", "generator": "nano_banana", "shot_id": shot},
    )
    assert response.status_code == 409


def _selfie(client, consent="true"):
    return client.post(
        "/api/selfies",
        data={"consent": consent},
        files={"photo": ("me.png", png(data.astronaut()), "image/png")},
    )


def test_selfie_needs_consent(client):
    assert _selfie(client, consent="false").status_code == 400


def test_selfie_needs_a_visible_body(client, monkeypatch):
    import fitshot.api as api_module

    no_shoulders = np.zeros((33, 3), np.float32)
    monkeypatch.setattr(api_module, "detect_poses", lambda image: [no_shoulders])
    response = _selfie(client)
    assert response.status_code == 422
    assert "shoulders" in response.json()["detail"]


def _faces_by_call(monkeypatch, *embeddings):
    """detect_faces returns one face per call, in order (face photo first, then the body photo)."""
    import types

    import fitshot.api as api_module

    calls = iter(embeddings)

    def detect(image):
        embedding = next(calls)
        if embedding is None:
            return []
        return [types.SimpleNamespace(embedding=np.asarray(embedding, np.float32), bbox=np.array([0, 0, 10, 10]))]

    person = np.zeros((33, 3), np.float32)
    person[:, 2] = 1.0
    monkeypatch.setattr(api_module, "detect_faces", detect)
    monkeypatch.setattr(api_module, "detect_poses", lambda image: [person])


def _two_photos(client):
    return client.post(
        "/api/selfies",
        data={"consent": "true"},
        files={
            "photo": ("body.png", png(data.astronaut()), "image/png"),
            "face": ("face.png", png(data.astronaut()), "image/png"),
        },
    )


def test_a_face_photo_and_a_faceless_body_photo_make_a_model(client, monkeypatch):
    me = np.zeros(512)
    me[0] = 1
    _faces_by_call(monkeypatch, me, None)  # face photo first, then a headless body photo
    response = _two_photos(client)
    assert response.status_code == 201, response.text
    assert response.json()["approved_shots"] == {"studio": 1}


def test_face_and_body_photos_of_different_people_are_refused(client, monkeypatch):
    me, someone = np.zeros(512), np.zeros(512)
    me[0], someone[1] = 1, 1
    _faces_by_call(monkeypatch, me, someone)
    response = _two_photos(client)
    assert response.status_code == 422
    assert "different people" in response.json()["detail"]


def test_a_body_photo_alone_is_enough_even_without_a_face(client, monkeypatch):
    _faces_by_call(monkeypatch, None)
    response = _selfie(client)
    assert response.status_code == 201, response.text
    assert response.json()["approved_shots"] == {"studio": 1}


def test_a_face_photo_alone_makes_a_model_waiting_for_its_body(client, monkeypatch):
    me = np.zeros(512)
    me[0] = 1
    _faces_by_call(monkeypatch, me)
    response = client.post(
        "/api/selfies",
        data={"consent": "true"},
        files={"face": ("face.png", png(data.astronaut()), "image/png")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["approved_shots"] == {}  # the body photo is made from the face next


def test_no_photo_at_all_is_refused(client):
    response = client.post("/api/selfies", data={"consent": "true"})
    assert response.status_code == 422
    assert "face, your body, or both" in response.json()["detail"]


def test_selfie_becomes_a_ready_model_and_can_be_removed(client, monkeypatch):
    import fitshot.api as api_module

    person = np.zeros((33, 3), np.float32)
    person[:, 2] = 1.0
    monkeypatch.setattr(api_module, "detect_poses", lambda image: [person])
    response = _selfie(client)
    assert response.status_code == 201, response.text
    me = response.json()
    assert me["kind"] == "self" and me["approved_shots"] == {"studio": 1}

    product = make_product(client)
    shot = client.get(f"/api/models/{me['id']}/shots").json()[0]
    assert shot["status"] == "approved"
    job = client.post(
        "/api/jobs",
        json={"product_ids": [product["id"]], "model_id": me["id"], "scene": "studio", "generator": "nano_banana", "num_images": 1},
    )
    assert job.status_code == 201, job.text
    assert client.delete(f"/api/models/{me['id']}").status_code == 409  # still queued

    with db.connect() as conn:
        conn.execute("UPDATE job_items SET status='failed'")
    reference = settings.data_dir / me["url"].lstrip("/")
    assert reference.exists()
    assert client.delete(f"/api/models/{me['id']}").status_code == 204
    assert not reference.exists()
    assert all(m["id"] != me["id"] for m in client.get("/api/models").json())
    assert client.get(f"/api/jobs/{job.json()['id']}").status_code == 404


def test_brand_models_cannot_be_removed_as_selfies(client):
    model = make_model(client, shots=0)
    assert client.delete(f"/api/models/{model['id']}").status_code == 409


def test_access_key_locks_api_and_media(client, monkeypatch):
    model = make_model(client, shots=0)
    monkeypatch.setattr(settings, "fitshot_access_key", "s3cret-key")
    assert client.get("/api/models").status_code == 401
    assert client.get(model["url"]).status_code == 401
    assert client.get("/api/models", headers={"X-FitShot-Key": "wrong"}).status_code == 401
    assert client.get("/api/models", headers={"X-FitShot-Key": "s3cret-key"}).status_code == 200
    # The media mount points at the real data folder in tests, so only check the gate lets it through.
    assert client.get(f"{model['url']}?key=s3cret-key").status_code != 401


def test_sleeve_length_is_read_once_and_remembered(client, monkeypatch):
    product = make_product(client)
    calls = []
    monkeypatch.setattr(settings, "gemini_api_key", "test")
    monkeypatch.setattr(worker_module, "read_sleeves", lambda *a: calls.append(1) or "short")
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT * FROM products WHERE id=?", (product["id"],))
    garment = np.zeros((8, 8, 3), np.uint8)
    assert worker_module.garment_sleeves(row, garment) == "short"
    assert worker_module.garment_sleeves(row, garment) == "short"
    assert len(calls) == 1


def test_worker_runs_two_threads_in_each_lane(monkeypatch):
    started = []
    monkeypatch.setattr(worker_module, "reset_interrupted", lambda: 0)
    monkeypatch.setattr(worker_module.threading.Thread, "start", lambda self: started.append(self.name))
    worker_module.Worker().start()
    assert sorted(started) == ["fitshot-cloud-0", "fitshot-cloud-1", "fitshot-local-0", "fitshot-local-1"]


def test_a_note_becomes_a_lesson_for_the_garment_and_tries_again(client, monkeypatch):
    from fitshot import learning

    model = make_model(client)
    product = make_product(client)
    job = start(client, model, product)
    run_all(ScriptedGenerator())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]

    monkeypatch.setattr(learning, "learn", lambda text, name, category: learning.Lesson(
        sleeves="short", fix="Short sleeves ending above the elbow.", watch="Are the sleeves short?"))
    response = client.post(f"/api/items/{item['id']}/feedback", json={"text": "sleeves should be short"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["status"] == "queued"
    assert body["lesson"]["lesson"]["watch"] == "Are the sleeves short?"

    lessons = learning.garment_lessons(product["id"])
    assert lessons.fixes == ["Short sleeves ending above the elbow."]
    assert lessons.watch == ["Are the sleeves short?"]
    with db.connect() as conn:
        assert db.fetch_one(conn, "SELECT sleeves FROM garment_traits WHERE product_id=?", (product["id"],))["sleeves"] == "short"

    listed = client.get(f"/api/products/{product['id']}/lessons").json()
    assert [entry["text"] for entry in listed] == ["sleeves should be short"]
    assert client.delete(f"/api/lessons/{listed[0]['id']}").status_code == 204
    assert learning.garment_lessons(product["id"]).fixes == []
    with db.connect() as conn:
        assert db.fetch_one(conn, "SELECT * FROM garment_traits WHERE product_id=?", (product["id"],)) is None


def test_without_a_key_a_note_is_kept_as_written(client):
    model = make_model(client)
    product = make_product(client)
    job = start(client, model, product)
    run_all(ScriptedGenerator())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    lesson = client.post(f"/api/items/{item['id']}/feedback", json={"text": "collar is missing", "retry": False}).json()["lesson"]
    assert lesson["lesson"]["learned_by"] == "as written"
    assert lesson["lesson"]["fix"] == "collar is missing"
    assert client.get(f"/api/jobs/{job['id']}").json()["items"][0]["status"] != "queued"


def test_a_photo_being_made_cannot_get_a_note(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    assert client.post(f"/api/items/{item['id']}/feedback", json={"text": "too early"}).status_code == 409


def test_any_finished_look_can_be_deleted(client):
    model = make_model(client)
    job = start(client, model, make_product(client))
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    assert client.delete(f"/api/items/{item['id']}").status_code == 409  # still queued

    run_all(ScriptedGenerator())
    item = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    client.post(f"/api/items/{item['id']}/review", json={"decision": "reject"})
    photo = settings.data_dir / item["url"].split("?")[0].lstrip("/")
    assert photo.exists()
    assert client.delete(f"/api/items/{item['id']}").status_code == 204
    assert not photo.exists()
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404  # its only look is gone
    assert client.get(f"/api/looks?model_id={model['id']}").json() == []


def test_a_used_up_free_quota_makes_the_look_wait_instead_of_fail(client):
    from fitshot.generators.base import QuotaWait

    class NoQuota(ScriptedGenerator):
        def dress(self, request):
            raise QuotaWait("Waiting for your free Hugging Face quota.", 3600)

    model = make_model(client)
    job = start(client, model, make_product(client))
    item = worker_module.claim_next()
    assert worker_module.process_item(item, NoQuota()) == "queued"

    waiting = client.get(f"/api/jobs/{job['id']}").json()["items"][0]
    assert waiting["status"] == "queued" and "quota" in waiting["error"]
    assert waiting["not_before"] > db.now()
    assert worker_module.claim_next() is None  # not before the hour is up

    with db.connect() as conn:
        conn.execute("UPDATE job_items SET not_before=?", ("2000-01-01T00:00:00+00:00",))
    assert worker_module.claim_next()["id"] == item["id"]
