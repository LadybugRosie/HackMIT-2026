from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .base import SessionRecord


class MemoryStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def create(self, record: SessionRecord) -> None:
        with self._lock:
            self._sessions[record.session_id] = record

    def get(self, session_id: str) -> Optional[SessionRecord]:
        return self._sessions.get(session_id)

    def append_events(self, session_id: str, events: List[Dict[str, Any]], head: str, replay_ok: bool) -> SessionRecord:
        with self._lock:
            rec = self._sessions[session_id]
            rec.events.extend(events)
            rec.head = head
            if not replay_ok:
                rec.replay_mismatches += 1
            return rec

    def set_certificate(self, session_id: str, certificate: Dict[str, Any]) -> None:
        with self._lock:
            self._sessions[session_id].certificate = certificate
