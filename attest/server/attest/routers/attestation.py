"""Stage 3 (L2): enrol a device key and sign chain heads with it.

    GET  /v1/session/{id}/enroll/options   -> PublicKeyCredentialCreationOptions (challenge kept server-side)
    POST /v1/session/{id}/enroll           <- navigator.credentials.create() result; stores the public key
    GET  /v1/session/{id}/credentials      -> keys enrolled for this session's owner (for allowCredentials)
    POST /v1/session/{id}/attest           <- navigator.credentials.get() result over a chain head

The owner of a session (a user in the classroom, the session itself in the demo) is the only
principal whose keys count. Each accepted device signature is followed by a best-effort RFC 3161
timestamp of the same head, so the pair says "this ledger state was on this device, no later
than T".
"""
from __future__ import annotations

import secrets
import time
from typing import Any, Dict, Tuple

from fastapi import APIRouter, HTTPException, Request

from ..attestors.timestamp import request_attestation
from ..attestors.webauthn import b64url_encode, parse_registration
from ..attestors.policy import assess_attestations
from ..models import AttestationResultView, AttestRequest, AttestResponse, CredentialView, EnrollOptions, EnrollRequest
from ..settings import settings

router = APIRouter(prefix="/v1/session", tags=["attestation"])

CHALLENGE_TTL_S = 300


def _challenges(request: Request) -> Dict[str, Tuple[bytes, float]]:
    if not hasattr(request.app.state, "enroll_challenges"):
        request.app.state.enroll_challenges = {}
    return request.app.state.enroll_challenges


def _session(request: Request, session_id: str):
    rec = request.app.state.store.get(session_id)
    if rec is None:
        raise HTTPException(404, "unknown session")
    return rec


def _cfg(request: Request):
    return getattr(request.app.state, "attest_settings", settings)


@router.get("/{session_id}/enroll/options", response_model=EnrollOptions)
def enroll_options(session_id: str, request: Request) -> EnrollOptions:
    rec = _session(request, session_id)
    cfg = _cfg(request)
    owner = rec.owner or rec.session_id
    challenge = secrets.token_bytes(32)
    ch = _challenges(request)
    now = time.time()
    for k in [k for k, (_, exp) in ch.items() if exp < now]:
        del ch[k]
    ch[session_id] = (challenge, now + CHALLENGE_TTL_S)
    existing = request.app.state.store.list_credentials(owner)
    return EnrollOptions(
        challenge=b64url_encode(challenge),
        rp={"id": cfg.WEBAUTHN_RP_ID, "name": cfg.WEBAUTHN_RP_NAME},
        user={"id": b64url_encode(owner.encode("utf-8")[:64]), "name": owner[:64], "displayName": owner[:64]},
        pubKeyCredParams=[{"type": "public-key", "alg": -7}],
        authenticatorSelection={"authenticatorAttachment": "platform", "residentKey": "discouraged", "userVerification": "required"},
        excludeCredentials=[{"type": "public-key", "id": c["credential_id"]} for c in existing],
    )


@router.post("/{session_id}/enroll", response_model=CredentialView, status_code=201)
def enroll(session_id: str, payload: EnrollRequest, request: Request) -> CredentialView:
    rec = _session(request, session_id)
    cfg = _cfg(request)
    entry = _challenges(request).pop(session_id, None)
    if entry is None or entry[1] < time.time():
        raise HTTPException(409, {"code": "no_challenge", "detail": "request enrol options first (challenge expired or missing)"})
    try:
        cred = parse_registration(payload.attestation_object, payload.client_data_json, entry[0], cfg.WEBAUTHN_RP_ID, cfg.WEBAUTHN_ORIGINS)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, {"code": "bad_registration", "detail": str(exc)})
    if cred["credential_id"] != payload.id:
        raise HTTPException(400, {"code": "bad_registration", "detail": "credential id mismatch"})
    cred.update(owner=rec.owner or rec.session_id, label=payload.label, transports=payload.transports)
    request.app.state.store.add_credential(cred)
    return CredentialView(credential_id=cred["credential_id"], created_ms=cred["created_ms"], aaguid=cred["aaguid"],
                          label=cred.get("label"), uv_at_enrol=cred["uv_at_enrol"])


@router.get("/{session_id}/credentials", response_model=list[CredentialView])
def credentials(session_id: str, request: Request) -> list[CredentialView]:
    rec = _session(request, session_id)
    return [CredentialView(credential_id=c["credential_id"], created_ms=c.get("created_ms", 0), aaguid=c.get("aaguid", ""),
                           label=c.get("label"), uv_at_enrol=bool(c.get("uv_at_enrol")))
            for c in request.app.state.store.list_credentials(rec.owner or rec.session_id)]


@router.post("/{session_id}/attest", response_model=AttestResponse)
def attest(session_id: str, payload: AttestRequest, request: Request) -> AttestResponse:
    store = request.app.state.store
    rec = _session(request, session_id)
    cfg = _cfg(request)
    if rec.certificate is not None:
        raise HTTPException(409, {"code": "finalized", "detail": "session already finalized"})
    # The signed head must be a state this ledger actually passed through.
    at_count = None
    if payload.head == rec.genesis:
        at_count = 0
    else:
        for n, ev in enumerate(rec.events):
            if ev["hash"] == payload.head:
                at_count = n + 1
                break
    if at_count is None:
        raise HTTPException(409, {"code": "unknown_head", "detail": "head is not a state of this ledger", "chain_head": rec.head})
    cred = store.get_credential(payload.credential_id)
    if cred is None or cred.get("owner") != (rec.owner or rec.session_id):
        raise HTTPException(404, {"code": "unknown_credential", "detail": "no such credential enrolled for this session's owner"})

    attestors = request.app.state.attestors
    record: Dict[str, Any] = {
        "kind": "webauthn", "head": payload.head, "at_event_count": at_count, "ts": int(time.time() * 1000),
        "credential_id": payload.credential_id, "authenticator_data": payload.authenticator_data,
        "client_data_json": payload.client_data_json, "signature": payload.signature,
        "public_key": cred["public_key"], "rp_id": cfg.WEBAUTHN_RP_ID,
    }
    res = attestors["webauthn"].verify(bytes.fromhex(payload.head), record)
    if not res.ok:
        raise HTTPException(400, {"code": "bad_assertion", "detail": res.detail})
    record["uv"] = bool(res.data.get("uv"))
    record["origin"] = res.data.get("origin")
    store.add_attestation(session_id, record)
    results = [res]

    if cfg.TSA_URL:
        try:
            ts_record = request_attestation(cfg.TSA_URL, payload.head, cfg.TSA_TIMEOUT_S)
            ts_record.update(at_event_count=at_count, ts=int(time.time() * 1000))
            ts_res = attestors["timestamp"].verify(bytes.fromhex(payload.head), ts_record)
            if ts_res.ok:  # never store a token we could not verify
                store.add_attestation(session_id, ts_record)
            results.append(ts_res)
        except Exception as exc:  # network / TSA outage must not block the checkpoint
            results.append(type(res)(kind="timestamp", ok=False, level="none", detail=f"timestamp unavailable: {exc.__class__.__name__}"))

    rec = store.get(session_id)
    level, _r, _s = assess_attestations(rec.attestations, attestors, rec.head, {rec.genesis, *(e["hash"] for e in rec.events)})
    return AttestResponse(session_id=session_id, head=payload.head, at_event_count=at_count,
                          results=[AttestationResultView(**r.__dict__) for r in results],
                          attestation_count=len(rec.attestations), level_if_sealed_now=level)

