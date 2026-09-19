from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class SessionRecord:
    session_id: str
    server_nonce: str
    genesis: str
    created_ms: int
    doc_id: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    head: str = ""  # == genesis until the first event lands
    replay_mismatches: int = 0
    certificate: Optional[Dict[str, Any]] = None
    owner: Optional[str] = None  # who may enrol/attest: a user id (classroom) or the session id (demo)
    attestations: List[Dict[str, Any]] = field(default_factory=list)  # device signatures / timestamps over heads

    @property
    def event_count(self) -> int:
        return len(self.events)


class Store(Protocol):
    def create(self, record: SessionRecord) -> None: ...
    def get(self, session_id: str) -> Optional[SessionRecord]: ...
    def append_events(self, session_id: str, events: List[Dict[str, Any]], head: str, replay_ok: bool) -> SessionRecord: ...
    def set_certificate(self, session_id: str, certificate: Dict[str, Any]) -> None: ...
    def add_attestation(self, session_id: str, attestation: Dict[str, Any]) -> None: ...
    def add_credential(self, credential: Dict[str, Any]) -> None: ...
    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]: ...
    def list_credentials(self, owner: str) -> List[Dict[str, Any]]: ...
