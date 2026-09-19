"""WebAuthn (FIDO2) device attestation over chain heads — the L2 mechanism.

Enrollment (`navigator.credentials.create`) yields a P-256 key pair whose private half lives in
the platform authenticator (Secure Enclave / TPM / security key) and cannot be exported. At each
checkpoint the browser calls `navigator.credentials.get` with the chain head as the challenge;
the authenticator signs `authenticatorData || SHA256(clientDataJSON)` and the server checks:

  * clientDataJSON.type == "webauthn.get", .challenge == base64url(head), .origin allowed
  * authenticatorData.rpIdHash == SHA256(rp_id), UP flag set (UV recorded)
  * ECDSA-P256 signature verifies with the enrolled public key

Attestation-statement formats (packed/tpm/apple…) are *not* verified: we request `attestation:
"none"` because we do not need to prove the authenticator's make, only that the same key keeps
signing. What binds a key to a person is enrollment under their account.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from ..crypto import cbor, ec
from .base import AttestationResult

FLAG_UP, FLAG_UV, FLAG_AT, FLAG_ED = 0x01, 0x04, 0x40, 0x80
COSE_KTY_EC2, COSE_ALG_ES256, COSE_CRV_P256 = 2, -7, 1


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _client_data(client_data_b64: str, expected_type: str, challenge: bytes, origins: Optional[Iterable[str]]) -> Dict[str, Any]:
    raw = b64url_decode(client_data_b64)
    cd = json.loads(raw)
    if cd.get("type") != expected_type:
        raise ValueError(f"clientData.type is {cd.get('type')!r}, expected {expected_type!r}")
    if cd.get("challenge") != b64url_encode(challenge):
        raise ValueError("clientData.challenge does not match the chain head")
    if origins is not None and cd.get("origin") not in set(origins):
        raise ValueError(f"origin {cd.get('origin')!r} not allowed")
    return cd


def _auth_data_header(auth_data: bytes, rp_id: Optional[str]) -> Tuple[int, int]:
    if len(auth_data) < 37:
        raise ValueError("authenticatorData too short")
    if rp_id is not None and auth_data[:32] != hashlib.sha256(rp_id.encode("utf-8")).digest():
        raise ValueError("rpIdHash does not match the relying party")
    flags = auth_data[32]
    sign_count = int.from_bytes(auth_data[33:37], "big")
    if not flags & FLAG_UP:
        raise ValueError("user-presence flag not set")
    return flags, sign_count


# -- enrollment -------------------------------------------------------------------------

def parse_registration(attestation_object_b64: str, client_data_b64: str, challenge: bytes,
                       rp_id: str, origins: Iterable[str]) -> Dict[str, Any]:
    """Validate a `credentials.create` response and return the credential record to store."""
    cd = _client_data(client_data_b64, "webauthn.create", challenge, origins)
    att_obj = cbor.decode(b64url_decode(attestation_object_b64))
    auth_data: bytes = att_obj["authData"]
    flags, sign_count = _auth_data_header(auth_data, rp_id)
    if not flags & FLAG_AT:
        raise ValueError("no attested credential data")
    aaguid = auth_data[37:53].hex()
    cred_len = int.from_bytes(auth_data[53:55], "big")
    cred_id = auth_data[55:55 + cred_len]
    cose, _consumed = cbor.decode_prefix(auth_data[55 + cred_len:])
    if cose.get(1) != COSE_KTY_EC2 or cose.get(3) != COSE_ALG_ES256 or cose.get(-1) != COSE_CRV_P256:
        raise ValueError("credential is not an ES256 / P-256 key")
    x, y = int.from_bytes(cose[-2], "big"), int.from_bytes(cose[-3], "big")
    if not ec.on_curve((x, y), ec.P256):
        raise ValueError("public key is not on P-256")
    return {
        "credential_id": b64url_encode(cred_id),
        "public_key": {"crv": "P-256", "x": f"{x:064x}", "y": f"{y:064x}"},
        "aaguid": aaguid, "sign_count": sign_count, "fmt": att_obj.get("fmt", "none"),
        "uv_at_enroll": bool(flags & FLAG_UV), "origin": cd.get("origin"), "rp_id": rp_id,
        "created_ms": int(time.time() * 1000),
    }


def public_key_tuple(pk: Mapping[str, str]) -> Tuple[int, int]:
    return int(pk["x"], 16), int(pk["y"], 16)


# -- assertion ---------------------------------------------------------------------------

class WebAuthnAttestor:
    """Attestation record shape (what the browser posts and the certificate carries):
        {kind: "webauthn", head, credential_id, authenticator_data, client_data_json, signature,
         public_key: {crv,x,y}, rp_id, origin}

    `lookup(credential_id)` returns the enrolled credential (server mode, authoritative); when it
    is None the embedded `public_key` is used (offline verification of a certificate). With
    `rp_id`/`origins` None, the values recorded in the attestation are checked against
    themselves only for structure — the issuing server is where policy is enforced."""

    kind = "webauthn"

    def __init__(self, rp_id: Optional[str] = None, origins: Optional[Iterable[str]] = None,
                 lookup: Optional[Callable[[str], Optional[Mapping[str, Any]]]] = None):
        self.rp_id = rp_id
        self.origins = list(origins) if origins is not None else None
        self.lookup = lookup

    def verify(self, statement: bytes, attestation: Mapping[str, Any]) -> AttestationResult:
        cred_id = str(attestation.get("credential_id", ""))
        try:
            cred = self.lookup(cred_id) if self.lookup else None
            if self.lookup and cred is None:
                return AttestationResult(kind=self.kind, ok=False, level="none", key_id=cred_id, detail="unknown credential")
            pk = (cred or attestation).get("public_key")
            if not pk:
                raise ValueError("no public key for credential")
            pub = public_key_tuple(pk)
            rp_id = self.rp_id if self.rp_id is not None else attestation.get("rp_id")
            cd = _client_data(attestation["client_data_json"], "webauthn.get", statement, self.origins)
            auth_data = b64url_decode(attestation["authenticator_data"])
            flags, sign_count = _auth_data_header(auth_data, rp_id)
            signed = auth_data + hashlib.sha256(b64url_decode(attestation["client_data_json"])).digest()
            sig = ec.sig_from_der(b64url_decode(attestation["signature"]))
            if not ec.verify_sha256(pub, signed, sig, ec.P256):
                return AttestationResult(kind=self.kind, ok=False, level="none", key_id=cred_id, detail="signature does not verify")
        except (KeyError, ValueError, TypeError) as exc:
            return AttestationResult(kind=self.kind, ok=False, level="none", key_id=cred_id, detail=str(exc))
        uv = bool(flags & FLAG_UV)
        return AttestationResult(
            kind=self.kind, ok=True, level="L2", key_id=cred_id,
            detail=f"device signature over head {statement.hex()[:12]}… ({'user verified' if uv else 'presence only'})",
            data={"uv": uv, "sign_count": sign_count, "origin": cd.get("origin"), "rp_id": rp_id},
        )
