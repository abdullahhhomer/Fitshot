"""Background worker. Progress lives in SQLite, so batches resume after a restart."""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .. import db
from ..config import settings
from ..generators import GenerationError, get_generator
from ..generators.base import DressRequest, QuotaWait
from ..imaging import load_rgb, resize_to, save_rgb
from ..qa.gate import QAInput, run_qa
from ..learning import garment_lessons
from ..qa.judge import Judge, default_judge, read_sleeves
from .compose import restore_face

log = logging.getLogger(__name__)
OUTPUT_DIR = "media/outputs"


def reset_interrupted() -> int:
    with db.connect() as conn:
        cursor = conn.execute(
            "UPDATE job_items SET status='queued', updated_at=? WHERE status='running'",
            (db.now(),),
        )
        return cursor.rowcount


# ComfyUI and CatVTON share one GPU and can only make one image at a time. Cloud generators
# run elsewhere, so they get their own lane and work at the same time as the local GPU.
CLOUD_GENERATORS = ("nano_banana", "fashn_hosted")


def claim_next(cloud: bool | None = None) -> dict | None:
    """Claim the oldest queued item. cloud=True or False limits it to one lane; None takes any."""
    lane, params = "", ()
    if cloud is not None:
        marks = ",".join("?" * len(CLOUD_GENERATORS))
        lane = f" AND j.generator {'IN' if cloud else 'NOT IN'} ({marks})"
        params = CLOUD_GENERATORS
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        item = db.fetch_one(
            conn,
            f"""SELECT i.*, j.scene, j.generator, j.model_id, j.settings job_settings
               FROM job_items i JOIN jobs j ON j.id = i.job_id
               WHERE i.status='queued' AND (i.not_before IS NULL OR i.not_before <= ?){lane}
               ORDER BY j.created_at, i.rowid LIMIT 1""",
            (db.now(), *params),
        )
        if item:
            conn.execute(
                "UPDATE job_items SET status='running', updated_at=? WHERE id=?",
                (db.now(), item["id"]),
            )
        return item


def garment_sleeves(product: dict, garment: np.ndarray) -> str | None:
    """Sleeve length of a top, read once by the vision model and remembered. None if unknown."""
    if product["category"] not in ("top", "outerwear", "dress"):
        return None
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT sleeves FROM garment_traits WHERE product_id=?", (product["id"],))
    if row:
        return row["sleeves"]
    if not settings.gemini_api_key:
        return None
    try:
        sleeves = read_sleeves(settings.gemini_api_key, settings.gemini_judge_model, garment)
    except Exception as exc:  # The try-on still works without it, only less carefully.
        log.warning("Could not read the sleeve length of %s: %s", product["id"], exc)
        return None
    with db.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO garment_traits VALUES (?, ?)", (product["id"], sleeves))
    return sleeves


def _finish(item_id: str, status: str, attempts: int, path: str | None, qa: dict | None, error: str | None) -> None:
    with db.connect() as conn:
        conn.execute(
            """UPDATE job_items
               SET status=?, attempts=?, output_path=?, qa=?, error=?, updated_at=? WHERE id=?""",
            (status, attempts, path, db.dumps(qa) if qa else None, error, db.now(), item_id),
        )


def _wait_for_quota(item: dict, exc: QuotaWait) -> str:
    """Put the item back in the queue until the free quota may have reset. Any photo it has stays."""
    until = (datetime.now(timezone.utc) + timedelta(seconds=exc.wait_seconds)).isoformat(timespec="seconds")
    with db.connect() as conn:
        conn.execute(
            "UPDATE job_items SET status='queued', not_before=?, error=?, updated_at=? WHERE id=?",
            (until, str(exc), db.now(), item["id"]),
        )
    log.info("Item %s waits for quota until %s", item["id"], until)
    return "queued"


def _no_new_image(item: dict, attempts: int, message: str) -> str:
    """A failed retry must never destroy the photo the item already has."""
    if item.get("output_path"):
        qa = json.loads(item["qa"]) if item.get("qa") else None
        note = f"The retry failed, so the previous photo was kept. {message}"
        _finish(item["id"], "review", attempts, item["output_path"], qa, note)
        return "review"
    _finish(item["id"], "failed", attempts, None, None, message)
    return "failed"


def process_item(item: dict, generator=None, judge: Judge | None = None) -> str:
    with db.connect() as conn:
        product = db.fetch_one(conn, "SELECT * FROM products WHERE id=?", (item["product_id"],))
        shot = db.fetch_one(conn, "SELECT * FROM shots WHERE id=?", (item["shot_id"],))
        model = db.fetch_one(conn, "SELECT * FROM brand_models WHERE id=?", (item["model_id"],))

    generator = generator or get_generator(item["generator"])
    garment = load_rgb(product["front_path"])
    back = load_rgb(product["back_path"]) if product["back_path"] else None
    base = load_rgb(shot["path"])
    reference = load_rgb(model["reference_path"])
    centroid = np.array(json.loads(model["embedding"]), dtype=np.float32)
    logo_box = json.loads(product["logo_box"]) if product["logo_box"] else None

    sleeves = garment_sleeves(product, garment)
    # What people taught FitShot about this garment: prompt fixes now, inspector checks later.
    lessons = garment_lessons(product["id"])
    hints: list[str] = list(lessons.fixes)
    best: tuple[int, np.ndarray, dict] | None = None
    attempts = 0
    rank = {"fail": 0, "review": 1, "pass": 2}

    for attempts in range(1, settings.max_attempts + 1):
        try:
            result = generator.dress(
                DressRequest(
                    base, garment, product["category"], item["scene"], reference, back, hints,
                    keep_body=model.get("kind") == "self", sleeves=sleeves,
                    options=json.loads(item["job_settings"]) if item.get("job_settings") else {},
                )
            )
        except QuotaWait as exc:
            return _wait_for_quota(item, exc)
        except GenerationError as exc:
            if exc.retryable and attempts < settings.max_attempts:
                continue
            if best is None:
                return _no_new_image(item, attempts, str(exc))
            break

        db.record_cost(result.provider, result.model, "dress", result.usd, item["job_id"], item["id"])
        output = resize_to(result.image, base.shape[1], base.shape[0])
        output, face_restored = restore_face(output, base)
        report = run_qa(
            QAInput(
                garment, output, base, reference, centroid, product["category"], item["scene"], logo_box,
                lessons.watch,
            ),
            judge,
        )
        if report.judge_called:
            db.record_cost("gemini", settings.gemini_judge_model, "judge", settings.judge_usd_per_call, item["job_id"], item["id"])

        qa = {**report.to_dict(), "attempt": attempts, "face_restored": face_restored}
        if best is None or rank[report.status] > rank[best[2]["status"]]:
            best = (attempts, output, qa)
        if report.status == "pass":
            break
        # Review results are uncertain, so spend retries only on clear failures.
        if report.status == "review":
            break
        hints = [*lessons.fixes, *report.hints]

    if best is None:
        return _no_new_image(item, attempts, "No image was generated.")

    _, image, qa = best
    # A new name per result stops browsers from showing a cached older photo.
    path = settings.data_dir / OUTPUT_DIR / item["job_id"] / f"{item['id']}_{uuid.uuid4().hex[:8]}.png"
    save_rgb(image, path)
    status = "passed" if qa["status"] == "pass" else "review"
    _finish(item["id"], status, attempts, str(Path(path)), qa, None)
    if item.get("output_path"):
        Path(item["output_path"]).unlink(missing_ok=True)
    return status


class Worker:
    """Worker threads in two lanes. The local lane's threads take turns on the GPU but overlap
    their CPU checks with each other's GPU work; the cloud lane runs at the same time."""

    LANES = {"local": False, "cloud": True}

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._wake = {lane: threading.Event() for lane in self.LANES}
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        reset_interrupted()
        counts = {"local": settings.local_workers, "cloud": settings.cloud_workers}
        self._threads = [
            threading.Thread(target=self._run, args=(lane,), name=f"fitshot-{lane}-{n}", daemon=True)
            for lane in self.LANES
            for n in range(max(counts[lane], 1))
        ]
        for thread in self._threads:
            thread.start()

    def notify(self) -> None:
        for wake in self._wake.values():
            wake.set()

    def stop(self) -> None:
        self._stop.set()
        self.notify()
        for thread in self._threads:
            thread.join(timeout=10)

    def _run(self, lane: str) -> None:
        judge = default_judge()
        wake = self._wake[lane]
        while not self._stop.is_set():
            item = claim_next(self.LANES[lane])
            if item is None:
                wake.wait(timeout=2)
                wake.clear()
                continue
            try:
                process_item(item, judge=judge)
            except Exception as exc:
                log.exception("Item %s crashed", item["id"])
                _no_new_image(item, item["attempts"], f"{type(exc).__name__}: {exc}")


worker = Worker()
