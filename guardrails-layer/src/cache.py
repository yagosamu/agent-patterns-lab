"""A tiny sqlite cache for model responses, keyed by model plus exact payload."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from src.config import CACHE_PATH

_SCHEMA = "CREATE TABLE IF NOT EXISTS responses (k TEXT PRIMARY KEY, v TEXT)"


def _connect() -> sqlite3.Connection:
    """Open the cache database, creating the table on first use."""
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute(_SCHEMA)
    return conn


def _key(model: str, payload: Any) -> str:
    """Hash a model id and payload into a stable cache key."""
    blob = json.dumps([model, payload], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# Repeated runs exist to measure how much the model varies. Serving those
# runs from cache would report zero variance and prove nothing, so the
# evaluation harness turns reads off when it is measuring spread.
reads_enabled = True


def get(model: str, payload: Any) -> str | None:
    """Return the cached response for this call, or None."""
    if not reads_enabled:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT v FROM responses WHERE k = ?", (_key(model, payload),)
        ).fetchone()
    return row[0] if row else None


def put(model: str, payload: Any, value: str) -> None:
    """Store a response for this call."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO responses (k, v) VALUES (?, ?)",
            (_key(model, payload), value),
        )