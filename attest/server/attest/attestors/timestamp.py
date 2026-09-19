"""RFC 3161 trusted timestamps over chain heads.

A Timestamp Authority (TSA) signs "this hash existed at time T" with its own key. We send the
chain head, keep the signed token, and can later prove — to anyone who trusts the TSA — that the
ledger stood at that head no later than T. This is what makes ledger timestamps *believable*
rather than merely *immutable*: the browser clock is the student's; the TSA clock is not.

Verification (pure, offline-capable):
  1. token.TSTInfo.messageImprint == SHA-256(statement)         (it is about *our* head)
  2. signedAttrs.messageDigest == hash(TSTInfo)                   (CMS content binding)
  3. signature over DER(signedAttrs as SET) verifies with the embedded signer certificate
  4. signer certificate SHA-256 fingerprint is in the trusted set  (pinning; no PKI walk)

The token is stored base64 so the certificate carries it verbatim.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Set, Tuple

from ..crypto import der, ec, rsa
from ..crypto.der import BIT_STRING, INTEGER, OCTET_STRING, OID, SEQUENCE, SET, TLV, Reader, find_first, parse_time
from .base import AttestationResult

OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_TST_INFO = "1.2.840.113549.1.9.16.1.4"
OID_MESSAGE_DIGEST = "1.2.840.113549.1.9.4"
OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_EC_PUBLIC_KEY = "1.2.840.10045.2.1"
OID_ECDSA = {"1.2.840.10045.4.3.2": "sha256", "1.2.840.10045.4.3.3": "sha384", "1.2.840.10045.4.3.4": "sha512"}

DEFAULT_TSA_URL = "https://freetsa.org/tsr"

# SHA-256 fingerprints of TSA signing certificates we accept out of the box. Captured from the
# live service during development; operators can extend the set through ATTEST_TSA_TRUSTED_FINGERPRINTS.
KNOWN_TSAS: Dict[str, str] = {
    "32e841a95cc1164101ffde41298ef2fc75c1c4372ef095e88a6bbd47dfb191fc": "FreeTSA (freetsa.org)",
}


# -- request ---------------------------------------------------------------------------

def build_request(digest: bytes, nonce: Optional[int] = None) -> bytes:
    """TimeStampReq { version 1, messageImprint { sha256, digest }, nonce, certReq TRUE }"""
    if len(digest) != 32:
        raise ValueError("expected a SHA-256 digest")
    imprint = der.encode_sequence(der.encode_sequence(der.encode_oid(OID_SHA256) + der.encode_null()) + der.encode_octet_string(digest))
    body = der.encode_integer(1) + imprint
    if nonce is not None:
        body += der.encode_integer(nonce)
    body += der.encode_boolean(True)
    return der.encode_sequence(body)


def fetch_token(url: str, digest: bytes, timeout_s: float = 8.0) -> bytes:
    """POST a TimeStampReq; returns the raw TimeStampResp DER. Raises on transport errors."""
    req = urllib.request.Request(url, data=build_request(digest, secrets.randbits(63)), method="POST",
                                 headers={"Content-Type": "application/timestamp-query", "User-Agent": "attest/0.1 (+hackmit)"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


# -- response parsing ------------------------------------------------------------------

@dataclass
class Token:
    status: int
    gen_time: str                 # ISO-8601 UTC
    imprint_alg: str
    imprint: bytes
    serial: int
    nonce: Optional[int]
    policy: str
    tst_info_der: bytes           # eContent bytes (what messageDigest is over)
    signed_attrs: TLV             # [0] IMPLICIT SET OF Attribute
    digest_alg: str               # hash name for messageDigest + signature
    sig_alg: str                  # OID
    signature: bytes
    signer_cert: Optional[TLV]    # matched by IssuerAndSerialNumber
    signer_subject: str
    signer_fingerprint: str       # sha256 hex of the signer cert DER

    @property
    def tsa_name(self) -> str:
        return KNOWN_TSAS.get(self.signer_fingerprint, self.signer_subject or "unknown TSA")


def _name_to_str(name: TLV) -> str:
    parts = []
    for rdn in name.children():
        for atv in rdn.children():
            oid, val = atv.children()
            short = {"2.5.4.3": "CN", "2.5.4.10": "O", "2.5.4.6": "C", "2.5.4.11": "OU"}.get(oid.oid(), oid.oid())
            try:
                parts.append(f"{short}={val.body.decode('utf-8')}")
            except UnicodeDecodeError:
                parts.append(f"{short}=<{val.body.hex()}>")
    return ", ".join(parts)


def _cert_parts(cert: TLV) -> Tuple[int, bytes, TLV, TLV]:
    """-> (serial, issuer DER, subject, spki)"""
    tbs = cert.children()[0].children()
    i = 1 if tbs[0].tag == 0xA0 else 0  # explicit version
    serial = tbs[i].integer()
    issuer = tbs[i + 2]
    subject = tbs[i + 4]
    spki = tbs[i + 5]
    return serial, issuer.raw, subject, spki


def parse_response(resp_der: bytes) -> Token:
    resp = Reader(resp_der).read_sequence()
    status_info = resp.read_sequence()
    status = status_info.read_integer()
    if status not in (0, 1):
        raise ValueError(f"TSA rejected request (PKIStatus {status})")
    content_info = resp.read_sequence()
    if content_info.expect(OID).oid() != OID_SIGNED_DATA:
        raise ValueError("timeStampToken is not CMS SignedData")
    signed_data = Reader(content_info.expect(0xA0).body).read_sequence()
    signed_data.read_integer()  # version
    signed_data.expect(SET)     # digestAlgorithms
    encap = signed_data.read_sequence()
    if encap.expect(OID).oid() != OID_TST_INFO:
        raise ValueError("encapsulated content is not TSTInfo")
    tst_info_der = Reader(encap.expect(0xA0).body).expect(OCTET_STRING).body

    certs: list[TLV] = []
    nxt = signed_data.read()
    if nxt.tag == 0xA0:  # certificates
        certs = nxt.children()
        nxt = signed_data.read()
    if nxt.tag == 0xA1:  # crls
        nxt = signed_data.read()
    if nxt.tag != SET:
        raise ValueError("missing signerInfos")
    signer = Reader(nxt.children()[0].body)
    signer.read_integer()  # version
    sid = signer.read()
    sig_issuer_serial: Optional[Tuple[bytes, int]] = None
    if sid.tag == SEQUENCE:  # IssuerAndSerialNumber
        issuer_tlv, serial_tlv = sid.children()
        sig_issuer_serial = (issuer_tlv.raw, serial_tlv.integer())
    digest_alg_oid = Reader(signer.expect(SEQUENCE).body).expect(OID).oid()
    digest_alg = rsa.OID_DIGEST_ALGS.get(digest_alg_oid)
    if digest_alg is None:
        raise ValueError(f"unsupported digest algorithm {digest_alg_oid}")
    signed_attrs = signer.expect(0xA0)
    sig_alg = Reader(signer.expect(SEQUENCE).body).expect(OID).oid()
    signature = signer.expect(OCTET_STRING).body

    signer_cert = None
    for c in certs:
        serial, issuer_raw, _subject, _spki = _cert_parts(c)
        if sig_issuer_serial and (issuer_raw, serial) == sig_issuer_serial:
            signer_cert = c
            break
    if signer_cert is None and len(certs) == 1 and sig_issuer_serial is None:
        signer_cert = certs[0]
    subject = _name_to_str(_cert_parts(signer_cert)[2]) if signer_cert else ""
    fingerprint = hashlib.sha256(signer_cert.raw).hexdigest() if signer_cert else ""

    # TSTInfo
    tst = Reader(tst_info_der).read_sequence()
    tst.read_integer()  # version
    policy = tst.expect(OID).oid()
    imprint = tst.read_sequence()
    imprint_alg = Reader(imprint.expect(SEQUENCE).body).expect(OID).oid()
    imprint_hash = imprint.expect(OCTET_STRING).body
    serial = tst.read_integer()
    gen_time = parse_time(tst.read())
    nonce = None
    for t in tst.iter():
        if t.tag == INTEGER and nonce is None and t.raw is not None:
            nonce = t.integer()
    return Token(status, gen_time, rsa.OID_DIGEST_ALGS.get(imprint_alg, imprint_alg), imprint_hash, serial, nonce, policy,
                 tst_info_der, signed_attrs, digest_alg, sig_alg, signature, signer_cert, subject, fingerprint)


def verify_token(token: Token, statement: bytes, trusted: Set[str]) -> Tuple[bool, str]:
    """Pure verification of steps 1–4 from the module docstring."""
    if token.imprint_alg != "sha256" or token.imprint != hashlib.sha256(statement).digest():
        return False, "token is not over this chain head"
    # signedAttrs must carry messageDigest == hash(eContent)
    msg_digest = None
    for attr in token.signed_attrs.children():
        oid, values = attr.children()
        if oid.oid() == OID_MESSAGE_DIGEST:
            msg_digest = values.children()[0].body
    if msg_digest != hashlib.new(token.digest_alg, token.tst_info_der).digest():
        return False, "messageDigest attribute does not match TSTInfo"
    if token.signer_cert is None:
        return False, "TSA response carries no signer certificate"
    signed_bytes = bytes([SET]) + token.signed_attrs.raw[1:]  # CMS: verify over SET OF, not [0]
    _serial, _issuer, _subject, spki = _cert_parts(token.signer_cert)
    if token.sig_alg in rsa.OID_SIG_ALGS or token.sig_alg == rsa.OID_RSA_ENCRYPTION:
        hash_name = rsa.OID_SIG_ALGS.get(token.sig_alg, token.digest_alg)
        try:
            pub = rsa.public_key_from_spki(spki.raw)
        except ValueError as exc:
            return False, f"signer key: {exc}"
        if not rsa.verify_pkcs1v15(pub, hash_name, signed_bytes, token.signature):
            return False, "TSA signature does not verify"
    elif token.sig_alg in OID_ECDSA:
        alg = Reader(spki.body).read_sequence()
        if alg.expect(OID).oid() != OID_EC_PUBLIC_KEY:
            return False, "signer key is not an EC key"
        curve = ec.CURVES_BY_OID.get(alg.expect(OID).oid())
        if curve is None:
            return False, "unsupported EC curve"
        point = find_first(spki, BIT_STRING).bit_string()
        try:
            pub = ec.decode_uncompressed(point, curve)
            sig = ec.sig_from_der(token.signature)
        except ValueError as exc:
            return False, f"signer key: {exc}"
        if not ec.verify_hashed(pub, OID_ECDSA[token.sig_alg], signed_bytes, sig, curve):
            return False, "TSA signature does not verify"
    else:
        return False, f"unsupported signature algorithm {token.sig_alg}"
    if token.signer_fingerprint not in trusted:
        return False, f"TSA certificate {token.signer_fingerprint[:16]}… is not in the trusted set"
    return True, f"{token.tsa_name} at {token.gen_time}"


# -- attestor ---------------------------------------------------------------------------

class TimestampAttestor:
    """Attestation record shape: {kind: "timestamp", head, token (b64 TimeStampResp DER)}.
    Level is L1 on purpose: a timestamp proves *when*, never *who* or *where*, so it enriches L2
    but cannot raise a certificate to it by itself."""

    kind = "timestamp"

    def __init__(self, trusted: Optional[Iterable[str]] = None):
        self.trusted: Set[str] = set(KNOWN_TSAS) | set(trusted or ())

    def verify(self, statement: bytes, attestation: Mapping[str, Any]) -> AttestationResult:
        try:
            token = parse_response(base64.b64decode(attestation["token"]))
            ok, detail = verify_token(token, statement, self.trusted)
        except (KeyError, ValueError, IndexError) as exc:
            return AttestationResult(kind=self.kind, ok=False, level="none", detail=f"malformed token: {exc}")
        return AttestationResult(kind=self.kind, ok=ok, level="L1", key_id=token.signer_fingerprint[:16], detail=detail,
                                 data={"gen_time": token.gen_time, "tsa": token.tsa_name, "serial": str(token.serial),
                                       "policy": token.policy})


def request_attestation(url: str, head_hex: str, timeout_s: float = 8.0) -> Dict[str, Any]:
    """Fetch a token for a chain head and return the attestation record to store (unverified)."""
    statement = bytes.fromhex(head_hex)
    raw = fetch_token(url, hashlib.sha256(statement).digest(), timeout_s)
    token = parse_response(raw)
    return {"kind": "timestamp", "head": head_hex, "token": base64.b64encode(raw).decode("ascii"),
            "gen_time": token.gen_time, "tsa": token.tsa_name, "tsa_fingerprint": token.signer_fingerprint,
            "tsa_url": url}
