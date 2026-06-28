"""
eval/ui/db.py — Minimal DB query helpers for the web UI.

Supports both Postgres (DATABASE_URL env var) and SQLite (fallback).
Read-only — all writes go through ingest.py.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_PATH  = Path(__file__).parent.parent / "db" / "eval.db"


def _pg() -> bool:
    return bool(DATABASE_URL)


@contextmanager
def _conn():
    if _pg():
        import psycopg2
        import psycopg2.extras
        c = psycopg2.connect(DATABASE_URL,
                             cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield c
        finally:
            c.close()
    else:
        c = sqlite3.connect(str(SQLITE_PATH))
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()


def q(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query and return all rows as dicts."""
    with _conn() as c:
        if _pg():
            cur = c.cursor()
            # Simple ? → %s conversion. Assumes no literal '?' inside SQL string
            # values — valid for all queries in this codebase (all params are bound).
            cur.execute(sql.replace("?", "%s"), params)
            return [dict(r) for r in cur.fetchall()]
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def q1(sql: str, params: tuple = ()) -> dict | None:
    """Run a query and return the first row as a dict, or None."""
    rows = q(sql, params)
    return rows[0] if rows else None
