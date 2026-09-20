from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from attest.chain import genesis_hash, link_hash
from attest.main import create_app
from attest.settings import Settings


def build_chain(genesis: str, raw_events: List[Dict[str, Any]], start_seq: int = 0) -> List[Dict[str, Any]]:
    """Attach seq/prev/hash to raw {ts,p,d,i,k,src?} events the way a client does."""
    out: List[Dict[str, Any]] = []
    prev = genesis
    for n, raw in enumerate(raw_events):
        ev = {"seq": start_seq + n, "ts": raw.get("ts", 1_700_000_000_000 + n), "p": raw.get("p", 0),
              "d": raw.get("d", 0), "i": raw.get("i", ""), "k": raw.get("k", "type"),
              "src": raw.get("src"), "prev": prev}
        ev["hash"] = link_hash(ev)
        out.append(ev)
        prev = ev["hash"]
    return out


def typed(text: str, start_pos: int = 0, start_ts: int = 1_700_000_000_000) -> List[Dict[str, Any]]:
    """Raw events for typing `text` one code point at a time."""
    return [{"ts": start_ts + 120 * n, "p": start_pos + n, "d": 0, "i": ch, "k": "type"}
            for n, ch in enumerate(text)]


@pytest.fixture
def genesis() -> str:
    return genesis_hash("test-session", "nonce")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(STORE="memory", ISSUER_KEY_PATH="")))
