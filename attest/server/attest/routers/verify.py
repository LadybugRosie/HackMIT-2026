from fastapi import APIRouter

from ..certificate import verify_certificate
from ..models import VerifyRequest, VerifyResponse

router = APIRouter(prefix="/v1", tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    events = [e.model_dump() for e in payload.events] if payload.events is not None else None
    ok, level, checks = verify_certificate(payload.certificate, payload.text, events)
    return VerifyResponse(ok=ok, assurance_level=level, checks=checks)
