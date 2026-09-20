from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Hex64 = Field(pattern=r"^[0-9a-f]{64}$")

EventKind = Literal["type", "paste", "ckpt", "copy", "kd", "ku"]
PasteSource = Literal["int", "ext"]


class Event(BaseModel):
    """One chained edit event. Field names are short because they are hashed verbatim."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0)
    ts: int = Field(ge=0, description="epoch milliseconds")
    p: int = Field(ge=0, description="position in code points")
    d: int = Field(ge=0, description="code points deleted")
    i: str = Field(default="", description="text inserted (ckpt: full text)")
    k: EventKind
    src: Optional[PasteSource] = None
    prev: str = Hex64
    hash: str = Hex64


class SessionStartRequest(BaseModel):
    doc_id: Optional[str] = None
    client: Optional[str] = None


class SessionStartResponse(BaseModel):
    session_id: str
    genesis: str
    server_nonce: str
    created_ms: int


class IngestRequest(BaseModel):
    session_id: str
    events: List[Event] = Field(min_length=1)
    content_sha256: str = Hex64
    content_len: int = Field(ge=0)


Verdict = Literal["genuine", "review", "suspicious", "insufficient_data"]


class Signal(BaseModel):
    name: str
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    label: str
    data: Dict[str, Any] = Field(default_factory=dict)


class Scores(BaseModel):
    trust: int = Field(ge=0, le=100)
    composition: int = Field(ge=0, le=100)


class Mix(BaseModel):
    typed: float
    internal: float
    external: float


class Span(BaseModel):
    start: int
    end: int


class IntegrityWarning(BaseModel):
    severity: Literal["low", "medium", "high"]
    code: str
    reason: str


class IntegrityResponse(BaseModel):
    scores: Scores
    mix: Mix
    ext_spans: List[Span] = Field(default_factory=list)
    signals: List[Signal] = Field(default_factory=list)
    verdict: Verdict
    confidence: float
    warnings: List[IntegrityWarning] = Field(default_factory=list)
    coverage: Dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    session_id: str
    chain_head: str
    event_count: int
    replay_ok: bool
    replay_sha256: str
    replay_len: int
    integrity: Optional[IntegrityResponse] = None


class SessionView(BaseModel):
    session_id: str
    genesis: str
    created_ms: int
    event_count: int
    chain_head: str
    replay_mismatches: int
    finalized: bool
    attestation_count: int = 0


class FinalizeRequest(BaseModel):
    final_text: str


class EnrollOptions(BaseModel):
    challenge: str  # base64url
    rp: Dict[str, str]
    user: Dict[str, str]
    pubKeyCredParams: List[Dict[str, Any]]
    authenticatorSelection: Dict[str, Any]
    attestation: str = "none"
    timeout: int = 60_000
    excludeCredentials: List[Dict[str, Any]] = Field(default_factory=list)


class EnrollRequest(BaseModel):
    id: str
    attestation_object: str
    client_data_json: str
    transports: List[str] = Field(default_factory=list)
    label: Optional[str] = None


class CredentialView(BaseModel):
    credential_id: str
    created_ms: int
    type: str = "webauthn"  # webauthn | hid
    aaguid: str = ""
    label: Optional[str] = None
    uv_at_enroll: bool = False


class EnrollHidRequest(BaseModel):
    """The native witness helper's Secure Enclave key, vouched for by the owner's authenticated
    session: `signature` is ECDSA-P256 (DER, base64url) over the enrollment challenge bytes."""
    public_key: str = Field(pattern=r"^04[0-9a-f]{128}$", description="uncompressed P-256 point, hex")
    key_id: str = Field(min_length=8, max_length=64)
    cdhash: str = Field(min_length=8, max_length=128)
    key_backend: str = "secure_enclave"  # secure_enclave | software
    signature: str
    helper_version: Optional[str] = None


class HidDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kd: int = Field(ge=0)
    builtin: bool = False


class HidStatement(BaseModel):
    """One witnessed window. Field names are short because they are hashed verbatim (see attestors/hid.py)."""
    model_config = ConfigDict(extra="forbid")
    v: int = 1
    sid: str
    seg: int = Field(ge=0)
    seq: int = Field(ge=0)
    t0: int = Field(ge=0)
    t1: int = Field(ge=0)
    kd: int = Field(ge=0)
    devices: List[HidDevice] = Field(default_factory=list)
    idle_ms: int = Field(ge=0)
    cdhash: str
    anchor: Optional[Dict[str, str]] = None
    final: bool = False
    prev: str = Hex64
    hash: str = Hex64
    sig: str


class AttestHidRequest(BaseModel):
    key_id: str
    statements: List[HidStatement] = Field(min_length=1, max_length=2000)


class AttestHidResponse(BaseModel):
    session_id: str
    accepted: int
    seg: int
    seq_to: int
    final: bool
    hid: Dict[str, Any] = Field(default_factory=dict)
    level_if_sealed_now: str


class AttestRequest(BaseModel):
    head: str = Hex64
    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str


class AttestationResultView(BaseModel):
    kind: str
    ok: bool
    level: str
    key_id: str = ""
    detail: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class AttestResponse(BaseModel):
    session_id: str
    head: str
    at_event_count: int
    results: List[AttestationResultView]
    attestation_count: int
    level_if_sealed_now: str


class Certificate(BaseModel):
    version: int = 1
    session_id: str
    doc_sha256: str
    doc_len: int
    chain_root: str
    merkle_root: str
    event_count: int
    genesis: str
    created_ms: int
    assurance_level: str  # L0 chain-valid | L1 +doc-bound | L2 +device-signed | L3 +hardware-origin
    claims: Dict[str, Any] = Field(default_factory=dict)
    attestations: List[Dict[str, Any]] = Field(default_factory=list)
    issuer: Optional[Dict[str, Any]] = None  # {alg, key_id, public_key, signature} — the server's seal


class Check(BaseModel):
    name: str
    ok: bool
    detail: str = ""
    info: bool = False  # informational: reported, but does not decide the verdict


class VerifyRequest(BaseModel):
    certificate: Certificate
    text: str
    events: Optional[List[Event]] = None


class VerifyResponse(BaseModel):
    ok: bool
    assurance_level: str
    checks: List[Check]
