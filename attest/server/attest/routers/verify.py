from fastapi import APIRouter, Request

from ..certificate import verify_certificate
from ..models import VerifyRequest, VerifyResponse

router = APIRouter(prefix="/v1", tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest, request: Request) -> VerifyResponse:
    """Pure verification against this server's issuer key: a certificate not issued here fails `issuer`."""
    events = [e.model_dump() for e in payload.events] if payload.events is not None else None
    issuer = getattr(request.app.state, "issuer", None)
    cfg = getattr(request.app.state, "attest_settings", None)
    ok, level, checks = verify_certificate(payload.certificate, payload.text, events,
                                           cfg.HID_TRUSTED_CDHASHES if cfg else (),
                                           {issuer.key_id: issuer.public_key_hex} if issuer else None)
    return VerifyResponse(ok=ok, assurance_level=level, checks=checks)
