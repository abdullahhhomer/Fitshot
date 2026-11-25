"""FastAPI application. Handlers are sync, so FastAPI runs them in its thread pool."""
from __future__ import annotations

import csv
import hmac
import io
import json
import os
import re
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from . import db, registry
from .config import ROOT, settings
from .generators import DRESSERS, GENERATOR_NAMES, GenerationError, get_generator
from .generators.base import CATEGORIES, POSES, SCENES, ShotRequest
from .imaging import limit_side, load_rgb, save_rgb
from .pipeline.worker import worker
from .qa.body import check_identity
from .qa.perception import detect_faces, detect_poses, garment_photo_type
from .qa.perception import framing as person_framing

MEDIA = settings.data_dir / "media"
MAX_UPLOAD = 20 * 1024 * 1024
MAX_ZIP = 1024 * 1024 * 1024
MAX_ROWS = 500
ACCEPTED = ("passed", "approved")
# Reference figures from the project brief, not a market measurement.
PHOTOSHOOT_LOW, PHOTOSHOOT_HIGH = 500, 3000


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    registry.seed()
    MEDIA.mkdir(parents=True, exist_ok=True)
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="FitShot", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def access_key_gate(request, call_next):
    """With FITSHOT_ACCESS_KEY set, only people who know the key can read or change anything."""
    path = request.url.path
    if settings.fitshot_access_key and request.method != "OPTIONS" and path.startswith(("/api/", "/media/")):
        given = request.headers.get("x-fitshot-key") or request.query_params.get("key") or ""
        if not hmac.compare_digest(given.encode(), settings.fitshot_access_key.encode()):
            return JSONResponse({"detail": "This FitShot is private. Enter its access key."}, status_code=401)
    return await call_next(request)


# Added after the gate so it wraps it: refusals still carry CORS headers the browser can read.
if settings.fitshot_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip().rstrip("/") for o in settings.fitshot_cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["Content-Type", "X-FitShot-Key"],
    )


# ---------- helpers ----------

def media_url(path: str | None) -> str | None:
    if not path:
        return None
    return "/media/" + Path(path).resolve().relative_to(MEDIA.resolve()).as_posix()


def decode_image(data: bytes, label: str = "image") -> np.ndarray:
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"{label} is larger than 20 MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.width * probe.height > 40_000_000:
                raise HTTPException(413, f"{label} has too many pixels.")
            probe.verify()
        return limit_side(load_rgb(io.BytesIO(data)), 2048)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, f"{label} is not a valid image.") from exc


def store(image: np.ndarray, folder: str, prefix: str) -> str:
    # Re-encoding also strips metadata from uploaded files.
    return str(save_rgb(image, MEDIA / folder / f"{db.new_id(prefix)}.png"))


def require(conn, table: str, row_id: str) -> dict:
    row = db.fetch_one(conn, f"SELECT * FROM {table} WHERE id=?", (row_id,))
    if row is None:
        raise HTTPException(404, f"{table} record not found.")
    return row


def parse_logo_box(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        box = {k: float(v) for k, v in json.loads(raw).items()}
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(400, "logo_box must be JSON with x, y, w and h.") from exc
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x and 0 < h <= 1 - y):
        raise HTTPException(400, "logo_box values must fit inside the image.")
    return db.dumps({"x": x, "y": y, "w": w, "h": h})


def check_choice(value: str, options, label: str) -> None:
    if value not in options:
        raise HTTPException(400, f"{label} must be one of: {', '.join(options)}.")


def generator_status() -> dict:
    """Try-on models follow the registry (added, validated and ready); ComfyUI makes model photos."""
    models = {m["id"]: m for m in registry.added()}
    result = {}
    for name in DRESSERS:
        m = models.get(name)
        result[name] = {
            "ready": bool(m and m["available"]),
            "detail": (m["detail"] if m else "Not added. Add it on the Models page."),
            "dresses": True,
        }
    for name in GENERATOR_NAMES:
        if name in DRESSERS:
            continue
        try:
            ready, detail = get_generator(name).status()
        except Exception as exc:
            ready, detail = False, f"{type(exc).__name__}: {exc}"
        result[name] = {"ready": ready, "detail": detail, "dresses": name in DRESSERS}
    return result


def require_dresser(name: str):
    """An AI try-on model that is added, validated and ready. Never swapped for another one."""
    if name not in DRESSERS:
        raise HTTPException(409, "ComfyUI now only makes brand model photos. Try garments on with FASHN VTON 1.5 or CatVTON.")
    model = registry.get(name)
    if not model or not model["added"]:
        raise HTTPException(409, f"{name} is not added. Add it on the Models page.")
    if not model["available"]:
        raise HTTPException(409, f"{model['name']} is not available: {model['detail']} Choose another model.")
    return get_generator(name)


def require_generator(name: str):
    check_choice(name, GENERATOR_NAMES, "generator")
    generator = get_generator(name)
    ready, detail = generator.status()
    if not ready:
        raise HTTPException(409, f"{name} is not ready: {detail}")
    return generator


def shot_view(row: dict) -> dict:
    return {
        **{k: row[k] for k in ("id", "model_id", "scene", "pose", "status", "created_at")},
        "url": media_url(row["path"]),
        "qa": json.loads(row["qa"]) if row["qa"] else None,
    }


def model_view(row: dict, conn) -> dict:
    counts = db.fetch_all(
        conn, "SELECT scene, COUNT(*) n FROM shots WHERE model_id=? AND status='approved' GROUP BY scene", (row["id"],)
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row.get("kind") or "brand",
        "url": media_url(row["reference_path"]),
        "created_at": row["created_at"],
        "approved_shots": {c["scene"]: c["n"] for c in counts},
    }


def product_view(row: dict) -> dict:
    return {
        **{k: row[k] for k in ("id", "sku", "name", "category", "created_at")},
        "url": media_url(row["front_path"]),
        "back_url": media_url(row["back_path"]),
        "logo_box": json.loads(row["logo_box"]) if row["logo_box"] else None,
        "photo_type": row.get("photo_type"),
    }


def item_view(row: dict) -> dict:
    return {
        **{k: row[k] for k in ("id", "job_id", "product_id", "shot_id", "status", "attempts", "error", "updated_at")},
        "not_before": row.get("not_before"),
        "url": media_url(row["output_path"]),
        "qa": json.loads(row["qa"]) if row["qa"] else None,
        "sku": row.get("sku"),
        "product_name": row.get("product_name"),
        "product_url": media_url(row.get("front_path")),
        "pose": row.get("pose"),
        "shot_url": media_url(row.get("shot_path")),
        "generator": row.get("generator"),
        "scene": row.get("scene"),
        "has_logo": bool(row.get("logo_box")),
        "usd": round(row.get("usd") or 0, 4),
        "settings": json.loads(row["job_settings"]) if row.get("job_settings") else {},
        "model_id": row.get("job_model_id"),
        "person_name": row.get("person_name"),
        "person_kind": row.get("person_kind"),
        "framing": row.get("framing"),
        "created_at": row.get("job_created"),
    }


ITEM_SQL = """
SELECT i.*, p.sku, p.name product_name, p.front_path, p.logo_box, s.pose, s.path shot_path, s.framing,
       j.generator, j.scene, j.settings job_settings, j.created_at job_created, j.model_id job_model_id,
       bm.name person_name, bm.kind person_kind,
       (SELECT COALESCE(SUM(c.usd), 0) FROM cost_ledger c WHERE c.item_id = i.id) usd
FROM job_items i
JOIN products p ON p.id = i.product_id
JOIN shots s ON s.id = i.shot_id
JOIN jobs j ON j.id = i.job_id
JOIN brand_models bm ON bm.id = j.model_id
"""


def job_summary(job: dict, conn) -> dict:
    counts = {
        r["status"]: r["n"]
        for r in db.fetch_all(conn, "SELECT status, COUNT(*) n FROM job_items WHERE job_id=? GROUP BY status", (job["id"],))
    }
    spent = conn.execute("SELECT COALESCE(SUM(usd), 0) FROM cost_ledger WHERE job_id=?", (job["id"],)).fetchone()[0]
    total = sum(counts.values())
    accepted = sum(counts.get(s, 0) for s in ACCEPTED)
    active = counts.get("queued", 0) + counts.get("running", 0)
    return {
        **job,
        "counts": counts,
        "total": total,
        "accepted": accepted,
        "done": active == 0,
        "usd": round(spent, 4),
        "usd_per_accepted": round(spent / accepted, 4) if accepted else None,
    }


def create_job(
    conn,
    kind: str,
    model_id: str,
    scene: str,
    generator: str,
    product_ids: list[str],
    num_images: int,
    shot_id: str | None = None,
    job_settings: dict | None = None,
) -> str:
    if shot_id:
        # A single chosen pose, as in the fitting room.
        shots = db.fetch_all(
            conn,
            "SELECT id FROM shots WHERE id=? AND model_id=? AND scene=? AND status='approved'",
            (shot_id, model_id, scene),
        )
        if not shots:
            raise HTTPException(409, "That pose isn't an approved shot of this model in this scene.")
    else:
        shots = db.fetch_all(
            conn,
            "SELECT id FROM shots WHERE model_id=? AND scene=? AND status='approved' ORDER BY created_at, rowid LIMIT ?",
            (model_id, scene, num_images),
        )
    if not shots:
        raise HTTPException(409, f"Approve at least one {scene} shot for this model first.")
    job_id = db.new_id("job")
    conn.execute(
        "INSERT INTO jobs (id, kind, model_id, scene, generator, created_at, settings) VALUES (?,?,?,?,?,?,?)",
        (job_id, kind, model_id, scene, generator, db.now(), db.dumps(job_settings) if job_settings else None),
    )
    conn.executemany(
        "INSERT INTO job_items (id, job_id, product_id, shot_id, updated_at) VALUES (?,?,?,?,?)",
        [(db.new_id("item"), job_id, pid, s["id"], db.now()) for pid in product_ids for s in shots],
    )
    return job_id


# ---------- system ----------

@app.get("/api/status")
def status():
    return {
        "generators": generator_status(),
        "judge_ready": bool(settings.gemini_api_key),
        "default_generator": registry.default_id() or "",
        "max_attempts": settings.max_attempts,
        "scenes": list(SCENES),
        "poses": list(POSES),
        "categories": list(CATEGORIES),
    }


# ---------- AI models (the registry) ----------

class AiModelAdd(BaseModel):
    id: str
    path: str | None = Field(default=None, max_length=500)
    download: bool = False


@app.get("/api/ai-models")
def list_ai_models():
    added = registry.added()
    ids = {m["id"] for m in added}
    return {"added": added, "catalog": [registry.view(a) for a in registry.CATALOG.values() if a.id not in ids]}


@app.post("/api/ai-models", status_code=201)
def add_ai_model(body: AiModelAdd):
    adapter = registry.CATALOG.get(body.id)
    if adapter is None:
        raise HTTPException(404, "There is no such model.")
    if not adapter.supported:
        raise HTTPException(409, f"FitShot has no adapter for {adapter.name} yet, so it cannot be added.")
    if registry.get(body.id)["added"]:
        raise HTTPException(409, f"{adapter.name} is already added.")
    if body.download and not adapter.download:
        raise HTTPException(400, f"{adapter.name} cannot be downloaded from FitShot. {adapter.setup_hint}")
    if body.path and not body.download and not Path(body.path).expanduser().exists():
        candidate = ROOT / body.path
        if not candidate.exists():
            raise HTTPException(400, f"The folder {body.path} does not exist.")
    return registry.add(body.id, body.path, body.download)


@app.post("/api/ai-models/{model_id}/validate")
def validate_ai_model(model_id: str):
    if not (registry.get(model_id) or {}).get("added"):
        raise HTTPException(404, "That model is not added.")
    return registry.validate(model_id)


@app.post("/api/ai-models/{model_id}/default")
def default_ai_model(model_id: str):
    model = registry.get(model_id)
    if not (model or {}).get("added"):
        raise HTTPException(404, "That model is not added.")
    if not model["available"]:
        raise HTTPException(409, f"Only an available model can be the default. {model['detail']}")
    registry.set_default(model_id)
    return registry.get(model_id)


@app.get("/api/ai-models/{model_id}/files")
def ai_model_files(model_id: str):
    """What removing the model's files would delete: only folders this model alone uses."""
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT * FROM ai_models WHERE id=?", (model_id,))
    if row is None:
        raise HTTPException(404, "That model is not added.")
    files = registry.removable_files(registry.CATALOG[model_id], row)
    return [{"path": str(p), "bytes": registry.folder_size(p)} for p in files]


@app.delete("/api/ai-models/{model_id}")
def remove_ai_model(model_id: str, delete_files: bool = False):
    if not (registry.get(model_id) or {}).get("added"):
        raise HTTPException(404, "That model is not added.")
    busy = registry.busy_with(model_id)
    if busy:
        raise HTTPException(409, f"{busy} try-on{'s are' if busy != 1 else ' is'} still using this model. Remove it when they finish.")
    return {"deleted": registry.remove(model_id, delete_files)}


# ---------- people: built-in photos and live photos ----------

FITS = {"full": ["top", "outerwear", "bottom", "dress"], "half": ["top", "outerwear"]}


def _with_framing(conn, row: dict) -> str:
    """Framing is worked out once per photo and remembered."""
    if row.get("framing"):
        return row["framing"]
    found = person_framing(load_rgb(row["path"])) or "half"
    conn.execute("UPDATE shots SET framing=? WHERE id=?", (found, row["id"]))
    return found


def person_view(conn, row: dict) -> dict:
    found = _with_framing(conn, row)
    return {
        "shot_id": row["id"], "model_id": row["model_id"], "name": row["name"], "kind": row["kind"],
        "url": media_url(row["path"]), "scene": row["scene"], "pose": row["pose"], "framing": found,
        "fits": FITS[found], "created_at": row["created_at"],
    }


@app.get("/api/people")
def built_in_people():
    """Built-in people: approved photos of brand models. Not AI models, and not live photos."""
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """SELECT s.*, m.name, m.kind FROM shots s JOIN brand_models m ON m.id = s.model_id
               WHERE s.status='approved' AND m.kind='brand' ORDER BY m.name, s.scene, s.created_at""",
        )
        return [person_view(conn, r) for r in rows]


@app.get("/api/live-photos")
def live_photos():
    """Photos visitors uploaded of themselves, newest first, so one can be reused."""
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """SELECT s.*, m.name, m.kind FROM shots s JOIN brand_models m ON m.id = s.model_id
               WHERE s.status='approved' AND m.kind='self' ORDER BY s.created_at DESC""",
        )
        return [person_view(conn, r) for r in rows]


@app.get("/api/results")
def results(limit: int = 120):
    """Every try-on, newest first, with the model and settings it was made with."""
    with db.connect() as conn:
        rows = db.fetch_all(conn, ITEM_SQL + " ORDER BY j.created_at DESC, i.rowid DESC LIMIT ?", (max(1, min(limit, 500)),))
    return [item_view(r) for r in rows]


# ---------- brand models ----------

@app.get("/api/models")
def list_models():
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT * FROM brand_models ORDER BY created_at DESC")
        return [model_view(r, conn) for r in rows]


@app.post("/api/models", status_code=201)
def create_model(
    name: Annotated[str, Form(min_length=1, max_length=80)],
    rights_confirmed: Annotated[bool, Form()],
    reference: Annotated[UploadFile, File()],
):
    if not rights_confirmed:
        raise HTTPException(400, "Confirm the face is synthetic or used with the adult's consent.")
    image = decode_image(reference.file.read(), "Reference")
    faces = detect_faces(image)
    if len(faces) != 1:
        raise HTTPException(422, f"The reference must show exactly one face. Found {len(faces)}.")
    row_id = db.new_id("model")
    path = store(image, "references", "ref")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO brand_models (id, name, reference_path, embedding, created_at, kind) VALUES (?,?,?,?,?,'brand')",
            (row_id, name.strip(), path, db.dumps(faces[0].embedding.round(6).tolist()), db.now()),
        )
        return model_view(require(conn, "brand_models", row_id), conn)


# ---------- try it on yourself ----------

SELF_SCENE, SELF_POSE = "studio", "front"
SHOULDERS = [11, 12]
# Generators that make photos of people (the rest only dress them).
PHOTO_MAKERS = ("comfyui", "nano_banana")
# Face photo and body photo must be at least this similar to count as the same person.
SAME_PERSON = 0.35


@app.post("/api/selfies", status_code=201)
def create_selfie(
    consent: Annotated[bool, Form()],
    photo: Annotated[UploadFile | None, File()] = None,
    face: Annotated[UploadFile | None, File()] = None,
    name: Annotated[str, Form(min_length=1, max_length=80)] = "You",
    mode: Annotated[Literal["auto", "full", "half"], Form()] = "auto",
):
    """Turn the visitor's own photos into a model. Either photo is enough.

    `photo` is the body (half or full body, with or without the head): garments go onto it.
    `face` is a close-up that becomes the identity reference. With a face only, the model has
    no shot yet; the caller makes one from the face next (POST /api/models/{id}/shots).
    """
    if not consent:
        raise HTTPException(400, "Confirm these are photos of you and that you are 18 or older.")
    has_body = photo is not None and bool(photo.filename)
    has_face = face is not None and bool(face.filename)
    if not (has_body or has_face):
        raise HTTPException(422, "Add a photo of your face, your body, or both.")

    close_up = identity = None
    if has_face:
        close_up = decode_image(face.file.read(), "Your face photo")
        found = detect_faces(close_up)
        if len(found) != 1:
            raise HTTPException(
                422,
                "Your face photo must show your face, up close." if not found
                else f"Your face photo shows {len(found)} people up front. Use one with only you up front.",
            )
        identity = found[0]

    body = shot = None
    if has_body:
        body = decode_image(photo.file.read(), "Your body photo")
        body_faces = detect_faces(body)
        if len(body_faces) > 1:
            raise HTTPException(422, f"Your body photo shows {len(body_faces)} people up front. Use one with only you up front; people far behind you are fine.")
        if identity is not None and body_faces and float(np.dot(body_faces[0].embedding, identity.embedding)) < SAME_PERSON:
            raise HTTPException(422, "Your face photo and body photo look like two different people. Use two photos of yourself.")
        if identity is None and body_faces:
            identity = body_faces[0]
        people = detect_poses(body)
        if not people or float(people[0][SHOULDERS, 2].min()) < 0.5:
            raise HTTPException(422, "Use a body photo that shows at least your shoulders and chest, facing the camera.")
        framing = person_framing(body) or "half"
        if mode == "full" and framing != "full":
            raise HTTPException(
                422,
                "Full body needs you from head to feet in the photo. Step back so your feet show, or choose Half body.",
            )
    else:
        framing = None

    model_id = db.new_id("model")
    reference = store(close_up if close_up is not None else body, "references", "self")
    # A headless body photo with no face photo has no face to check; the QA gate handles that.
    embedding = identity.embedding if identity is not None else np.zeros(512, np.float32)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO brand_models (id, name, reference_path, embedding, created_at, kind) VALUES (?,?,?,?,?,'self')",
            (model_id, name.strip(), reference, db.dumps(np.asarray(embedding).round(6).tolist()), db.now()),
        )
        if body is not None:
            shot = store(body, "shots", "shot")
            qa = {"identity": {"status": "pass", "score": 1.0, "reason": "This is your own photo."}}
            conn.execute(
                "INSERT INTO shots (id, model_id, scene, pose, path, status, qa, created_at, framing) VALUES (?,?,?,?,?,'approved',?,?,?)",
                (db.new_id("shot"), model_id, SELF_SCENE, SELF_POSE, shot, db.dumps(qa), db.now(), framing),
            )
        return model_view(require(conn, "brand_models", model_id), conn)


@app.delete("/api/items/{item_id}", status_code=204)
def delete_item(item_id: str):
    """Delete one look and its photo, whatever its decision. Spending stays in the cost ledger."""
    with db.connect() as conn:
        item = require(conn, "job_items", item_id)
        if item["status"] in ("queued", "running"):
            raise HTTPException(409, "This photo is still being made. Delete it when it finishes.")
        conn.execute("DELETE FROM job_items WHERE id=?", (item_id,))
        if not db.fetch_one(conn, "SELECT 1 FROM job_items WHERE job_id=?", (item["job_id"],)):
            conn.execute("DELETE FROM jobs WHERE id=?", (item["job_id"],))
    if item["output_path"]:
        Path(item["output_path"]).unlink(missing_ok=True)
    return Response(status_code=204)


@app.delete("/api/models/{model_id}", status_code=204)
def delete_own_photo(model_id: str):
    """Remove a visitor's own photo and every look made from it. Spending stays in the cost ledger."""
    with db.connect() as conn:
        model = require(conn, "brand_models", model_id)
        if model.get("kind") != "self":
            raise HTTPException(409, "Only your own photo can be removed here.")
        busy = db.fetch_one(
            conn,
            "SELECT 1 FROM job_items i JOIN jobs j ON j.id = i.job_id WHERE j.model_id=? AND i.status IN ('queued','running')",
            (model_id,),
        )
        if busy:
            raise HTTPException(409, "A try-on with this photo is still running. Remove it when it finishes.")
        paths = [model["reference_path"]]
        paths += [r["path"] for r in db.fetch_all(conn, "SELECT path FROM shots WHERE model_id=?", (model_id,))]
        paths += [
            r["output_path"]
            for r in db.fetch_all(
                conn, "SELECT i.output_path FROM job_items i JOIN jobs j ON j.id = i.job_id WHERE j.model_id=?", (model_id,)
            )
            if r["output_path"]
        ]
        conn.execute("DELETE FROM jobs WHERE model_id=?", (model_id,))
        conn.execute("DELETE FROM brand_models WHERE id=?", (model_id,))
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
    return Response(status_code=204)


@app.get("/api/models/{model_id}/shots")
def list_shots(model_id: str):
    with db.connect() as conn:
        require(conn, "brand_models", model_id)
        rows = db.fetch_all(conn, "SELECT * FROM shots WHERE model_id=? ORDER BY created_at DESC, rowid DESC", (model_id,))
    return [shot_view(r) for r in rows]


def _save_shot(model: dict, image: np.ndarray, scene: str, pose: str) -> dict:
    faces = detect_faces(image)
    centroid = np.array(json.loads(model["embedding"]), dtype=np.float32)
    gate = check_identity(faces, centroid)
    qa = {"identity": {"status": gate.status, "score": gate.score, "reason": gate.reason}}
    row_id = db.new_id("shot")
    path = store(image, "shots", "shot")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO shots (id, model_id, scene, pose, path, status, qa, created_at) VALUES (?,?,?,?,?,'pending',?,?)",
            (row_id, model["id"], scene, pose, path, db.dumps(qa), db.now()),
        )
        return shot_view(require(conn, "shots", row_id))


class ShotCreate(BaseModel):
    scene: str
    pose: str
    generator: str = settings.default_generator


@app.post("/api/models/{model_id}/shots", status_code=201)
def generate_shot(model_id: str, body: ShotCreate):
    check_choice(body.scene, SCENES, "scene")
    check_choice(body.pose, POSES, "pose")
    if body.generator not in PHOTO_MAKERS:
        raise HTTPException(409, "Person photos are made with ComfyUI (or Nano Banana if added). Try-on models only dress people.")
    if body.generator == "nano_banana":
        require_dresser(body.generator)  # Nano Banana must be added and ready in the registry
    generator = require_generator(body.generator)
    with db.connect() as conn:
        model = require(conn, "brand_models", model_id)
    try:
        result = generator.create_shot(ShotRequest(load_rgb(model["reference_path"]), body.scene, body.pose))
    except GenerationError as exc:
        raise HTTPException(502, str(exc)) from exc
    db.record_cost(result.provider, result.model, "shot", result.usd)
    return _save_shot(model, limit_side(result.image, 2048), body.scene, body.pose)


@app.post("/api/models/{model_id}/shots/upload", status_code=201)
def upload_shot(
    model_id: str,
    scene: Annotated[str, Form()],
    pose: Annotated[str, Form()],
    image: Annotated[UploadFile, File()],
):
    check_choice(scene, SCENES, "scene")
    check_choice(pose, POSES, "pose")
    with db.connect() as conn:
        model = require(conn, "brand_models", model_id)
    return _save_shot(model, decode_image(image.file.read(), "Shot"), scene, pose)


class ShotDecision(BaseModel):
    status: Literal["approved", "rejected"]


@app.patch("/api/shots/{shot_id}")
def decide_shot(shot_id: str, body: ShotDecision):
    with db.connect() as conn:
        shot = require(conn, "shots", shot_id)
        model = require(conn, "brand_models", shot["model_id"])
    if body.status == "approved":
        faces = detect_faces(load_rgb(shot["path"]))
        if len(faces) != 1:
            raise HTTPException(422, "An approved shot must show exactly one detectable face.")
    with db.connect() as conn:
        conn.execute("UPDATE shots SET status=? WHERE id=?", (body.status, shot_id))
        approved = db.fetch_all(conn, "SELECT path FROM shots WHERE model_id=? AND status='approved'", (model["id"],))
    _refresh_centroid(model, [a["path"] for a in approved])
    with db.connect() as conn:
        return shot_view(require(conn, "shots", shot_id))


def _refresh_centroid(model: dict, shot_paths: list[str]) -> None:
    """Average the reference and approved shots into a steadier identity vector."""
    embeddings = []
    for path in [model["reference_path"], *shot_paths]:
        faces = detect_faces(load_rgb(path))
        if len(faces) == 1:
            embeddings.append(faces[0].embedding)
    if not embeddings:
        return
    centroid = np.mean(embeddings, axis=0)
    centroid /= np.linalg.norm(centroid)
    with db.connect() as conn:
        conn.execute("UPDATE brand_models SET embedding=? WHERE id=?", (db.dumps(centroid.round(6).tolist()), model["id"]))


# ---------- products ----------

@app.get("/api/products")
def list_products():
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT * FROM products ORDER BY created_at DESC")
        for row in rows:
            if not row.get("photo_type"):
                # Garments added before detection existed: detect once and remember.
                row["photo_type"] = garment_photo_type(load_rgb(row["front_path"]))
                conn.execute("UPDATE products SET photo_type=? WHERE id=?", (row["photo_type"], row["id"]))
        return [product_view(r) for r in rows]


@app.post("/api/products", status_code=201)
def create_product(
    sku: Annotated[str, Form(min_length=1, max_length=64)],
    name: Annotated[str, Form(min_length=1, max_length=120)],
    category: Annotated[str, Form()],
    front: Annotated[UploadFile, File()],
    back: Annotated[UploadFile | None, File()] = None,
    logo_box: Annotated[str | None, Form()] = None,
):
    check_choice(category, CATEGORIES, "category")
    box = parse_logo_box(logo_box)
    front_image = decode_image(front.file.read(), "Front photo")
    front_path = store(front_image, "products", "front")
    back_path = store(decode_image(back.file.read(), "Back photo"), "products", "back") if back else None
    row_id = db.new_id("prod")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO products (id, sku, name, category, front_path, back_path, logo_box, created_at, photo_type) VALUES (?,?,?,?,?,?,?,?,?)",
            (row_id, sku.strip(), name.strip(), category, front_path, back_path, box, db.now(), garment_photo_type(front_image)),
        )
        return product_view(require(conn, "products", row_id))


# ---------- jobs ----------

class JobCreate(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=MAX_ROWS)
    model_id: str
    scene: str
    generator: str = settings.default_generator
    num_images: int = Field(default=4, ge=1, le=6)
    shot_id: str | None = None
    # Model-specific settings from the Fitting Room review step, e.g. {"steps": 30, "photo_type": "model"}.
    settings: dict | None = None


def check_settings(model_id: str, values: dict | None) -> dict | None:
    """Only settings the chosen model declares, within its ranges."""
    if not values:
        return None
    adapter = registry.CATALOG[model_id]
    known = {s.key: s for s in adapter.settings}
    clean: dict = {}
    for key, value in values.items():
        if key == "photo_type":
            if value not in adapter.photo_types:
                raise HTTPException(400, f"{adapter.name} accepts these garment photo types: {', '.join(adapter.photo_types)}.")
            clean[key] = value
            continue
        if key not in known:
            raise HTTPException(400, f"{adapter.name} has no setting called {key}.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, f"{known[key].label} must be a number.") from exc
        if not known[key].minimum <= number <= known[key].maximum:
            raise HTTPException(400, f"{known[key].label} must be between {known[key].minimum:g} and {known[key].maximum:g}.")
        clean[key] = number
    return clean


def check_fit(conn, model_id: str, product: dict, shot_id: str | None) -> None:
    """The garment must suit the person photo and the chosen model."""
    adapter = registry.CATALOG[model_id]
    if product["category"] not in adapter.categories:
        raise HTTPException(409, f"{adapter.name} cannot dress {CATEGORIES[product['category']]}.")
    if shot_id:
        shot = db.fetch_one(conn, "SELECT framing FROM shots WHERE id=?", (shot_id,))
        if shot and shot.get("framing") == "half" and product["category"] in ("bottom", "dress"):
            raise HTTPException(
                409, "This photo shows the upper body only. Trousers, skirts and dresses need a full-body photo."
            )


@app.post("/api/jobs", status_code=201)
def start_job(body: JobCreate):
    check_choice(body.scene, SCENES, "scene")
    require_dresser(body.generator)
    job_settings = check_settings(body.generator, body.settings)
    product_ids = list(dict.fromkeys(body.product_ids))
    with db.connect() as conn:
        require(conn, "brand_models", body.model_id)
        for product_id in product_ids:
            check_fit(conn, body.generator, require(conn, "products", product_id), body.shot_id)
        job_id = create_job(
            conn, "single", body.model_id, body.scene, body.generator, product_ids, body.num_images, body.shot_id,
            job_settings,
        )
        summary = job_summary(require(conn, "jobs", job_id), conn)
    worker.notify()
    return summary


def _read_bulk_rows(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "The CSV must be UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower() for f in reader.fieldnames or []}
    missing = {"sku", "name", "category", "image"} - fields
    if missing:
        raise HTTPException(400, f"CSV is missing columns: {', '.join(sorted(missing))}.")
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in reader]
    if not rows:
        raise HTTPException(400, "The CSV has no products.")
    if len(rows) > MAX_ROWS:
        raise HTTPException(400, f"The CSV can contain at most {MAX_ROWS} products.")
    return rows


def _zip_index(archive: zipfile.ZipFile) -> dict[str, list[zipfile.ZipInfo]]:
    total, index = 0, {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        if info.file_size > MAX_UPLOAD:
            raise HTTPException(413, f"{info.filename} is larger than 20 MB.")
        total += info.file_size
        if total > MAX_ZIP:
            raise HTTPException(413, "The ZIP expands to more than 1 GB.")
        index.setdefault(PurePosixPath(info.filename.replace("\\", "/")).name.lower(), []).append(info)
    return index


def _zip_image(archive, index, name: str, line: int) -> np.ndarray:
    matches = index.get(PurePosixPath(name.replace("\\", "/")).name.lower(), [])
    if len(matches) != 1:
        problem = "was not found" if not matches else "matches several files"
        raise HTTPException(400, f"CSV line {line}: image '{name}' {problem} in the ZIP.")
    return decode_image(archive.read(matches[0]), f"CSV line {line} image")


@app.post("/api/jobs/bulk", status_code=201)
def start_bulk_job(
    model_id: Annotated[str, Form()],
    scene: Annotated[str, Form()],
    csv_file: Annotated[UploadFile, File()],
    images_zip: Annotated[UploadFile, File()],
    generator: Annotated[str, Form()] = settings.default_generator,
    num_images: Annotated[int, Form(ge=1, le=6)] = 4,
):
    check_choice(scene, SCENES, "scene")
    require_dresser(generator)
    with db.connect() as conn:
        require(conn, "brand_models", model_id)
        has_shots = conn.execute(
            "SELECT 1 FROM shots WHERE model_id=? AND scene=? AND status='approved' LIMIT 1", (model_id, scene)
        ).fetchone()
    if not has_shots:
        raise HTTPException(409, f"Approve at least one {scene} shot for this model first.")

    rows = _read_bulk_rows(csv_file.file.read())
    try:
        archive = zipfile.ZipFile(images_zip.file)
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "The images file is not a valid ZIP.") from exc

    # Validate every row before saving anything, so a bad CSV leaves no partial batch.
    prepared = []
    with archive:
        index = _zip_index(archive)
        for line, row in enumerate(rows, start=2):
            if not row.get("sku") or not row.get("name"):
                raise HTTPException(400, f"CSV line {line}: sku and name are required.")
            if row.get("category") not in CATEGORIES:
                raise HTTPException(400, f"CSV line {line}: category must be one of {', '.join(CATEGORIES)}.")
            front = _zip_image(archive, index, row.get("image", ""), line)
            back = _zip_image(archive, index, row["back_image"], line) if row.get("back_image") else None
            prepared.append((row, front, back))

    product_rows = []
    for row, front, back in prepared:
        product_rows.append(
            (
                db.new_id("prod"), row["sku"][:64], row["name"][:120], row["category"],
                store(front, "products", "front"),
                store(back, "products", "back") if back is not None else None,
                None, db.now(),
            )
        )
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO products (id, sku, name, category, front_path, back_path, logo_box, created_at) VALUES (?,?,?,?,?,?,?,?)",
            product_rows,
        )
        job_id = create_job(conn, "bulk", model_id, scene, generator, [p[0] for p in product_rows], num_images)
        summary = job_summary(require(conn, "jobs", job_id), conn)
    worker.notify()
    return summary


@app.get("/api/jobs")
def list_jobs():
    with db.connect() as conn:
        return [job_summary(j, conn) for j in db.fetch_all(conn, "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC")]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with db.connect() as conn:
        summary = job_summary(require(conn, "jobs", job_id), conn)
        items = db.fetch_all(conn, ITEM_SQL + " WHERE i.job_id=? ORDER BY p.sku, i.rowid", (job_id,))
    return {**summary, "items": [item_view(i) for i in items]}


@app.get("/api/looks")
def looks(model_id: str, scene: str | None = None):
    """Every photo made of one brand model, newest first, for the fitting room."""
    sql = ITEM_SQL + " WHERE j.model_id=?"
    params: list = [model_id]
    if scene:
        check_choice(scene, SCENES, "scene")
        sql += " AND j.scene=?"
        params.append(scene)
    with db.connect() as conn:
        require(conn, "brand_models", model_id)
        items = db.fetch_all(conn, sql + " ORDER BY i.updated_at DESC, i.rowid DESC LIMIT 200", tuple(params))
    return [item_view(i) for i in items]


@app.get("/api/review")
def review_queue():
    with db.connect() as conn:
        items = db.fetch_all(conn, ITEM_SQL + " WHERE i.status='review' ORDER BY i.updated_at")
    return [item_view(i) for i in items]


class ItemDecision(BaseModel):
    decision: Literal["approve", "reject"]


@app.post("/api/items/{item_id}/review")
def review_item(item_id: str, body: ItemDecision):
    status_value = "approved" if body.decision == "approve" else "rejected"
    with db.connect() as conn:
        item = require(conn, "job_items", item_id)
        if item["status"] != "review":
            raise HTTPException(409, "Only items waiting for review can be decided.")
        conn.execute("UPDATE job_items SET status=?, updated_at=? WHERE id=?", (status_value, db.now(), item_id))
        row = db.fetch_one(conn, ITEM_SQL + " WHERE i.id=?", (item_id,))
    return item_view(row)


@app.post("/api/items/{item_id}/reopen")
def reopen_item(item_id: str):
    """Undo a person's approve or reject decision."""
    with db.connect() as conn:
        item = require(conn, "job_items", item_id)
        if item["status"] not in ("approved", "rejected") or not item["output_path"]:
            raise HTTPException(409, "Only approved or rejected photos can be reopened.")
        conn.execute("UPDATE job_items SET status='review', updated_at=? WHERE id=?", (db.now(), item_id))
        row = db.fetch_one(conn, ITEM_SQL + " WHERE i.id=?", (item_id,))
    return item_view(row)


@app.post("/api/items/{item_id}/retry")
def retry_item(item_id: str):
    with db.connect() as conn:
        item = require(conn, "job_items", item_id)
        job = require(conn, "jobs", item["job_id"])
    if item["status"] not in ("review", "rejected", "failed"):
        raise HTTPException(409, "Only review, rejected or failed items can be retried.")
    require_dresser(job["generator"])
    with db.connect() as conn:
        # The current photo stays until a replacement has been generated.
        conn.execute(
            "UPDATE job_items SET status='queued', attempts=0, error=NULL, not_before=NULL, updated_at=? WHERE id=?",
            (db.now(), item_id),
        )
        row = db.fetch_one(conn, ITEM_SQL + " WHERE i.id=?", (item_id,))
    worker.notify()
    return item_view(row)


class FeedbackIn(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    retry: bool = True


def lesson_view(row: dict) -> dict:
    return {"id": row["id"], "text": row["text"], "lesson": json.loads(row["lesson"]), "created_at": row["created_at"],
            "generator": row["generator"]}


@app.post("/api/items/{item_id}/feedback")
def give_feedback(item_id: str, body: FeedbackIn):
    """Write what is wrong; FitShot learns it for this garment and, by default, tries again."""
    from .learning import learn

    with db.connect() as conn:
        item = require(conn, "job_items", item_id)
        job = require(conn, "jobs", item["job_id"])
        product = require(conn, "products", item["product_id"])
    if item["status"] in ("queued", "running"):
        raise HTTPException(409, "This photo is still being made. Write your note when it is ready.")
    if body.retry:
        require_dresser(job["generator"])
    lesson = learn(body.text.strip(), product["name"], product["category"])
    with db.connect() as conn:
        feedback_id = db.new_id("fb")
        conn.execute(
            "INSERT INTO feedback VALUES (?,?,?,?,?,?,?)",
            (feedback_id, item_id, product["id"], job["generator"], body.text.strip(), lesson.model_dump_json(), db.now()),
        )
        if lesson.sleeves:
            # The person knows the garment better than the automatic sleeve reading.
            conn.execute("INSERT OR REPLACE INTO garment_traits VALUES (?, ?)", (product["id"], lesson.sleeves))
        if body.retry:
            conn.execute(
                "UPDATE job_items SET status='queued', attempts=0, error=NULL, not_before=NULL, updated_at=? WHERE id=?",
                (db.now(), item_id),
            )
        row = db.fetch_one(conn, ITEM_SQL + " WHERE i.id=?", (item_id,))
        saved = db.fetch_one(conn, "SELECT * FROM feedback WHERE id=?", (feedback_id,))
    if body.retry:
        worker.notify()
    return {"item": item_view(row), "lesson": lesson_view(saved)}


@app.get("/api/products/{product_id}/lessons")
def product_lessons(product_id: str):
    with db.connect() as conn:
        require(conn, "products", product_id)
        rows = db.fetch_all(conn, "SELECT * FROM feedback WHERE product_id=? ORDER BY created_at DESC", (product_id,))
    return [lesson_view(r) for r in rows]


@app.delete("/api/lessons/{lesson_id}", status_code=204)
def forget_lesson(lesson_id: str):
    """Remove a lesson that turned out to be wrong. A corrected sleeve length is read again next time."""
    with db.connect() as conn:
        row = require(conn, "feedback", lesson_id)
        conn.execute("DELETE FROM feedback WHERE id=?", (lesson_id,))
        if json.loads(row["lesson"]).get("sleeves"):
            conn.execute("DELETE FROM garment_traits WHERE product_id=?", (row["product_id"],))
    return Response(status_code=204)


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "item"


def _csv_cell(value) -> str:
    """Stop spreadsheet apps from running a cell as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@app.get("/api/jobs/{job_id}/export")
def export_job(job_id: str):
    with db.connect() as conn:
        job = require(conn, "jobs", job_id)
        items = db.fetch_all(
            conn,
            ITEM_SQL + " WHERE i.job_id=? AND i.status IN ('passed','approved') ORDER BY p.sku, i.rowid",
            (job_id,),
        )
    if not items:
        raise HTTPException(409, "This job has no accepted images to export.")

    handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=settings.data_dir)
    handle.close()
    report = io.StringIO()
    writer = csv.writer(report)
    writer.writerow(["file", "sku", "product", "scene", "pose", "status", "attempts", "usd", "ai_generated"])
    used: set[str] = set()
    with zipfile.ZipFile(handle.name, "w", zipfile.ZIP_STORED) as archive:
        for item in items:
            stem = f"{_safe_name(item['sku'])}_{job['scene']}_{item['pose']}"
            name, n = f"{stem}.png", 2
            while name in used:
                name, n = f"{stem}_{n}.png", n + 1
            used.add(name)
            archive.write(item["output_path"], f"images/{name}")
            writer.writerow(
                [name, _csv_cell(item["sku"]), _csv_cell(item["product_name"]), job["scene"], item["pose"],
                 item["status"], item["attempts"], round(item["usd"], 4), "yes"]
            )
        archive.writestr("results.csv", report.getvalue())
    return FileResponse(
        handle.name,
        media_type="application/zip",
        filename=f"fitshot_{job_id}.zip",
        background=BackgroundTask(os.unlink, handle.name),
    )


# ---------- costs ----------

@app.get("/api/costs")
def costs():
    with db.connect() as conn:
        total = conn.execute("SELECT COALESCE(SUM(usd), 0) FROM cost_ledger").fetchone()[0]
        accepted = conn.execute("SELECT COUNT(*) FROM job_items WHERE status IN ('passed','approved')").fetchone()[0]
        by_operation = db.fetch_all(
            conn, "SELECT operation, COUNT(*) calls, ROUND(SUM(usd), 4) usd FROM cost_ledger GROUP BY operation ORDER BY usd DESC"
        )
        by_product = db.fetch_all(
            conn,
            """SELECT p.id, p.sku, p.name,
                      COUNT(DISTINCT CASE WHEN i.status IN ('passed','approved') THEN i.id END) accepted,
                      ROUND(COALESCE(SUM(c.usd), 0), 4) usd
               FROM products p
               JOIN job_items i ON i.product_id = p.id
               LEFT JOIN cost_ledger c ON c.item_id = i.id
               GROUP BY p.id ORDER BY usd DESC""",
        )
        products = len(by_product)
    return {
        "total_usd": round(total, 4),
        "accepted_images": accepted,
        "usd_per_accepted": round(total / accepted, 4) if accepted else None,
        "products": products,
        "usd_per_product": round(total / products, 4) if products else None,
        "by_operation": by_operation,
        "by_product": by_product,
        "photoshoot_reference": {"low": PHOTOSHOOT_LOW, "high": PHOTOSHOOT_HIGH, "source": "project brief estimate"},
    }


# ---------- static files ----------

MEDIA.mkdir(parents=True, exist_ok=True)
# Only the media folder is public. The database stays outside it.
app.mount("/media", StaticFiles(directory=MEDIA), name="media")

_dist = ROOT / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
