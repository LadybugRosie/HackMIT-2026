"""Minimal CBOR (RFC 8949) decoder for WebAuthn `attestationObject` and COSE keys, plus a tiny
encoder used only by tests to fabricate authenticator output. Supports the definite-length
subset the WebAuthn spec (CTAP2 canonical CBOR) actually emits: unsigned/negative ints, byte and
text strings, arrays, maps, and the simple values false/true/null."""
from __future__ import annotations

from typing import Any, Tuple


def decode(data: bytes) -> Any:
    value, end = _decode_item(data, 0)
    return value  # trailing bytes are tolerated (attestationObject is followed by nothing anyway)


def decode_prefix(data: bytes) -> Tuple[Any, int]:
    """Decode one item and return (value, bytes consumed) — authData has a COSE key followed by extensions."""
    return _decode_item(data, 0)


def _read_uint(data: bytes, pos: int, info: int) -> Tuple[int, int]:
    if info < 24:
        return info, pos
    n = {24: 1, 25: 2, 26: 4, 27: 8}.get(info)
    if n is None:
        raise ValueError("CBOR: indefinite lengths unsupported")
    return int.from_bytes(data[pos:pos + n], "big"), pos + n


def _decode_item(data: bytes, pos: int) -> Tuple[Any, int]:
    if pos >= len(data):
        raise ValueError("CBOR: unexpected end")
    major, info = data[pos] >> 5, data[pos] & 0x1F
    pos += 1
    if major == 0:
        return _read_uint(data, pos, info)
    if major == 1:
        v, pos = _read_uint(data, pos, info)
        return -1 - v, pos
    if major in (2, 3):
        n, pos = _read_uint(data, pos, info)
        chunk = data[pos:pos + n]
        if len(chunk) != n:
            raise ValueError("CBOR: string overruns buffer")
        return (chunk if major == 2 else chunk.decode("utf-8")), pos + n
    if major == 4:
        n, pos = _read_uint(data, pos, info)
        out = []
        for _ in range(n):
            v, pos = _decode_item(data, pos)
            out.append(v)
        return out, pos
    if major == 5:
        n, pos = _read_uint(data, pos, info)
        out = {}
        for _ in range(n):
            k, pos = _decode_item(data, pos)
            v, pos = _decode_item(data, pos)
            out[k] = v
        return out, pos
    if major == 7:
        if info == 20:
            return False, pos
        if info == 21:
            return True, pos
        if info == 22:
            return None, pos
        raise ValueError(f"CBOR: unsupported simple value {info}")
    raise ValueError(f"CBOR: unsupported major type {major}")


# -- encoder (tests only) ----------------------------------------------------------------

def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    for info, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
        if n < 1 << (8 * size):
            return bytes([(major << 5) | info]) + n.to_bytes(size, "big")
    raise ValueError("too large")


def encode(value: Any) -> bytes:
    if value is False:
        return b"\xf4"
    if value is True:
        return b"\xf5"
    if value is None:
        return b"\xf6"
    if isinstance(value, int):
        return _head(0, value) if value >= 0 else _head(1, -1 - value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        b = value.encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(value, (list, tuple)):
        return _head(4, len(value)) + b"".join(encode(v) for v in value)
    if isinstance(value, dict):
        # CTAP2 canonical order: shorter keys first, then bytewise — good enough for our small maps.
        items = sorted(((encode(k), encode(v)) for k, v in value.items()), key=lambda kv: (len(kv[0]), kv[0]))
        return _head(5, len(items)) + b"".join(k + v for k, v in items)
    raise TypeError(f"cannot CBOR-encode {type(value).__name__}")
