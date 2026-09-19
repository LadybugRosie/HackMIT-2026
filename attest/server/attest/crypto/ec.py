"""ECDSA over NIST prime curves (P-256 for WebAuthn/Secure Enclave keys, P-384 for some
timestamp authorities), pure Python.

Only `verify` is security-relevant here; `sign` exists so tests can act as a fake authenticator.
Jacobian coordinates keep a P-256 verify around 5 ms. Parameters are from FIPS 186-4 / SEC 2.
Signatures are (r, s) integers; helpers convert from the DER form WebAuthn returns.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional, Tuple

Point = Optional[Tuple[int, int]]  # None is the point at infinity
_Jac = Tuple[int, int, int]


@dataclass(frozen=True)
class Curve:
    name: str
    oid: str
    p: int
    a: int
    b: int
    n: int
    gx: int
    gy: int

    @property
    def size(self) -> int:  # bytes per coordinate
        return (self.p.bit_length() + 7) // 8


P256 = Curve(
    "P-256", "1.2.840.10045.3.1.7",
    p=0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF,
    a=0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC,
    b=0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B,
    n=0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551,
    gx=0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    gy=0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)
P384 = Curve(
    "P-384", "1.3.132.0.34",
    p=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFF,
    a=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFC,
    b=0xB3312FA7E23EE7E4988E056BE3F82D19181D9C6EFE8141120314088F5013875AC656398D8A2ED19D2A85C8EDD3EC2AEF,
    n=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF581A0DB248B0A77AECEC196ACCC52973,
    gx=0xAA87CA22BE8B05378EB1C71EF320AD746E1D3B628BA79B9859F741E082542A385502F25DBF55296C3A545E3872760AB7,
    gy=0x3617DE4A96262C6F5D9E98BF9292DC29F8F41DBD289A147CE9DA3113B5F0B8C00A60B1CE1D7E819D7A431D7C90EA0E5F,
)
CURVES_BY_OID = {c.oid: c for c in (P256, P384)}


def _to_jac(pt: Point) -> _Jac:
    return (pt[0], pt[1], 1) if pt else (0, 1, 0)


def _from_jac(c: Curve, j: _Jac) -> Point:
    x, y, z = j
    if z == 0:
        return None
    zi = pow(z, -1, c.p)
    zi2 = zi * zi % c.p
    return (x * zi2 % c.p, y * zi2 * zi % c.p)


def _jac_double(c: Curve, j: _Jac) -> _Jac:
    x, y, z = j
    if z == 0 or y == 0:
        return (0, 1, 0)
    p = c.p
    ysq = y * y % p
    s = 4 * x * ysq % p
    m = (3 * x * x + c.a * pow(z, 4, p)) % p
    nx = (m * m - 2 * s) % p
    ny = (m * (s - nx) - 8 * ysq * ysq) % p
    return (nx, ny, 2 * y * z % p)


def _jac_add(c: Curve, a: _Jac, b: _Jac) -> _Jac:
    if a[2] == 0:
        return b
    if b[2] == 0:
        return a
    p = c.p
    x1, y1, z1 = a
    x2, y2, z2 = b
    z1z1, z2z2 = z1 * z1 % p, z2 * z2 % p
    u1, u2 = x1 * z2z2 % p, x2 * z1z1 % p
    s1, s2 = y1 * z2 * z2z2 % p, y2 * z1 * z1z1 % p
    if u1 == u2:
        return _jac_double(c, a) if s1 == s2 else (0, 1, 0)
    h = (u2 - u1) % p
    r = (s2 - s1) % p
    h2 = h * h % p
    h3 = h2 * h % p
    u1h2 = u1 * h2 % p
    nx = (r * r - h3 - 2 * u1h2) % p
    ny = (r * (u1h2 - nx) - s1 * h3) % p
    return (nx, ny, h * z1 * z2 % p)


def _mul(c: Curve, k: int, pt: Point) -> Point:
    acc: _Jac = (0, 1, 0)
    base = _to_jac(pt)
    while k:
        if k & 1:
            acc = _jac_add(c, acc, base)
        base = _jac_double(c, base)
        k >>= 1
    return _from_jac(c, acc)


def on_curve(pt: Point, c: Curve = P256) -> bool:
    if pt is None:
        return False
    x, y = pt
    return 0 <= x < c.p and 0 <= y < c.p and (y * y - (x * x * x + c.a * x + c.b)) % c.p == 0


# -- keys ------------------------------------------------------------------------------

def public_from_private(d: int, c: Curve = P256) -> Tuple[int, int]:
    pt = _mul(c, d, (c.gx, c.gy))
    assert pt is not None
    return pt


def generate_private(c: Curve = P256) -> int:
    return 1 + secrets.randbelow(c.n - 1)


def encode_uncompressed(pub: Tuple[int, int], c: Curve = P256) -> bytes:
    return b"\x04" + pub[0].to_bytes(c.size, "big") + pub[1].to_bytes(c.size, "big")


def decode_uncompressed(raw: bytes, c: Curve = P256) -> Tuple[int, int]:
    if len(raw) != 1 + 2 * c.size or raw[0] != 4:
        raise ValueError(f"expected {1 + 2 * c.size}-byte uncompressed {c.name} point")
    pt = (int.from_bytes(raw[1:1 + c.size], "big"), int.from_bytes(raw[1 + c.size:], "big"))
    if not on_curve(pt, c):
        raise ValueError(f"point not on {c.name}")
    return pt


# -- signatures ------------------------------------------------------------------------

def _z(c: Curve, msg_hash: bytes) -> int:
    """Leftmost bit_length(n) bits of the hash (FIPS 186-4 §6.4) — matters for SHA-512 on P-384."""
    z = int.from_bytes(msg_hash, "big")
    extra = 8 * len(msg_hash) - c.n.bit_length()
    return z >> extra if extra > 0 else z


def sign(d: int, msg_hash: bytes, c: Curve = P256) -> Tuple[int, int]:
    """Plain ECDSA with a random nonce; for fake authenticators in tests only."""
    z = _z(c, msg_hash)
    while True:
        k = 1 + secrets.randbelow(c.n - 1)
        pt = _mul(c, k, (c.gx, c.gy))
        assert pt is not None
        r = pt[0] % c.n
        if r == 0:
            continue
        s = pow(k, -1, c.n) * (z + r * d) % c.n
        if s == 0:
            continue
        return r, s


def verify(pub: Tuple[int, int], msg_hash: bytes, sig: Tuple[int, int], c: Curve = P256) -> bool:
    r, s = sig
    if not (0 < r < c.n and 0 < s < c.n) or not on_curve(pub, c):
        return False
    z = _z(c, msg_hash)
    w = pow(s, -1, c.n)
    u1, u2 = z * w % c.n, r * w % c.n
    pt = _from_jac(c, _jac_add(c, _to_jac(_mul(c, u1, (c.gx, c.gy))), _to_jac(_mul(c, u2, pub))))
    return pt is not None and pt[0] % c.n == r


def verify_hashed(pub: Tuple[int, int], hash_name: str, message: bytes, sig: Tuple[int, int], c: Curve = P256) -> bool:
    return verify(pub, hashlib.new(hash_name, message).digest(), sig, c)


def verify_sha256(pub: Tuple[int, int], message: bytes, sig: Tuple[int, int], c: Curve = P256) -> bool:
    return verify_hashed(pub, "sha256", message, sig, c)


def sig_from_der(der_bytes: bytes) -> Tuple[int, int]:
    """X9.62 / WebAuthn signature: SEQUENCE { INTEGER r, INTEGER s }."""
    from .der import Reader

    seq = Reader(der_bytes).read_sequence()
    return seq.read_integer(), seq.read_integer()


def sig_to_der(sig: Tuple[int, int]) -> bytes:
    from .der import encode_integer, encode_sequence

    return encode_sequence(encode_integer(sig[0]) + encode_integer(sig[1]))
