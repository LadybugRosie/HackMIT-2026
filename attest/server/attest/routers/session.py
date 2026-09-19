import secrets
import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from ..analysis import analyze
from ..chain import genesis_hash
from ..models import IntegrityResponse, SessionStartRequest, SessionStartResponse, SessionView
from ..storage.base import SessionRecord

router = APIRouter(prefix="/v1/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
def start_session(payload: SessionStartRequest, request: Request) -> SessionStartResponse:
    session_id = str(uuid.uuid4())
    nonce = secrets.token_hex(16)
    genesis = genesis_hash(session_id, nonce)
    created_ms = int(time.time() * 1000)
    record = SessionRecord(
        session_id=session_id, server_nonce=nonce, genesis=genesis, created_ms=created_ms,
        doc_id=payload.doc_id, head=genesis,
    )
    request.app.state.store.create(record)
    return SessionStartResponse(session_id=session_id, genesis=genesis, server_nonce=nonce, created_ms=created_ms)


@router.get("/{session_id}", response_model=SessionView)
def get_session(session_id: str, request: Request) -> SessionView:
    rec = request.app.state.store.get(session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    return SessionView(
        session_id=rec.session_id, genesis=rec.genesis, created_ms=rec.created_ms,
        event_count=rec.event_count, chain_head=rec.head, replay_mismatches=rec.replay_mismatches,
        finalized=rec.certificate is not None,
    )


@router.get("/{session_id}/integrity", response_model=IntegrityResponse)
def get_integrity(session_id: str, request: Request) -> IntegrityResponse:
    rec = request.app.state.store.get(session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    return analyze(rec.events)


@router.get("/{session_id}/events")
def export_events(session_id: str, request: Request) -> dict:
    """Export the raw ledger so it can be verified offline with the standalone CLI."""
    rec = request.app.state.store.get(session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    return {"session_id": rec.session_id, "genesis": rec.genesis, "events": rec.events}
