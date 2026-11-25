"""The AI model registry: which try-on models FitShot knows, which are added, and which are usable.

Three ideas stay separate in FitShot:
1. AI inference models (this file): FASHN VTON 1.5, CatVTON, Nano Banana, later Leffa.
2. Built-in people: approved photos of brand models (the `shots` table).
3. Live photos: a visitor's own uploads (models of kind 'self').

CATALOG says what each adapter can do; the `ai_models` table records which are added, where
their files are and whether they passed validation. A model is offered in the Fitting Room
only when it is added, validated and ready right now. Nothing falls back to another model.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from . import db
from .config import ROOT, settings

log = logging.getLogger(__name__)
PROJECT = ROOT  # the FitShot folder


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    minimum: float
    maximum: float
    step: float
    default: float
    help: str


@dataclass(frozen=True)
class Adapter:
    id: str  # also the generator name the worker runs
    name: str
    version: str
    description: str
    categories: tuple[str, ...]  # FitShot garment categories it can dress
    person_modes: tuple[str, ...]  # "full", "half"
    photo_types: tuple[str, ...]  # garment photo types it understands: "flat-lay", "model"
    hardware: str
    limitations: str
    location: str  # "local" or "online"
    license: str
    default_path: str | None = None  # relative to the FitShot folder, for local files
    files: tuple[str, ...] = ()  # files that must exist under the path
    exclusive_paths: tuple[str, ...] = ()  # extra folders only this model uses (deleted on request)
    size_gb: float = 0.0
    download: bool = False  # FitShot can download the weights itself
    setup_hint: str = ""
    settings: tuple[Setting, ...] = ()
    supported: bool = True


CATALOG: dict[str, Adapter] = {
    a.id: a
    for a in (
        Adapter(
            id="fashn", name="FASHN VTON 1.5 (this PC)", version="1.5",
            description="Maskless virtual try-on that finds the body and the garment itself. The most realistic model FitShot has tested.",
            categories=("top", "outerwear", "bottom", "dress"), person_modes=("full", "half"), photo_types=("flat-lay", "model"),
            hardware="NVIDIA GPU with 8 GB. Measured on an RTX 5060 Laptop GPU: about 3 GB for the model, about 60 s per image.",
            limitations="576x864 output (FitShot keeps your original photo outside the clothes). A jacket over a top can come out open.",
            location="local", license="Apache-2.0", default_path="fashn/weights",
            files=("model.safetensors", "dwpose/yolox_l.onnx", "dwpose/dw-ll_ucoco_384.onnx"),
            exclusive_paths=("fashn/hf-cache",), size_gb=2.4, download=True,
            setup_hint="Needs the FASHN service: run-fashn.cmd (start-all.cmd starts it).",
            settings=(
                Setting("steps", "Quality steps", 10, 50, 5, 30, "20 is faster, 30 balanced, 50 best."),
                Setting("guidance", "Garment guidance", 1.0, 3.0, 0.1, 1.5, "How strictly it follows the garment photo."),
            ),
        ),
        Adapter(
            id="fashn_hosted", name="FASHN VTON 1.5 (Hugging Face)", version="1.5",
            description="The same FASHN model running on a Hugging Face Space. Nothing to install, no GPU needed.",
            categories=("top", "outerwear", "bottom", "dress"), person_modes=("full", "half"), photo_types=("flat-lay", "model"),
            hardware="None on this PC. Needs HF_TOKEN; a free account gets about 9 images a day.",
            limitations="Photos are sent to the Hugging Face Space. When the free quota is used up, looks wait for it to reset.",
            location="online", license="Apache-2.0 (Space run by others)",
            setup_hint="Add HF_TOKEN (a Hugging Face read token) to the .env file.",
            settings=(
                Setting("steps", "Quality steps", 10, 50, 5, 30, "20 is faster, 30 balanced, 50 best."),
                Setting("guidance", "Garment guidance", 1.0, 3.0, 0.1, 1.5, "How strictly it follows the garment photo."),
            ),
        ),
        Adapter(
            id="catvton", name="CatVTON", version="mix-48k-1024",
            description="Mask-based try-on. Changes only the clothing area FitShot marks; works offline.",
            categories=("top", "outerwear", "bottom", "dress"), person_modes=("full", "half"), photo_types=("flat-lay",),
            hardware="NVIDIA GPU with 8 GB; up to 7 GB with the bare-arms pass.",
            limitations="Colors and stripes can fade; dresses often fail. Works best with flat-lay garment photos.",
            location="local", license="CC BY-NC-SA 4.0 (non-commercial)", default_path="catvton/weights",
            files=("catvton",), size_gb=1.8,
            setup_hint="Install with scripts/setup_catvton.sh and run run-catvton.cmd.",
            settings=(
                Setting("steps", "Quality steps", 10, 60, 5, 30, "More steps are slower and a little cleaner."),
                Setting("guidance", "Garment guidance", 1.0, 7.0, 0.5, 2.5, "How strictly it follows the garment photo."),
            ),
        ),
        Adapter(
            id="nano_banana", name="Nano Banana", version=settings.gemini_image_model,
            description="Google's image model through the Gemini API, prompted to change only the clothing.",
            categories=("top", "outerwear", "bottom", "dress"), person_modes=("full", "half"), photo_types=("flat-lay", "model"),
            hardware="None on this PC. Needs GEMINI_API_KEY with billing (the free tier has no image quota).",
            limitations="Paid per image. Photos are sent to Google.",
            location="online", license="Google terms",
            setup_hint="Needs a Gemini key with image quota.",
        ),
        Adapter(
            id="leffa", name="Leffa", version="not integrated yet",
            description="Flow-field try-on model. Listed so it can be added once FitShot has an adapter for it.",
            categories=("top", "bottom", "dress"), person_modes=("full", "half"), photo_types=("flat-lay",),
            hardware="NVIDIA GPU; requirements not measured.", limitations="No adapter yet.",
            location="local", license="Check before use", supported=False,
        ),
    )
}


# ---------- registry table ----------

def _row(conn, model_id: str) -> dict | None:
    return db.fetch_one(conn, "SELECT * FROM ai_models WHERE id=?", (model_id,))


def _path(adapter: Adapter, row: dict | None) -> Path | None:
    raw = (row or {}).get("path") or adapter.default_path
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else PROJECT / path


def files_present(adapter: Adapter, path: Path | None) -> bool:
    if not adapter.files:
        return True
    return path is not None and all((path / f).exists() for f in adapter.files)


def seed() -> None:
    """On first run only, register the models that are already installed or configured.
    Later, a model the person removed stays removed."""
    with db.connect() as conn:
        if db.fetch_one(conn, "SELECT 1 FROM app_meta WHERE key='ai_models_seeded'"):
            return
        conn.execute("INSERT OR REPLACE INTO app_meta VALUES ('ai_models_seeded', ?)", (db.now(),))
        found = []
        for adapter in CATALOG.values():
            if not adapter.supported:
                continue
            if adapter.location == "local" and files_present(adapter, _path(adapter, None)):
                found.append(adapter.id)
            elif adapter.id == "fashn_hosted" and settings.hf_token:
                found.append(adapter.id)
        default = next((m for m in ("fashn", "catvton", "fashn_hosted") if m in found), found[0] if found else None)
        for model_id in found:
            conn.execute(
                "INSERT INTO ai_models (id, path, status, is_default, added_at) VALUES (?,?,?,?,?)",
                (model_id, CATALOG[model_id].default_path, "installed", int(model_id == default), db.now()),
            )


def runtime(adapter: Adapter, row: dict) -> tuple[str, str]:
    """(status, detail). Status is downloading, error, unavailable or ready."""
    from .generators import get_generator

    if row["status"] == "downloading":
        return "downloading", row.get("error") or "Downloading the model files."
    if row["status"] == "error":
        return "error", row.get("error") or "The model could not be installed."
    if not files_present(adapter, _path(adapter, row)):
        return "unavailable", f"Model files are missing in {_path(adapter, row)}."
    try:
        ready, detail = get_generator(adapter.id).status()
    except Exception as exc:  # A broken adapter is unavailable, never an error page.
        ready, detail = False, f"{type(exc).__name__}: {exc}"
    if not ready:
        return "unavailable", detail
    return "ready", detail


def view(adapter: Adapter, row: dict | None = None, live: bool = True) -> dict:
    data = asdict(adapter)
    data["settings"] = [asdict(s) for s in adapter.settings]
    data["added"] = row is not None
    if row is None:
        return {**data, "status": "not added", "detail": "", "is_default": False, "validated": False, "path": adapter.default_path}
    status, detail = runtime(adapter, row) if live else (row["status"], row.get("error") or "")
    if status == "ready" and not row.get("validated_at"):
        # First time it is seen working: that is its validation.
        _mark_validated(adapter.id)
        row = {**row, "validated_at": db.now()}
    return {
        **data,
        "status": status,
        "detail": detail,
        "progress": row.get("progress"),
        "is_default": bool(row["is_default"]),
        "validated": bool(row.get("validated_at")),
        "available": status == "ready" and bool(row.get("validated_at")),
        "path": row.get("path"),
        "added_at": row["added_at"],
    }


def _mark_validated(model_id: str) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE ai_models SET validated_at=?, status='installed', error=NULL WHERE id=?", (db.now(), model_id))


def added() -> list[dict]:
    seed()
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT * FROM ai_models ORDER BY is_default DESC, added_at")
    return [view(CATALOG[r["id"]], r) for r in rows if r["id"] in CATALOG]


def available_ids() -> list[str]:
    return [m["id"] for m in added() if m["available"]]


def default_id() -> str | None:
    models = added()
    chosen = next((m for m in models if m["is_default"] and m["available"]), None)
    return chosen["id"] if chosen else None


def get(model_id: str) -> dict | None:
    seed()
    adapter = CATALOG.get(model_id)
    if adapter is None:
        return None
    with db.connect() as conn:
        row = _row(conn, model_id)
    return view(adapter, row)


def add(model_id: str, path: str | None, download: bool) -> dict:
    """Register a model. Downloading runs in the background; poll get() for progress."""
    adapter = CATALOG[model_id]
    with db.connect() as conn:
        is_first = not db.fetch_one(conn, "SELECT 1 FROM ai_models LIMIT 1")
        conn.execute(
            "INSERT OR REPLACE INTO ai_models (id, path, status, progress, error, is_default, added_at, validated_at) VALUES (?,?,?,?,?,?,?,NULL)",
            (model_id, path or adapter.default_path, "downloading" if download else "installed", 0.0 if download else None,
             None, int(is_first), db.now()),
        )
    if download:
        threading.Thread(target=_download, args=(adapter, _path(adapter, {"path": path})), daemon=True).start()
    return validate(model_id) if not download else get(model_id)


def validate(model_id: str) -> dict:
    """Check the files and that the model can run now. Only a passing model becomes available."""
    adapter = CATALOG[model_id]
    with db.connect() as conn:
        row = _row(conn, model_id)
    status, detail = runtime(adapter, row)
    with db.connect() as conn:
        if status == "ready":
            conn.execute("UPDATE ai_models SET validated_at=?, status='installed', error=NULL WHERE id=?", (db.now(), model_id))
        elif status in ("unavailable", "error"):
            conn.execute("UPDATE ai_models SET validated_at=NULL, error=? WHERE id=?", (detail, model_id))
    return get(model_id)


def set_default(model_id: str) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE ai_models SET is_default = (id = ?)", (model_id,))


def busy_with(model_id: str) -> int:
    with db.connect() as conn:
        row = db.fetch_one(
            conn,
            "SELECT COUNT(*) n FROM job_items i JOIN jobs j ON j.id=i.job_id WHERE j.generator=? AND i.status IN ('queued','running')",
            (model_id,),
        )
    return int(row["n"])


def removable_files(adapter: Adapter, row: dict) -> list[Path]:
    """Folders that belong to this model alone, inside the FitShot folder. Shared Python
    environments, ComfyUI and other models' folders are never listed."""
    candidates = [_path(adapter, row)] + [PROJECT / p for p in adapter.exclusive_paths]
    project = PROJECT.resolve()
    safe = []
    for path in candidates:
        if path is None or not path.exists():
            continue
        resolved = path.resolve()
        if resolved == project or project not in resolved.parents:
            continue  # never outside the project, never the project itself
        if resolved.name in (".venv", "comfyui", "backend", "frontend", "services"):
            continue
        safe.append(resolved)
    return safe


def folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def remove(model_id: str, delete_files: bool) -> list[str]:
    adapter = CATALOG[model_id]
    with db.connect() as conn:
        row = _row(conn, model_id)
        was_default = bool(row and row["is_default"])
        conn.execute("DELETE FROM ai_models WHERE id=?", (model_id,))
        if was_default:
            # Another added model becomes the default, so the Fitting Room always has one.
            nxt = db.fetch_one(conn, "SELECT id FROM ai_models ORDER BY added_at LIMIT 1")
            if nxt:
                conn.execute("UPDATE ai_models SET is_default=1 WHERE id=?", (nxt["id"],))
    deleted = []
    if delete_files and row:
        for path in removable_files(adapter, row):
            shutil.rmtree(path, ignore_errors=True)
            deleted.append(str(path))
    return deleted


# ---------- downloading ----------

def _download(adapter: Adapter, path: Path) -> None:
    """Download weights with the model's own script, reporting progress by folder size."""
    def fail(message: str) -> None:
        with db.connect() as conn:
            conn.execute("UPDATE ai_models SET status='error', error=? WHERE id=?", (message, adapter.id))

    if adapter.id != "fashn":
        return fail(f"{adapter.name} cannot be downloaded from FitShot. {adapter.setup_hint}")
    python = PROJECT / "catvton" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    script = PROJECT / "fashn" / "fashn-vton-1.5" / "scripts" / "download_weights.py"
    if not python.exists() or not script.exists():
        return fail("The FASHN code is not set up yet. Run scripts/setup_fashn.sh once, which also downloads the weights.")
    path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HF_HOME": str(PROJECT / "fashn" / "hf-cache"), "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(
        [str(python), str(script), "--weights-dir", str(path)], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    )
    total = adapter.size_gb * 2**30
    while process.poll() is None:
        try:
            done = folder_size(path)
        except OSError:
            done = 0
        with db.connect() as conn:
            conn.execute(
                "UPDATE ai_models SET progress=?, error=? WHERE id=?",
                (min(done / total, 0.99), f"Downloading: {done / 2**30:.1f} of about {adapter.size_gb:.1f} GB", adapter.id),
            )
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    output = (process.stdout.read() if process.stdout else "")[-400:]
    if not files_present(adapter, path):
        return fail(f"The download did not finish. {output.strip()}")
    with db.connect() as conn:
        conn.execute("UPDATE ai_models SET status='installed', progress=1.0, error=NULL WHERE id=?", (adapter.id,))
    validate(adapter.id)
    log.info("Downloaded %s to %s (%s)", adapter.id, path, sys.platform)
