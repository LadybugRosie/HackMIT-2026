"""A software WebAuthn authenticator for tests: produces `credentials.create` / `credentials.get`
responses byte-compatible with what a browser hands back, signed with a P-256 key held in memory.
No Touch ID, no browser — lets the whole L2 path run in pytest."""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any, Dict, Optional

from attest.attestors.webauthn import b64url_encode
from attest.crypto import cbor, ec


class FakeAuthenticator:
    def __init__(self, rp_id: str = "localhost", origin: str = "http://localhost:9100"):
        self.rp_id, self.origin = rp_id, origin
        self.d = ec.generate_private()
        self.pub = ec.public_from_private(self.d)
        self.credential_id = secrets.token_bytes(16)
        self.sign_count = 0
        self.aaguid = bytes(16)

    def _auth_data(self, flags: int, attested: bool) -> bytes:
        self.sign_count += 1
        out = hashlib.sha256(self.rp_id.encode()).digest() + bytes([flags]) + self.sign_count.to_bytes(4, "big")
        if attested:
            cose = {1: 2, 3: -7, -1: 1, -2: self.pub[0].to_bytes(32, "big"), -3: self.pub[1].to_bytes(32, "big")}
            out += self.aaguid + len(self.credential_id).to_bytes(2, "big") + self.credential_id + cbor.encode(cose)
        return out

    def _client_data(self, typ: str, challenge: bytes, origin: Optional[str] = None) -> bytes:
        return json.dumps({"type": typ, "challenge": b64url_encode(challenge), "origin": origin or self.origin,
                           "crossOrigin": False}).encode()

    def create(self, challenge: bytes, uv: bool = True) -> Dict[str, Any]:
        flags = 0x01 | 0x40 | (0x04 if uv else 0)
        att_obj = cbor.encode({"fmt": "none", "attStmt": {}, "authData": self._auth_data(flags, True)})
        return {"id": b64url_encode(self.credential_id), "attestation_object": b64url_encode(att_obj),
                "client_data_json": b64url_encode(self._client_data("webauthn.create", challenge))}

    def get(self, challenge: bytes, uv: bool = True, origin: Optional[str] = None,
            tamper_signature: bool = False) -> Dict[str, Any]:
        flags = 0x01 | (0x04 if uv else 0)
        auth = self._auth_data(flags, False)
        cd = self._client_data("webauthn.get", challenge, origin)
        sig = ec.sig_to_der(ec.sign(self.d, hashlib.sha256(auth + hashlib.sha256(cd).digest()).digest()))
        if tamper_signature:
            sig = sig[:-1] + bytes([sig[-1] ^ 1])
        return {"credential_id": b64url_encode(self.credential_id), "authenticator_data": b64url_encode(auth),
                "client_data_json": b64url_encode(cd), "signature": b64url_encode(sig)}
