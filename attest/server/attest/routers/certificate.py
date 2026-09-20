from fastapi import APIRouter, HTTPException, Request

from ..certificate import build_certificate
from ..models import Certificate, FinalizeRequest

router = APIRouter(prefix="/v1/session", tags=["certificate"])


@router.post("/{session_id}/finalize", response_model=Certificate)
def finalize(session_id: str, payload: FinalizeRequest, request: Request) -> Certificate:
    store = request.app.state.store
    rec = store.get(session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    if rec.certificate is not None:
        return Certificate(**rec.certificate)
    cfg = getattr(request.app.state, 'attest_settings', None)
    cert, reason = build_certificate(rec, payload.final_text, getattr(request.app.state, 'attestors', None),
                                     cfg.HID_TRUSTED_CDHASHES if cfg else (), getattr(request.app.state, 'issuer', None))
    if cert is None:
        raise HTTPException(409, {"code": "not_bound", "detail": reason})
    store.set_certificate(session_id, cert.model_dump())
    return cert


@router.get("/{session_id}/certificate", response_model=Certificate)
def get_certificate(session_id: str, request: Request) -> Certificate:
    rec = request.app.state.store.get(session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    if rec.certificate is None:
        raise HTTPException(404, "session not finalized")
    return Certificate(**rec.certificate)
