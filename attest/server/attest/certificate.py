"""Build and verify Proof-of-Writing certificates.

A certificate binds *what* was submitted (doc_sha256) to *how* it was produced
(chain_root / merkle_root over the event ledger). Verification is pure: it needs no
store, so the standalone verifier CLI can do exactly the same checks offline.
"""
from __future__ import annotations

import time
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from .chain import merkle_root, sha256_hex, verify_chain
from .models import Certificate, Check
from .replay import ReplayError, replay
from .storage.base import SessionRecord

LEVEL_CHAIN_VALID = "L0"
LEVEL_DOC_BOUND = "L1"


def build_certificate(session: SessionRecord, final_text: str) -> Tuple[Optional[Certificate], Optional[str]]:
    """Return (certificate, None) or (None, reason) if the ledger does not bind to final_text."""
    chain = verify_chain(session.events, session.genesis)
    if not chain.ok:
        return None, f"ledger chain invalid at event {chain.index}: {chain.error}"
    try:
        reconstructed = replay(session.events)
    except ReplayError as exc:
        return None, f"ledger does not replay: {exc}"
    if reconstructed != final_text:
        return None, "replayed ledger does not match final_text (document not bound)"

    cert = Certificate(
        session_id=session.session_id,
        doc_sha256=sha256_hex(final_text),
        doc_len=len(final_text),
        chain_root=chain.head or session.genesis,
        merkle_root=merkle_root([e["hash"] for e in session.events]),
        event_count=session.event_count,
        genesis=session.genesis,
        created_ms=int(time.time() * 1000),
        assurance_level=LEVEL_DOC_BOUND,
        claims={"replay_mismatches_during_session": session.replay_mismatches},
    )
    return cert, None


def verify_certificate(
    cert: Certificate, text: str, events: Optional[Sequence[Mapping[str, Any]]] = None
) -> Tuple[bool, str, List[Check]]:
    """Pure verification. With `events` supplied, the full ledger is re-derived and matched."""
    checks: List[Check] = []

    doc_ok = sha256_hex(text) == cert.doc_sha256
    checks.append(Check(name="doc_sha256", ok=doc_ok, detail="submitted text matches certificate" if doc_ok else "text hash mismatch"))
    len_ok = len(text) == cert.doc_len
    checks.append(Check(name="doc_len", ok=len_ok, detail=f"{len(text)} vs {cert.doc_len}"))

    if events is None:
        ok = doc_ok and len_ok
        return ok, cert.assurance_level if ok else "none", checks

    chain = verify_chain(events, cert.genesis)
    checks.append(Check(name="chain_links", ok=chain.ok, detail=chain.error or f"{len(events)} links valid"))
    root_ok = chain.ok and chain.head == cert.chain_root
    checks.append(Check(name="chain_root", ok=root_ok, detail="head matches certificate" if root_ok else "head != chain_root"))
    count_ok = len(events) == cert.event_count
    checks.append(Check(name="event_count", ok=count_ok, detail=f"{len(events)} vs {cert.event_count}"))
    mroot = merkle_root([e["hash"] for e in events]) if chain.ok else ""
    merkle_ok = mroot == cert.merkle_root
    checks.append(Check(name="merkle_root", ok=merkle_ok, detail="matches" if merkle_ok else "mismatch"))

    try:
        reconstructed = replay(events)
        replay_ok = reconstructed == text
        detail = "ledger replays to submitted text" if replay_ok else "ledger replays to different text"
    except ReplayError as exc:
        replay_ok, detail = False, str(exc)
    checks.append(Check(name="replay", ok=replay_ok, detail=detail))

    all_ok = all(c.ok for c in checks)
    level = cert.assurance_level if all_ok else (LEVEL_CHAIN_VALID if chain.ok and root_ok else "none")
    return all_ok, level, checks
