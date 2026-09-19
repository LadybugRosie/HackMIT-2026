from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from .base import SessionRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY, server_nonce TEXT NOT NULL, genesis TEXT NOT NULL,
  created_ms INTEGER NOT NULL, doc_id TEXT, head TEXT NOT NULL,
  replay_mismatches INTEGER NOT NULL DEFAULT 0, certificate TEXT
);
CREATE TABLE IF NOT EXISTS events (
  session_id TEXT NOT NULL, seq INTEGER NOT NULL, data TEXT NOT NULL,
  PRIMARY KEY (session_id, seq)
);
CREATE TABLE IF NOT EXISTS attestations (
  session_id TEXT NOT NULL, n INTEGER NOT NULL, data TEXT NOT NULL,
  PRIMARY KEY (session_id, n)
);
CREATE TABLE IF NOT EXISTS credentials (
  credential_id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL, created_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS credentials_owner ON credentials (owner);
"""


class SqliteStore:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")  # the classroom app writes to the same file
        self._conn.executescript(_SCHEMA)
        try:  # Stage 3 column on databases created before it existed
            self._conn.execute("ALTER TABLE sessions ADD COLUMN owner TEXT")
        except sqlite3.OperationalError:
            pass
        self._lock = threading.Lock()

    def create(self, record: SessionRecord) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (session_id, server_nonce, genesis, created_ms, doc_id, head, replay_mismatches, "
                "certificate, owner) VALUES (?,?,?,?,?,?,?,?,?)",
                (record.session_id, record.server_nonce, record.genesis, record.created_ms, record.doc_id,
                 record.head, record.replay_mismatches, json.dumps(record.certificate) if record.certificate else None,
                 record.owner),
            )

    def get(self, session_id: str) -> Optional[SessionRecord]:
        row = self._conn.execute(
            "SELECT session_id, server_nonce, genesis, created_ms, doc_id, head, replay_mismatches, certificate, owner "
            "FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if row is None:
            return None
        events = [json.loads(r[0]) for r in self._conn.execute(
            "SELECT data FROM events WHERE session_id=? ORDER BY seq", (session_id,))]
        attestations = [json.loads(r[0]) for r in self._conn.execute(
            "SELECT data FROM attestations WHERE session_id=? ORDER BY n", (session_id,))]
        return SessionRecord(
            session_id=row[0], server_nonce=row[1], genesis=row[2], created_ms=row[3], doc_id=row[4],
            events=events, head=row[5], replay_mismatches=row[6],
            certificate=json.loads(row[7]) if row[7] else None, owner=row[8], attestations=attestations,
        )

    def append_events(self, session_id: str, events: List[Dict[str, Any]], head: str, replay_ok: bool) -> SessionRecord:
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO events VALUES (?,?,?)",
                [(session_id, ev["seq"], json.dumps(ev, ensure_ascii=False)) for ev in events],
            )
            self._conn.execute(
                "UPDATE sessions SET head=?, replay_mismatches=replay_mismatches+? WHERE session_id=?",
                (head, 0 if replay_ok else 1, session_id),
            )
        rec = self.get(session_id)
        assert rec is not None
        return rec

    def set_certificate(self, session_id: str, certificate: Dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE sessions SET certificate=? WHERE session_id=?",
                               (json.dumps(certificate), session_id))

    def add_attestation(self, session_id: str, attestation: Dict[str, Any]) -> None:
        with self._lock, self._conn:
            n = self._conn.execute("SELECT COALESCE(MAX(n), -1) + 1 FROM attestations WHERE session_id=?",
                                   (session_id,)).fetchone()[0]
            self._conn.execute("INSERT INTO attestations VALUES (?,?,?)", (session_id, n, json.dumps(attestation)))

    def add_credential(self, credential: Dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO credentials VALUES (?,?,?,?)",
                               (credential["credential_id"], credential["owner"], json.dumps(credential),
                                int(credential.get("created_ms", 0))))

    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("SELECT data FROM credentials WHERE credential_id=?", (credential_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_credentials(self, owner: str) -> List[Dict[str, Any]]:
        return [json.loads(r[0]) for r in self._conn.execute(
            "SELECT data FROM credentials WHERE owner=? ORDER BY created_ms", (owner,))]
