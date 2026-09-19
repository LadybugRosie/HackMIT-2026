"""Thin sqlite3 wrapper for the product tables. Shares the database file with attest's
`sessions` / `events` tables but never touches them directly — ledger access goes through the
attest Store so that protocol stays the only contract."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, List, Optional, Sequence

DDL = """
CREATE TABLE IF NOT EXISTS users (
  user_id       TEXT PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  name          TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('student','teacher')),
  created_ms    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_tokens (
  token_hash  TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  created_ms  INTEGER NOT NULL,
  expires_ms  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_auth_tokens_user ON auth_tokens(user_id);

CREATE TABLE IF NOT EXISTS classes (
  class_id    TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  class_code  TEXT NOT NULL UNIQUE,
  teacher_id  TEXT NOT NULL REFERENCES users(user_id),
  created_ms  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS class_members (
  class_id   TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  role       TEXT NOT NULL CHECK (role IN ('student','teacher')),
  joined_ms  INTEGER NOT NULL,
  PRIMARY KEY (class_id, user_id)
);

CREATE TABLE IF NOT EXISTS assignments (
  assignment_id TEXT PRIMARY KEY,
  class_id      TEXT NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  instructions  TEXT NOT NULL DEFAULT '',
  due_ms        INTEGER,
  points        INTEGER NOT NULL DEFAULT 100,
  published     INTEGER NOT NULL DEFAULT 1,
  settings_json TEXT NOT NULL DEFAULT '{}',
  created_ms    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_assignments_class ON assignments(class_id);

CREATE TABLE IF NOT EXISTS submissions (
  submission_id     TEXT PRIMARY KEY,
  assignment_id     TEXT NOT NULL REFERENCES assignments(assignment_id) ON DELETE CASCADE,
  student_id        TEXT NOT NULL REFERENCES users(user_id),
  content           TEXT NOT NULL DEFAULT '',
  status            TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','graded','returned')),
  ledger_session_id TEXT UNIQUE,
  certificate_json  TEXT,
  integrity_json    TEXT,
  factcheck_status  TEXT NOT NULL DEFAULT 'none' CHECK (factcheck_status IN ('none','pending','done','error','skipped')),
  factcheck_json    TEXT,
  similarity_status TEXT NOT NULL DEFAULT 'none' CHECK (similarity_status IN ('none','pending','done','error','skipped')),
  similarity_json   TEXT,
  submitted_ms      INTEGER,
  grade             REAL,
  feedback          TEXT,
  graded_ms         INTEGER,
  updated_ms        INTEGER NOT NULL,
  UNIQUE (assignment_id, student_id)
);
CREATE INDEX IF NOT EXISTS ix_submissions_assignment ON submissions(assignment_id);

CREATE TABLE IF NOT EXISTS fingerprints (
  assignment_id TEXT NOT NULL,
  submission_id TEXT NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
  hash          INTEGER NOT NULL,
  pos           INTEGER NOT NULL,
  PRIMARY KEY (submission_id, hash, pos)
);
CREATE INDEX IF NOT EXISTS ix_fp_assignment_hash ON fingerprints(assignment_id, hash);

CREATE TABLE IF NOT EXISTS factcheck_cache (
  key        TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  fetched_ms INTEGER NOT NULL
);
"""


class Db:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(DDL)
        self._lock = threading.RLock()

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def exec(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._lock, self._conn:
            return self._conn.execute(sql, params).rowcount

    def exec_many(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self._lock, self._conn:
            self._conn.executemany(sql, rows)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Several statements in one transaction, serialized against other writers in-process."""
        with self._lock, self._conn:
            yield self._conn
