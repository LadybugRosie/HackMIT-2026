#!/usr/bin/env python3
"""Standalone Proof-of-Writing verifier. Depends only on the Python standard library.

    attest_verify.py CERT.json DOC.txt [--events LEDGER.json]

Deliberately re-implements the hashing rules instead of importing the server, so a
verifier can be audited (and run) without trusting or installing the service.
Wire rules mirror server/attest/chain.py and web/src/lib/chain.js exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

CANON_KEYS = ("seq", "ts", "p", "d", "i", "k", "src", "prev")


def canon(ev: Dict[str, Any]) -> bytes:
    return json.dumps({k: ev.get(k) for k in CANON_KEYS}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def link_hash(ev: Dict[str, Any]) -> str:
    return hashlib.sha256(canon(ev) + str(ev["prev"]).encode("ascii")).hexdigest()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_chain(events: Sequence[Dict[str, Any]], genesis: str) -> Tuple[bool, Optional[int], str, str]:
    prev, seq = genesis, 0
    for idx, ev in enumerate(events):
        if ev.get("seq") != seq:
            return False, idx, f"seq {ev.get('seq')} != {seq}", prev
        if ev.get("prev") != prev:
            return False, idx, "prev does not match previous hash", prev
        if link_hash(ev) != ev.get("hash"):
            return False, idx, "hash mismatch (event altered)", prev
        prev, seq = ev["hash"], seq + 1
    return True, None, f"{len(events)} links valid", prev


def merkle_root(hashes: Sequence[str]) -> str:
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(h) for h in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def replay(events: Sequence[Dict[str, Any]]) -> str:
    text = ""
    for idx, ev in enumerate(events):
        k = ev.get("k")
        if k == "ckpt":
            text = ev.get("i") or ""
        elif k in ("type", "paste"):
            p, d = int(ev.get("p", 0)), int(ev.get("d", 0))
            if p > len(text) or p + d > len(text):
                raise ValueError(f"event {idx}: edit out of range")
            text = text[:p] + (ev.get("i") or "") + text[p + d:]
    return text


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("certificate")
    ap.add_argument("document")
    ap.add_argument("--events", help="ledger export JSON ({genesis, events}) for full re-derivation")
    args = ap.parse_args(argv)

    cert = json.load(open(args.certificate, encoding="utf-8"))
    text = open(args.document, encoding="utf-8", newline="").read()
    checks: List[Tuple[str, bool, str]] = []

    def check(name: str, ok: bool, if_ok: str, if_fail: str) -> None:
        checks.append((name, ok, if_ok if ok else if_fail))

    check("doc_sha256", sha256_hex(text) == cert["doc_sha256"],
          "submitted text matches certificate", "submitted text does NOT match certificate hash")
    check("doc_len", len(text) == cert["doc_len"], f"{len(text)} chars", f"{len(text)} chars vs {cert['doc_len']} certified")

    if args.events:
        ledger = json.load(open(args.events, encoding="utf-8"))
        events = ledger["events"]
        genesis = ledger.get("genesis", cert["genesis"])
        check("genesis", genesis == cert["genesis"], "ledger genesis matches certificate", "ledger genesis differs from certificate")
        ok, idx, msg, head = verify_chain(events, cert["genesis"])
        check("chain_links", ok, msg, f"broken at event {idx}: {msg}")
        check("chain_root", ok and head == cert["chain_root"], "head matches certificate", "ledger head != certified chain_root")
        check("event_count", len(events) == cert["event_count"], f"{len(events)} events",
              f"{len(events)} events vs {cert['event_count']} certified")
        check("merkle_root", ok and merkle_root([e["hash"] for e in events]) == cert["merkle_root"],
              "matches certificate", "does not match certificate")
        try:
            check("replay", replay(events) == text, "ledger replays to submitted text", "ledger replays to DIFFERENT text")
        except ValueError as exc:
            check("replay", False, "", str(exc))

    all_ok = all(ok for _, ok, _ in checks)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:12s} {detail}")
    level = cert.get("assurance_level", "?") if all_ok else "none"
    print(f"\n{'PASS' if all_ok else 'FAIL'} — assurance level {level}"
          f"{'' if args.events else '  (certificate-only check; pass --events for full ledger re-derivation)'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
