"""SQLite access layer (stdlib only). Everything above this file talks to repositories, never to
sqlite3 directly, so swapping in PostgreSQL later only means providing the same repository interface."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False) if path == ":memory:" else None

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._memory_conn or sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 15000")
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self._memory_conn is None:
                conn.close()

    def init(self, schema_sql: str) -> None:
        with self.connect() as conn:
            if self.path != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(schema_sql)
