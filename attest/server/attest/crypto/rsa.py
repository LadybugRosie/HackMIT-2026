"""RSASSA-PKCS1-v1_5 signature verification (RFC 8017 §8.2.2), which is what public RFC 3161
timestamp authorities sign with. Verification is just modular exponentiation plus a byte
comparison against the expected EMSA-PKCS1-v1_5 encoding — no padding oracle concerns on the
verify side."""
from __future__ import annotations

import hashlib
from typing import Tuple

from .der import BIT_STRING, INTEGER, NULL, OID, SEQUENCE, Reader

# DigestInfo prefixes (DER of AlgorithmIdentifier + OCTET STRING header) from RFC 8017 §9.2 note 1.
_DIGEST_INFO = {
    "sha256": bytes.fromhex("3031300d060960864801650304020105000420"),
    "sha384": bytes.fromhex("3041300d060960864801650304020205000430"),
    "sha512": bytes.fromhex("3051300d060960864801650304020305000440"),
    "sha1": bytes.fromhex("3021300906052b0e03021a05000414"),
}

OID_RSA_ENCRYPTION = "1.2.840.113549.1.1.1"
OID_SIG_ALGS = {  # signatureAlgorithm OID -> hash name
    "1.2.840.113549.1.1.11": "sha256", "1.2.840.113549.1.1.12": "sha384",
    "1.2.840.113549.1.1.13": "sha512", "1.2.840.113549.1.1.5": "sha1",
}
OID_DIGEST_ALGS = {"2.16.840.1.101.3.4.2.1": "sha256", "2.16.840.1.101.3.4.2.2": "sha384",
                   "2.16.840.1.101.3.4.2.3": "sha512", "1.3.14.3.2.26": "sha1"}


def public_key_from_spki(spki: bytes) -> Tuple[int, int]:
    """SubjectPublicKeyInfo -> (n, e). Raises if not an RSA key."""
    outer = Reader(spki).read_sequence()
    alg = outer.read_sequence()
    if alg.expect(OID).oid() != OID_RSA_ENCRYPTION:
        raise ValueError("not an RSA SubjectPublicKeyInfo")
    if not alg.at_end():
        alg.expect(NULL)
    bits = outer.expect(BIT_STRING).bit_string()
    inner = Reader(bits).read_sequence()
    n = inner.read_integer()
    e = inner.read_integer()
    return n, e


def verify_pkcs1v15(pub: Tuple[int, int], hash_name: str, message: bytes, signature: bytes) -> bool:
    n, e = pub
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, "big")
    prefix = _DIGEST_INFO.get(hash_name)
    if prefix is None:
        return False
    t = prefix + hashlib.new(hash_name, message).digest()
    if len(t) + 11 > k:
        return False
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return em == expected


__all__ = ["public_key_from_spki", "verify_pkcs1v15", "OID_SIG_ALGS", "OID_DIGEST_ALGS", "INTEGER", "SEQUENCE"]
