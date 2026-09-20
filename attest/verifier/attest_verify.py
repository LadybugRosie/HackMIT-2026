#!/usr/bin/env python3
"""Standalone Proof-of-Writing verifier. Depends only on the Python standard library.

    attest_verify.py CERT.json DOC.txt [--events LEDGER.json]

Deliberately re-implements the hashing rules instead of importing the server, so a
verifier can be audited (and run) without trusting or installing the service.
Wire rules mirror server/attest/chain.py and web/src/lib/chain.js exactly.

L2 attestations (device signatures over chain heads, RFC 3161 timestamps) are checked with the
pure-stdlib modules under server/attest/{crypto,attestors}/ when that directory sits next to this
script (or is on PYTHONPATH); otherwise they are reported as unchecked and the level is capped at
what this file can prove on its own (L1).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
try:  # optional: attestation verification (still stdlib-only, just more code)
    from attest.attestors import offline_attestors  # type: ignore
    from attest.attestors.policy import assess_attestations  # type: ignore
    from attest.issuer import key_id_for, verify_issuer  # type: ignore
    HAVE_ATTESTORS = True
except Exception:  # noqa: BLE001
    HAVE_ATTESTORS = False

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
    ap.add_argument("--issuer-key", metavar="HEX|FILE",
                    help="the issuing server's public key (65-byte uncompressed P-256, hex — from GET /v1/issuer — or a JSON file with "
                         "a public_key field). With it, a certificate not signed by that server FAILS `issuer`.")
    ap.add_argument("--trust-helper", action="append", metavar="CDHASH",
                    help="accept hardware-witness statements only from this helper build (repeatable); default: accept any, flag unverified")
    args = ap.parse_args(argv)

    cert = json.load(open(args.certificate, encoding="utf-8"))
    text = open(args.document, encoding="utf-8", newline="").read()
    checks: List[Tuple[str, bool, str, bool]] = []  # (name, ok, detail, informational)

    def check(name: str, ok: bool, if_ok: str, if_fail: str, info: bool = False) -> None:
        checks.append((name, ok, if_ok if ok else if_fail, info and not ok))

    check("doc_sha256", sha256_hex(text) == cert["doc_sha256"],
          "submitted text matches certificate", "submitted text does NOT match certificate hash")
    check("doc_len", len(text) == cert["doc_len"], f"{len(text)} chars", f"{len(text)} chars vs {cert['doc_len']} certified")

    events: List[Dict[str, Any]] = []
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

    if HAVE_ATTESTORS:
        trusted = None
        if args.issuer_key:
            key = args.issuer_key
            if os.path.exists(key):
                key = json.load(open(key, encoding="utf-8"))["public_key"]
            trusted = {key_id_for(key): key}
        present, sig_ok, is_trusted, detail = verify_issuer(cert, trusted)
        if trusted is not None:
            check("issuer", present and sig_ok and bool(is_trusted), detail, detail)
        else:
            check("issuer", sig_ok, detail, detail, info=not present)
    elif cert.get("issuer"):
        check("issuer", False, "", "issuer signature present but server/attest modules not found — cannot check", info=True)

    attestations = cert.get("attestations") or []
    claimed = cert.get("assurance_level", "?")
    level_note = ""
    if attestations or claimed not in ("L0", "L1"):
        if HAVE_ATTESTORS:
            heads = None
            if args.events:
                heads = {cert["genesis"], *(e["hash"] for e in events)}
            level, results, summary = assess_attestations(attestations, offline_attestors(), cert["chain_root"], heads,
                                                          events=events if args.events else None,
                                                          trusted_cdhashes=args.trust_helper or ())
            claims_l3 = claimed == "L3"  # a witness that did not qualify is why a cert stays L2, not a defect
            hid_b = [(att, res) for att, res in zip(attestations, results) if att.get("kind") == "hid"]
            for n, (att, res) in enumerate(zip(attestations, results)):
                if att.get("kind") == "hid":
                    continue
                tag = "final" if att.get("head") == cert["chain_root"] else "checkpoint"
                check(f"{res.kind}[{n}]", res.ok, f"{tag} {str(att.get('head'))[:12]}… — {res.detail}",
                      f"{tag} {str(att.get('head'))[:12]}… — {res.detail}")
            if hid_b:
                bad = [res for _a, res in hid_b if not res.ok]
                n_st = sum(len(a.get("statements") or []) for a, _r in hid_b)
                check("hid_batches", not bad, f"{len(hid_b)} batch(es), {n_st} signed statement(s) verified",
                      f"{len(bad)} of {len(hid_b)} batch(es) failed: {bad[0].detail if bad else ''}", info=not claims_l3)
            for c in summary.get("hid_checks", []):
                check(c["name"], c["ok"], c["detail"], c["detail"], info=not claims_l3)
            check("assurance_level", level == claimed, f"attestations support {level}",
                  f"attestations support {level}, certificate claims {claimed}")
            if summary["final_head_signed"]:
                level_note = (f"  (device-signed final head{' with user verification' if summary['uv_at_seal'] else ''}, "
                              f"{summary['device_checkpoints']} checkpoint(s), {summary['timestamps']} trusted timestamp(s))")
            hid = summary.get("hid")
            if hid:
                trusted = {True: "pinned helper", False: "UNPINNED helper", None: "helper not pinned (software witness)"}[hid["helper_trusted"]]
                devs = ", ".join(f"{d['id']}{' built-in' if d['builtin'] else ''} {d['share']:.0%}" for d in hid["devices"])
                level_note += (f"\n  hardware witness: {hid['windows']} window(s), coverage {hid['coverage_ratio']:.0%}, "
                               f"editor {hid['ledger_kd']} / hardware {hid['hw_kd']} key-downs, {len(hid['injection_windows'])} injection window(s); "
                               f"{trusted}; devices: {devs or 'none'}")
        else:
            check("attestations", False, "", f"{len(attestations)} attestation(s) present but server/attest modules not found — cannot verify above L1")

    all_ok = all(ok or info for _, ok, _, info in checks)
    for name, ok, detail, info in checks:
        print(f"  [{'PASS' if ok else 'INFO' if info else 'FAIL'}] {name:16s} {detail}")
    level = claimed if all_ok else "none"
    print(f"\n{'PASS' if all_ok else 'FAIL'} — assurance level {level}{level_note}"
          f"{'' if args.events else '  (certificate-only check; pass --events for full ledger re-derivation)'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
