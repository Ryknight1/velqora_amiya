"""Table definitions and repositories (users, research jobs, briefings)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..utils.date_utils import utc_now_iso
from .connection import Database

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    request_json TEXT NOT NULL,
    entity_json TEXT NOT NULL,
    window_json TEXT,
    sources_json TEXT,
    warnings_json TEXT,
    error_json TEXT,
    briefing_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS briefings (
    id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    briefing_json TEXT,
    error_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_briefings_research ON briefings(research_id);
"""

_JSON_FIELDS = {"request_json", "entity_json", "window_json", "sources_json", "warnings_json", "error_json",
                "briefing_json"}
_RESEARCH_COLS = {"status", "stage", "progress", "message", "window_json", "sources_json", "warnings_json",
                  "error_json", "briefing_id"}
_BRIEFING_COLS = {"status", "stage", "progress", "message", "briefing_json", "error_json"}


def _decode(row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    for key in list(data):
        if key in _JSON_FIELDS:
            data[key[:-5]] = json.loads(data[key]) if data[key] else None
            del data[key]
    return data


def _encode(fields: Dict[str, Any], allowed: set) -> Dict[str, Any]:
    out = {}
    for key, value in fields.items():
        column = key if key in allowed else key + "_json"
        if column not in allowed:
            raise KeyError(f"unknown column {key}")
        out[column] = json.dumps(value) if column in _JSON_FIELDS and value is not None else value
    return out


class UserRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, user_id: str, email: str, name: Optional[str], password_hash: str) -> None:
        with self.db.connect() as c:
            c.execute("INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?,?,?,?,?)",
                      (user_id, email, name, password_hash, utc_now_iso()))

    def get_by_email(self, email: str) -> Optional[dict]:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def get(self, user_id: str) -> Optional[dict]:
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


class ResearchRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, research_id: str, user_id: Optional[str], request: dict, entity: dict, window: dict) -> None:
        now = utc_now_iso()
        with self.db.connect() as c:
            c.execute(
                "INSERT INTO research (id, user_id, status, stage, progress, message, request_json, entity_json, "
                "window_json, warnings_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (research_id, user_id, "queued", "queued", 0, "Queued…", json.dumps(request), json.dumps(entity),
                 json.dumps(window), json.dumps([]), now, now))

    def update(self, research_id: str, **fields: Any) -> None:
        cols = _encode(fields, _RESEARCH_COLS)
        cols["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{k} = ?" for k in cols)
        with self.db.connect() as c:
            c.execute(f"UPDATE research SET {assignments} WHERE id = ?", (*cols.values(), research_id))

    def get(self, research_id: str) -> Optional[dict]:
        with self.db.connect() as c:
            return _decode(c.execute("SELECT * FROM research WHERE id = ?", (research_id,)).fetchone())

    def fail_interrupted(self) -> int:
        err = json.dumps({"code": "interrupted", "message": "The server restarted while this research was running. Please run it again."})
        with self.db.connect() as c:
            cur = c.execute("UPDATE research SET status='failed', stage='failed', message=?, error_json=?, updated_at=? "
                            "WHERE status IN ('queued','running')",
                            ("Interrupted by a server restart.", err, utc_now_iso()))
            return cur.rowcount


class BriefingRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, briefing_id: str, research_id: str, user_id: Optional[str]) -> None:
        now = utc_now_iso()
        with self.db.connect() as c:
            c.execute("INSERT INTO briefings (id, research_id, user_id, status, stage, progress, message, created_at, "
                      "updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (briefing_id, research_id, user_id, "queued", "queued", 0, "Queued…", now, now))

    def update(self, briefing_id: str, **fields: Any) -> None:
        cols = _encode(fields, _BRIEFING_COLS)
        cols["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{k} = ?" for k in cols)
        with self.db.connect() as c:
            c.execute(f"UPDATE briefings SET {assignments} WHERE id = ?", (*cols.values(), briefing_id))

    def get(self, briefing_id: str) -> Optional[dict]:
        with self.db.connect() as c:
            return _decode(c.execute("SELECT * FROM briefings WHERE id = ?", (briefing_id,)).fetchone())

    def latest_for_research(self, research_id: str) -> Optional[dict]:
        with self.db.connect() as c:
            return _decode(c.execute("SELECT * FROM briefings WHERE research_id = ? ORDER BY created_at DESC LIMIT 1",
                                     (research_id,)).fetchone())

    def fail_interrupted(self) -> int:
        err = json.dumps({"code": "interrupted", "message": "The server restarted while this briefing was being generated."})
        with self.db.connect() as c:
            cur = c.execute("UPDATE briefings SET status='failed', stage='failed', message=?, error_json=?, updated_at=? "
                            "WHERE status IN ('queued','running')", ("Interrupted by a server restart.", err, utc_now_iso()))
            return cur.rowcount
