from fastapi import APIRouter, HTTPException, Request

from ..analysis import analyze
from ..chain import sha256_hex, verify_chain
from ..models import IngestRequest, IngestResponse
from ..replay import ReplayError, replay
from ..settings import settings

router = APIRouter(prefix="/v1", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, request: Request) -> IngestResponse:
    store = request.app.state.store
    rec = store.get(payload.session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    if rec.certificate is not None:
        raise HTTPException(409, {"code": "finalized", "detail": "session already finalized"})
    if len(payload.events) > settings.MAX_EVENTS_PER_BATCH:
        raise HTTPException(413, "batch too large")

    events = [e.model_dump() for e in payload.events]
    for ev in events:
        if len(ev["i"]) > settings.MAX_EVENT_TEXT_CHARS:
            raise HTTPException(413, "event text too large")

    # The client committed to these hashes before sending; we re-derive every link and
    # refuse anything that does not continue exactly from our recorded head.
    chain = verify_chain(events, rec.head, start_seq=rec.event_count)
    if not chain.ok:
        raise HTTPException(
            409,
            {"code": "chain_break", "index": chain.index, "detail": chain.error,
             "expected_prev": rec.head, "expected_seq": rec.event_count},
        )

    try:
        text = replay(rec.events + events)
    except ReplayError as exc:
        raise HTTPException(409, {"code": "replay_error", "detail": str(exc)})

    replay_sha = sha256_hex(text)
    replay_ok = replay_sha == payload.content_sha256 and len(text) == payload.content_len
    rec = store.append_events(payload.session_id, events, chain.head, replay_ok)
    return IngestResponse(
        session_id=rec.session_id, chain_head=rec.head, event_count=rec.event_count,
        replay_ok=replay_ok, replay_sha256=replay_sha, replay_len=len(text),
        integrity=analyze(rec.events, text),
    )
