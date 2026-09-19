"""Stage 3 (L2): enroll a device key and sign chain heads with it.

    GET  /v1/session/{id}/enroll/options   -> PublicKeyCredentialCreationOptions (challenge kept server-side)
    POST /v1/session/{id}/enroll           <- navigator.credentials.create() result; stores the public key
    GET  /v1/session/{id}/credentials      -> keys enrolled for this session's owner (for allowCredentials)
    POST /v1/session/{id}/attest           <- navigator.credentials.get() result over a chain head
    POST /v1/session/{id}/enroll-hid       <- the native witness helper's key, signed over the enrollment challenge (L3)
    POST /v1/session/{id}/attest-hid       <- a batch of the helper's signed window statements (L3)

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

from ..attestors.hid import statement_hash, verify_statement_signature
from ..attestors.policy import assess_attestations
from ..attestors.timestamp import request_attestation
from ..attestors.webauthn import b64url_decode, b64url_encode, parse_registration
from ..crypto import ec
from ..models import (AttestationResultView, AttestHidRequest, AttestHidResponse, AttestRequest, AttestResponse, CredentialView,
                      EnrollHidRequest, EnrollOptions, EnrollRequest)
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
        excludeCredentials=[{"type": "public-key", "id": c["credential_id"]} for c in existing if c.get("type", "webauthn") == "webauthn"],
    )


@router.post("/{session_id}/enroll", response_model=CredentialView, status_code=201)
def enroll(session_id: str, payload: EnrollRequest, request: Request) -> CredentialView:
    rec = _session(request, session_id)
    cfg = _cfg(request)
    entry = _challenges(request).pop(session_id, None)
    if entry is None or entry[1] < time.time():
        raise HTTPException(409, {"code": "no_challenge", "detail": "request enroll options first (challenge expired or missing)"})
    try:
        cred = parse_registration(payload.attestation_object, payload.client_data_json, entry[0], cfg.WEBAUTHN_RP_ID, cfg.WEBAUTHN_ORIGINS)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, {"code": "bad_registration", "detail": str(exc)})
    if cred["credential_id"] != payload.id:
        raise HTTPException(400, {"code": "bad_registration", "detail": "credential id mismatch"})
    cred.update(owner=rec.owner or rec.session_id, label=payload.label, transports=payload.transports)
    request.app.state.store.add_credential(cred)
    return CredentialView(credential_id=cred["credential_id"], created_ms=cred["created_ms"], aaguid=cred["aaguid"],
                          label=cred.get("label"), uv_at_enroll=cred["uv_at_enroll"])


@router.get("/{session_id}/credentials", response_model=list[CredentialView])
def credentials(session_id: str, request: Request) -> list[CredentialView]:
    rec = _session(request, session_id)
    return [CredentialView(credential_id=c["credential_id"], created_ms=c.get("created_ms", 0), type=c.get("type", "webauthn"),
                           aaguid=c.get("aaguid", ""), label=c.get("label"), uv_at_enroll=bool(c.get("uv_at_enroll")))
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
    if cred is None or cred.get("owner") != (rec.owner or rec.session_id) or cred.get("type", "webauthn") != "webauthn":
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
    level, _r, _s = assess_attestations(rec.attestations, attestors, rec.head, {rec.genesis, *(e["hash"] for e in rec.events)},
                                        events=rec.events, trusted_cdhashes=cfg.HID_TRUSTED_CDHASHES)
    return AttestResponse(session_id=session_id, head=payload.head, at_event_count=at_count,
                          results=[AttestationResultView(**r.__dict__) for r in results],
                          attestation_count=len(rec.attestations), level_if_sealed_now=level)



# -- Stage 4 (L3): hardware witness ---------------------------------------------------------

@router.post("/{session_id}/enroll-hid", response_model=CredentialView, status_code=201)
def enroll_hid(session_id: str, payload: EnrollHidRequest, request: Request) -> CredentialView:
    """The helper never talks to this server; the browser relays its public key and a signature
    over the same single-use challenge the WebAuthn flow uses. The authenticated session (and, in
    the classroom, the bearer token) is what binds the helper key to a person."""
    rec = _session(request, session_id)
    entry = _challenges(request).pop(session_id, None)
    if entry is None or entry[1] < time.time():
        raise HTTPException(409, {"code": "no_challenge", "detail": "request enroll options first (challenge expired or missing)"})
    try:
        pub = ec.decode_uncompressed(bytes.fromhex(payload.public_key), ec.P256)
        sig = ec.sig_from_der(b64url_decode(payload.signature))
    except ValueError as exc:
        raise HTTPException(400, {"code": "bad_registration", "detail": str(exc)})
    if not ec.verify_sha256(pub, entry[0], sig, ec.P256):
        raise HTTPException(400, {"code": "bad_registration", "detail": "signature over challenge does not verify"})
    cred = {
        "credential_id": payload.key_id, "type": "hid", "owner": rec.owner or rec.session_id,
        "public_key": {"crv": "P-256", "x": f"{pub[0]:064x}", "y": f"{pub[1]:064x}"},
        "cdhash": payload.cdhash, "key_backend": payload.key_backend, "helper_version": payload.helper_version,
        "created_ms": int(time.time() * 1000), "label": "attest-hid",
    }
    request.app.state.store.add_credential(cred)
    return CredentialView(credential_id=cred["credential_id"], created_ms=cred["created_ms"], type="hid", label="attest-hid")


@router.post("/{session_id}/attest-hid", response_model=AttestHidResponse)
def attest_hid(session_id: str, payload: AttestHidRequest, request: Request) -> AttestHidResponse:
    """Accept a batch of signed window statements. Each batch must continue the stored witness
    chain for its segment; a segment's first statement must be anchored to a head this ledger
    actually passed through. The terminal statement (final=true, anchored to the current head)
    is accepted up to finalize."""
    store = request.app.state.store
    rec = _session(request, session_id)
    cfg = _cfg(request)
    if rec.certificate is not None:
        raise HTTPException(409, {"code": "finalized", "detail": "session already finalized"})
    cred = store.get_credential(payload.key_id)
    if cred is None or cred.get("owner") != (rec.owner or rec.session_id) or cred.get("type") != "hid":
        raise HTTPException(404, {"code": "unknown_credential", "detail": "no such witness key enrolled for this session's owner"})
    pub = (int(cred["public_key"]["x"], 16), int(cred["public_key"]["y"], 16))
    heads = {rec.genesis, *(e["hash"] for e in rec.events)}
    head_index = {rec.genesis: 0, **{e["hash"]: n + 1 for n, e in enumerate(rec.events)}}

    # where the stored chain currently ends, per segment
    tails: Dict[int, Dict[str, Any]] = {}
    sealed = False
    for att in rec.attestations:
        if att.get("kind") != "hid":
            continue
        for st in att.get("statements") or []:
            tails[int(st["seg"])] = st
            sealed = sealed or bool(st.get("final"))
    if sealed:
        raise HTTPException(409, {"code": "hid_sealed", "detail": "witness already emitted its terminal statement"})

    sts = [st.model_dump() for st in payload.statements]
    prev_st = None
    for st in sts:
        if st["sid"] != session_id:
            raise HTTPException(400, {"code": "bad_statement", "detail": "statement is for a different session"})
        if statement_hash(st) != st["hash"]:
            raise HTTPException(400, {"code": "bad_statement", "detail": f"statement {st['seg']}/{st['seq']} hash mismatch"})
        if not verify_statement_signature(st, pub):
            raise HTTPException(400, {"code": "bad_statement", "detail": f"statement {st['seg']}/{st['seq']} signature does not verify"})
        if st["cdhash"] != cred.get("cdhash"):
            raise HTTPException(400, {"code": "bad_statement", "detail": "statement cdhash differs from the enrolled helper build"})
        expected_prev = prev_st if prev_st is not None else tails.get(st["seg"])
        if st["seq"] == 0:
            if expected_prev is not None:
                raise HTTPException(409, {"code": "hid_chain_break", "detail": f"segment {st['seg']} already started"})
            head = (st.get("anchor") or {}).get("head")
            if head not in heads or st["prev"] != head:
                raise HTTPException(409, {"code": "unknown_head", "detail": "segment anchor is not a state of this ledger", "chain_head": rec.head})
            st["at_event_count"] = head_index[head]
        else:
            if expected_prev is None or st["seq"] != expected_prev["seq"] + 1 or st["prev"] != expected_prev["hash"] \
                    or st["t0"] != expected_prev["t1"]:
                raise HTTPException(409, {"code": "hid_chain_break", "detail": f"statement {st['seg']}/{st['seq']} does not continue the stored chain",
                                          "expected_seq": (expected_prev["seq"] + 1) if expected_prev else 0})
        if st.get("final"):
            head = (st.get("anchor") or {}).get("head")
            if head != rec.head:
                raise HTTPException(409, {"code": "unknown_head", "detail": "terminal statement must be anchored to the current chain head",
                                          "chain_head": rec.head})
            st["at_event_count"] = rec.event_count
        prev_st = st
    if any(st.get("final") for st in sts[:-1]):
        raise HTTPException(400, {"code": "bad_statement", "detail": "terminal statement must be last in its batch"})

    record: Dict[str, Any] = {"kind": "hid", "key_id": payload.key_id, "public_key": cred["public_key"], "cdhash": cred.get("cdhash"),
                              "key_backend": cred.get("key_backend"), "ts": int(time.time() * 1000), "statements": sts}
    store.add_attestation(session_id, record)
    rec = store.get(session_id)
    level, _r, summary = assess_attestations(rec.attestations, request.app.state.attestors, rec.head, heads,
                                             events=rec.events, trusted_cdhashes=cfg.HID_TRUSTED_CDHASHES)
    return AttestHidResponse(session_id=session_id, accepted=len(sts), seg=sts[-1]["seg"], seq_to=sts[-1]["seq"],
                             final=bool(sts[-1].get("final")), hid=summary.get("hid", {}), level_if_sealed_now=level)
