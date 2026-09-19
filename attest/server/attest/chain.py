"""Forward hash chain over canonical events.

The wire format here must match web/src/lib/chain.js and verifier/attest_verify.py
byte-for-byte: any divergence breaks verification, which is the point.

    canon(e)  = JSON(e without "hash"; keys sorted; no whitespace; raw UTF-8)
    hash(e)   = SHA256( canon(e) || e.prev )          # prev as lowercase hex ASCII
    genesis   = SHA256( session_id || ":" || nonce )

Timestamps and positions are integers so both JS and Python canonicalize identically.
Positions are in Unicode code points, not UTF-16 units, so Python slicing matches.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

CANON_KEYS = ("seq", "ts", "p", "d", "i", "k", "src", "prev")
HEX64 = 64


def canon(event: Mapping[str, Any]) -> bytes:
    obj = {key: event.get(key) for key in CANON_KEYS}
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def link_hash(event: Mapping[str, Any]) -> str:
    return hashlib.sha256(canon(event) + str(event["prev"]).encode("ascii")).hexdigest()


def genesis_hash(session_id: str, nonce: str) -> str:
    return hashlib.sha256(f"{session_id}:{nonce}".encode("utf-8")).hexdigest()


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ChainResult:
    ok: bool
    index: Optional[int] = None  # index into the checked sequence where it broke
    error: Optional[str] = None
    head: Optional[str] = None


def verify_chain(events: Sequence[Mapping[str, Any]], prev: str, start_seq: int = 0) -> ChainResult:
    """Check that `events` form a valid chain continuing from `prev` at `start_seq`."""
    expected_prev = prev
    expected_seq = start_seq
    for idx, ev in enumerate(events):
        if ev.get("seq") != expected_seq:
            return ChainResult(False, idx, f"seq {ev.get('seq')} != expected {expected_seq}")
        if ev.get("prev") != expected_prev:
            return ChainResult(False, idx, "prev does not match previous hash")
        actual = ev.get("hash")
        if not isinstance(actual, str) or len(actual) != HEX64:
            return ChainResult(False, idx, "malformed hash")
        if link_hash(ev) != actual:
            return ChainResult(False, idx, "hash mismatch (event altered)")
        expected_prev = actual
        expected_seq += 1
    return ChainResult(True, None, None, expected_prev)


def merkle_root(leaf_hashes: Sequence[str]) -> str:
    """Binary Merkle root over hex leaf hashes (odd node duplicated). Empty -> SHA256("")."""
    if not leaf_hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(h) for h in leaf_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()
