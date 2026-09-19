from fastapi import APIRouter, Depends, HTTPException

from attest.certificate import verify_certificate
from attest.models import Certificate

from ..db import Db
from ..deps import current_user, get_db, get_store, submission_or_404
from ..playback import build_playback
from ..views import loads

router = APIRouter(prefix="/api/review", tags=["review"])


def _bound_session(store, row: dict):
    if row["ledger_session_id"] is None:
        raise HTTPException(404, "no ledger for this submission")
    rec = store.get(row["ledger_session_id"])
    if rec is None:
        raise HTTPException(404, "ledger session missing")
    return rec


@router.post("/submissions/{submission_id}/verify")
def verify_submission(submission_id: str, db: Db = Depends(get_db), store=Depends(get_store),
                      user: dict = Depends(current_user)) -> dict:
    """Re-derive the whole chain and replay against the stored text — the same checks the offline CLI runs."""
    row = submission_or_404(db, submission_id, user)
    cert = loads(row["certificate_json"])
    if cert is None:
        raise HTTPException(409, {"code": "not_submitted", "detail": "no certificate yet"})
    rec = _bound_session(store, row)
    ok, level, checks = verify_certificate(Certificate(**cert), row["content"], rec.events)
    return {"ok": ok, "assurance_level": level, "checks": [c.model_dump() for c in checks], "event_count": rec.event_count}


@router.get("/submissions/{submission_id}/playback")
def playback(submission_id: str, db: Db = Depends(get_db), store=Depends(get_store),
             user: dict = Depends(current_user)) -> dict:
    """Text events with provenance labels and pauses; kd/ku/copy are stripped after labelling."""
    row = submission_or_404(db, submission_id, user)
    rec = _bound_session(store, row)
    return build_playback(rec)


@router.get("/submissions/{submission_id}/ledger")
def download_ledger(submission_id: str, db: Db = Depends(get_db), store=Depends(get_store),
                    user: dict = Depends(current_user)) -> dict:
    """Raw ledger in the exact shape `verifier/attest_verify.py --events` expects."""
    row = submission_or_404(db, submission_id, user)
    rec = _bound_session(store, row)
    return {"session_id": rec.session_id, "genesis": rec.genesis, "events": rec.events}
