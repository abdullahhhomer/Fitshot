"""SQLite persistence. The job_items table doubles as the work queue."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS brand_models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    reference_path TEXT NOT NULL,
    embedding TEXT NOT NULL,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'brand'
);
CREATE TABLE IF NOT EXISTS shots (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL REFERENCES brand_models(id) ON DELETE CASCADE,
    scene TEXT NOT NULL,
    pose TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    qa TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    front_path TEXT NOT NULL,
    back_path TEXT,
    logo_box TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS garment_traits (
    product_id TEXT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    sleeves TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    item_id TEXT,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    generator TEXT NOT NULL,
    text TEXT NOT NULL,
    lesson TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS ai_models (
    id TEXT PRIMARY KEY,
    path TEXT,
    status TEXT NOT NULL,
    progress REAL,
    error TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    validated_at TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    model_id TEXT NOT NULL REFERENCES brand_models(id),
    scene TEXT NOT NULL,
    generator TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id),
    shot_id TEXT NOT NULL REFERENCES shots(id),
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    output_path TEXT,
    qa TEXT,
    error TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_status ON job_items(status);
CREATE INDEX IF NOT EXISTS idx_items_job ON job_items(job_id);
CREATE TABLE IF NOT EXISTS cost_ledger (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    item_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    operation TEXT NOT NULL,
    usd REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cost_job ON cost_ledger(job_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        # Databases created before "try it on yourself" lack the model kind.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(brand_models)")}
        if "kind" not in columns:
            conn.execute("ALTER TABLE brand_models ADD COLUMN kind TEXT NOT NULL DEFAULT 'brand'")
        # Items waiting for a free quota to reset are not claimed before this time.
        item_columns = {row["name"] for row in conn.execute("PRAGMA table_info(job_items)")}
        if "not_before" not in item_columns:
            conn.execute("ALTER TABLE job_items ADD COLUMN not_before TEXT")
        # Fitting-room additions: per-generation settings, person framing, garment photo type.
        for table, column in (("jobs", "settings"), ("shots", "framing"), ("products", "photo_type")):
            if column not in {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")


def fetch_all(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def fetch_one(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def record_cost(
    provider: str,
    model: str,
    operation: str,
    usd: float,
    job_id: str | None = None,
    item_id: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO cost_ledger VALUES (?,?,?,?,?,?,?,?)",
            (new_id("cost"), job_id, item_id, provider, model, operation, usd, now()),
        )


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))
