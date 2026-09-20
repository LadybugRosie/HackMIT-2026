"""Issuer signatures: the server's own seal on every certificate it issues.

Everything else in a certificate is self-consistent by construction — a student running their own
copy of this server could produce a file whose chain verifies, whose replay matches, whose device
signature checks against the key *inside the file*. The issuer signature is the one thing they
cannot forge: ECDSA-P256 by a key only this server holds, over the canonical certificate. A
verifier that knows the server's public key (README, `GET /v1/issuer`, `--issuer-key`) can tell a
certificate this classroom issued from one that merely looks like it.

    canon(cert) = JSON(cert without "issuer"; keys sorted; compact; raw UTF-8)
    issuer      = {alg: "ES256", key_id, public_key: "04…" (hex), signature: base64url(DER ECDSA over SHA256(canon))}

The key lives in a JSON file next to the database (`ATTEST_ISSUER_KEY_PATH`); an empty path
means an ephemeral key (tests). Losing the file means past certificates verify only as
"issuer unknown", never as forged — the public key is embedded in each certificate, so the
signature itself still checks; what is lost is the link to *this* server.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any, Dict, Mapping, Optional, Tuple

from .crypto import ec


def _js_stable(v: Any) -> Any:
    """Certificates round-trip through JavaScript, which has one number type: 1.0 comes back as 1.
    Normalise integral floats to ints (and drop -0.0) so the canonical bytes survive the trip."""
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else v
    if isinstance(v, dict):
        return {k: _js_stable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_js_stable(x) for x in v]
    return v


def canon_certificate(cert: Mapping[str, Any]) -> bytes:
    body = _js_stable({k: v for k, v in cert.items() if k != "issuer"})
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def key_id_for(public_key_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:16]


class Issuer:
    def __init__(self, d: int):
        self.d = d
        self.pub = ec.public_from_private(d)
        self.public_key_hex = ec.encode_uncompressed(self.pub).hex()
        self.key_id = key_id_for(self.public_key_hex)

    @classmethod
    def load_or_create(cls, path: str) -> "Issuer":
        if not path:
            return cls(ec.generate_private())
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls(int(data["d"], 16))
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        issuer = cls(ec.generate_private())
        tmp = f"{path}.{secrets.token_hex(4)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"alg": "ES256", "d": f"{issuer.d:064x}", "public_key": issuer.public_key_hex, "key_id": issuer.key_id,
                       "created_ms": int(time.time() * 1000),
                       "note": "attest issuer private key — anyone holding this can mint certificates in this server's name"}, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        return issuer

    def public_info(self) -> Dict[str, str]:
        return {"alg": "ES256", "key_id": self.key_id, "public_key": self.public_key_hex}

    def sign(self, cert: Mapping[str, Any]) -> Dict[str, Any]:
        digest = hashlib.sha256(canon_certificate(cert)).digest()
        sig = ec.sig_to_der(ec.sign(self.d, digest))
        return {**self.public_info(), "signature": _b64url(sig), "signed_ms": int(time.time() * 1000)}


def verify_issuer(cert: Mapping[str, Any], trusted_public_keys: Optional[Mapping[str, str]] = None) -> Tuple[bool, bool, Optional[bool], str]:
    """-> (present, signature_ok, trusted, detail).
    `trusted_public_keys` maps key_id -> public key hex; None means the verifier has no issuer list
    (then `trusted` is None and the caller reports the signature as self-consistent only)."""
    issuer = cert.get("issuer")
    if not issuer:
        return False, False, None, "certificate carries no issuer signature"
    try:
        pub = ec.decode_uncompressed(bytes.fromhex(issuer["public_key"]))
        sig = ec.sig_from_der(_unb64url(issuer["signature"]))
    except (KeyError, ValueError, TypeError) as exc:
        return True, False, None, f"malformed issuer signature: {exc}"
    if key_id_for(issuer["public_key"]) != issuer.get("key_id"):
        return True, False, None, "issuer key_id does not match its public key"
    ok = ec.verify_sha256(pub, canon_certificate(cert), sig)
    if not ok:
        return True, False, None, "issuer signature does not verify (certificate altered or not issued by this key)"
    if trusted_public_keys is None:
        return True, True, None, f"signed by issuer key {issuer['key_id']} (not checked against a trusted issuer list)"
    trusted = trusted_public_keys.get(issuer["key_id"]) == issuer["public_key"]
    return True, True, trusted, (f"issued by trusted key {issuer['key_id']}" if trusted
                                 else f"signed by UNKNOWN issuer key {issuer['key_id']} — not this server")
