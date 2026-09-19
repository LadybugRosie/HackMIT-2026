"""Minimal ASN.1 DER: enough to build an RFC 3161 TimeStampReq and to walk a TimeStampResp /
CMS SignedData / X.509 certificate. Tags are the raw identifier octets (e.g. 0x30 SEQUENCE,
0x02 INTEGER, 0x04 OCTET STRING, 0x06 OID, 0xA0 [0] constructed context)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Tuple

SEQUENCE, SET, INTEGER, BIT_STRING, OCTET_STRING, NULL, OID, BOOLEAN = 0x30, 0x31, 0x02, 0x03, 0x04, 0x05, 0x06, 0x01
GENERALIZED_TIME, UTC_TIME = 0x18, 0x17


def encode_length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def encode_tlv(tag: int, body: bytes) -> bytes:
    return bytes([tag]) + encode_length(len(body)) + body


def encode_sequence(body: bytes) -> bytes:
    return encode_tlv(SEQUENCE, body)


def encode_integer(n: int) -> bytes:
    if n < 0:
        raise ValueError("negative integers not needed here")
    body = n.to_bytes((n.bit_length() + 8) // 8, "big") or b"\x00"  # +8 keeps a leading 0x00 for high bit
    return encode_tlv(INTEGER, body)


def encode_octet_string(b: bytes) -> bytes:
    return encode_tlv(OCTET_STRING, b)


def encode_null() -> bytes:
    return encode_tlv(NULL, b"")


def encode_boolean(v: bool) -> bytes:
    return encode_tlv(BOOLEAN, b"\xff" if v else b"\x00")


def encode_oid(dotted: str) -> bytes:
    parts = [int(x) for x in dotted.split(".")]
    out = bytearray([40 * parts[0] + parts[1]])
    for v in parts[2:]:
        chunk = [v & 0x7F]
        v >>= 7
        while v:
            chunk.append(0x80 | (v & 0x7F))
            v >>= 7
        out.extend(reversed(chunk))
    return encode_tlv(OID, bytes(out))


def decode_oid(body: bytes) -> str:
    first = body[0]
    parts = [first // 40, first % 40] if first < 80 else [2, first - 80]
    v = 0
    for b in body[1:]:
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            parts.append(v)
            v = 0
    return ".".join(map(str, parts))


@dataclass
class TLV:
    tag: int
    body: bytes
    raw: bytes  # full encoding incl. header — needed when the signed bytes are a whole element

    @property
    def constructed(self) -> bool:
        return bool(self.tag & 0x20)

    def children(self) -> List["TLV"]:
        return list(Reader(self.body).iter())

    def integer(self) -> int:
        return int.from_bytes(self.body, "big", signed=True)

    def oid(self) -> str:
        return decode_oid(self.body)

    def bit_string(self) -> bytes:
        return self.body[1:]  # drop the unused-bits octet


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def at_end(self) -> bool:
        return self.pos >= len(self.data)

    def read(self) -> TLV:
        start = self.pos
        d = self.data
        if start >= len(d):
            raise ValueError("DER: unexpected end")
        tag = d[start]
        i = start + 1
        if tag & 0x1F == 0x1F:
            raise ValueError("DER: multi-byte tags unsupported")
        first = d[i]
        i += 1
        if first < 0x80:
            length = first
        else:
            nbytes = first & 0x7F
            if nbytes == 0 or nbytes > 4:
                raise ValueError("DER: bad length")
            length = int.from_bytes(d[i:i + nbytes], "big")
            i += nbytes
        end = i + length
        if end > len(d):
            raise ValueError("DER: element overruns buffer")
        self.pos = end
        return TLV(tag, d[i:end], d[start:end])

    def iter(self) -> Iterator[TLV]:
        while not self.at_end():
            yield self.read()

    def expect(self, tag: int) -> TLV:
        t = self.read()
        if t.tag != tag:
            raise ValueError(f"DER: expected tag 0x{tag:02x}, got 0x{t.tag:02x}")
        return t

    def read_sequence(self) -> "Reader":
        return Reader(self.expect(SEQUENCE).body)

    def read_integer(self) -> int:
        return self.expect(INTEGER).integer()


def parse_time(t: TLV) -> str:
    """GeneralizedTime/UTCTime -> ISO-8601 UTC string."""
    s = t.body.decode("ascii")
    if t.tag == UTC_TIME:  # YYMMDDhhmmssZ
        yy = int(s[:2])
        s = f"{2000 + yy if yy < 50 else 1900 + yy}{s[2:]}"
    date, rest = s[:8], s[8:]
    hms = rest[:6].ljust(6, "0")
    frac = ""
    if "." in rest:
        frac = "." + rest.split(".", 1)[1].rstrip("Z")
    return f"{date[:4]}-{date[4:6]}-{date[6:8]}T{hms[:2]}:{hms[2:4]}:{hms[4:6]}{frac}Z"


def find_first(t: TLV, tag: int) -> TLV:
    """Depth-first search for the first element with `tag` under a constructed element."""
    stack: List[TLV] = [t]
    while stack:
        cur = stack.pop(0)
        if cur.tag == tag and cur is not t:
            return cur
        if cur.constructed:
            stack = cur.children() + stack
    raise ValueError(f"DER: tag 0x{tag:02x} not found")
