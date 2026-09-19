"""Hardware witness (Stage 4, L3): signed, hash-chained statements from a native helper that
counts *physical* HID key-downs in fixed windows, correlated against the ledger's content-free
`kd` events.

    statement = {v, sid, seg, seq, t0, t1, kd, devices:[{id, kd, builtin}], idle_ms, cdhash,
                 anchor: {head} | null, final: bool, prev, hash, sig}
    canon     = JSON(statement without hash/sig; keys sorted; compact; raw UTF-8)
    hash      = SHA256(canon || prev)          prev of seq 0 == anchor.head (binds the segment to
    sig       = ECDSA-P256 over SHA256(hash)    a state of *this* ledger)

Verification is pure and stdlib-only so the offline CLI can run it. See docs/L3-hardware-witness.md
§4.4 for the rules and §6 for what this does and does not prove.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ..crypto import ec
from .base import AttestationResult

CANON_KEYS = ("v", "sid", "seg", "seq", "t0", "t1", "kd", "devices", "idle_ms", "cdhash", "anchor", "final", "prev")
DEVICE_KEYS = ("id", "kd", "builtin")
SKEW_MS = 250                 # browser Date.now() vs HID report clock, same machine
INJECTION_MIN_LEDGER = 8      # below this a window cannot be called injection (detection floor)
INJECTION_RATIO = 0.5
LEDGER_KEY_KINDS = ("kd",)    # content-free key-down events


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canon(st: Mapping[str, Any]) -> bytes:
    body = {k: st.get(k) for k in CANON_KEYS}
    body["devices"] = [{dk: d.get(dk) for dk in DEVICE_KEYS} for d in (st.get("devices") or [])]
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def statement_hash(st: Mapping[str, Any]) -> str:
    return hashlib.sha256(canon(st) + str(st.get("prev", "")).encode("ascii")).hexdigest()


def verify_statement_signature(st: Mapping[str, Any], pub: Tuple[int, int]) -> bool:
    try:
        sig = ec.sig_from_der(_b64url_decode(st["sig"]))
        return ec.verify_sha256(pub, str(st["hash"]).encode("ascii"), sig, ec.P256)
    except (KeyError, ValueError, TypeError):
        return False


def public_key_tuple(pk: Mapping[str, str]) -> Tuple[int, int]:
    return int(pk["x"], 16), int(pk["y"], 16)


# -- per-batch attestor (structure + signatures) -------------------------------------------------

class HidAttestor:
    """Attestation record: {kind: "hid", key_id, public_key: {crv,x,y}, cdhash, statements: [...]}.
    Verifies every statement's hash and signature and the intra-batch chain. Cross-batch chain,
    anchors, coverage and correlation are `assess_hid`'s job. Level "L2" here means "does not by
    itself raise past L2"; the L3 raise is decided by the policy after correlation."""

    kind = "hid"

    def __init__(self, lookup: Optional[Callable[[str], Optional[Mapping[str, Any]]]] = None):
        self.lookup = lookup

    def verify(self, statement: bytes, attestation: Mapping[str, Any]) -> AttestationResult:
        key_id = str(attestation.get("key_id", ""))
        cred = self.lookup(key_id) if self.lookup else None
        if self.lookup and cred is None:
            return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id, detail="unknown helper key")
        pk = (cred or attestation).get("public_key")
        if not pk:
            return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id, detail="no public key")
        try:
            pub = public_key_tuple(pk)
        except (KeyError, ValueError):
            return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id, detail="malformed public key")
        sts = list(attestation.get("statements") or [])
        if not sts:
            return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id, detail="empty batch")
        prev = None
        for st in sts:
            if statement_hash(st) != st.get("hash"):
                return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id,
                                         detail=f"statement {st.get('seg')}/{st.get('seq')} hash mismatch (altered)")
            if not verify_statement_signature(st, pub):
                return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id,
                                         detail=f"statement {st.get('seg')}/{st.get('seq')} signature does not verify")
            if prev is not None and (st.get("seg") != prev.get("seg") or st.get("seq") != prev.get("seq") + 1 or st.get("prev") != prev.get("hash")):
                return AttestationResult(kind=self.kind, ok=False, level="none", key_id=key_id,
                                         detail=f"batch chain break at {st.get('seg')}/{st.get('seq')}")
            prev = st
        first, last = sts[0], sts[-1]
        return AttestationResult(kind=self.kind, ok=True, level="L2", key_id=key_id,
                                 detail=f"{len(sts)} signed window(s) seg {first.get('seg')} seq {first.get('seq')}–{last.get('seq')}",
                                 data={"statements": len(sts), "seg": first.get("seg"), "seq_from": first.get("seq"), "seq_to": last.get("seq"),
                                       "final": bool(last.get("final"))})


# -- cross-batch assessment: chain, anchors, coverage, correlation ------------------------------

@dataclass
class HidSummary:
    ok: bool = False
    supports_l3: bool = False
    reasons: List[str] = field(default_factory=list)
    checks: List[Tuple[str, bool, str]] = field(default_factory=list)  # (name, ok, detail)
    windows: int = 0
    segments: int = 0
    covered_ms: int = 0
    coverage_ratio: float = 0.0
    ledger_kd: int = 0
    hw_kd: int = 0
    injection_windows: List[Dict[str, Any]] = field(default_factory=list)
    shortfall_windows: int = 0
    devices: List[Dict[str, Any]] = field(default_factory=list)
    helper_trusted: Optional[bool] = None
    helper_cdhash: str = ""
    correlation_basis: str = "kd"
    correlation_checked: bool = False

    def as_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d.pop("checks")
        return d


def ledger_keystroke_ts(events: Sequence[Mapping[str, Any]]) -> Tuple[List[int], str]:
    """Timestamps of keystrokes as the ledger saw them.

    Primary basis: content-free `kd` events (one per physical key-down the browser saw). On top of
    that, any `type` event that inserts more net text than one key press explains — `insertText`
    from a script, dictation, a macro — contributes one keystroke-equivalent per extra code point at
    its timestamp, so text that arrived without key events still has to be matched by hardware.
    Autocorrect (delete 5, insert 5 -> net 0) and IME commits (net 3 for ~6 key-downs) stay within
    the hardware >= editor rule. Pastes are excluded: provenance already labels them and a paste is
    one physical Cmd-V. Older ledgers without `kd` fall back to edit events (weaker basis)."""
    kd = sorted(int(e["ts"]) for e in events if e.get("k") in LEDGER_KEY_KINDS)
    extra: List[int] = []
    for e in events:
        if e.get("k") != "type":
            continue
        net = len(e.get("i") or "") - int(e.get("d", 0))
        if kd:
            if net >= 2:
                extra.extend([int(e["ts"])] * (net - 1))  # the first code point may be the key the kd recorded
        else:
            extra.extend([int(e["ts"])] * max(1, net))
    return sorted(kd + extra), ("kd" if kd else "edits")


def tolerance(ledger_kd: int) -> int:
    return 2 + math.ceil(0.05 * ledger_kd)


def assess_hid(batches: Sequence[Mapping[str, Any]], batch_results: Sequence[AttestationResult],
               events: Optional[Sequence[Mapping[str, Any]]], chain_root: str, known_heads: Optional[Set[str]],
               trusted_cdhashes: Iterable[str] = ()) -> HidSummary:
    """`events`/`known_heads` None = certificate-only verification: chain, anchors-to-root and helper
    identity are checked; coverage and correlation are reported as not re-checked."""
    s = HidSummary()
    trusted = set(trusted_cdhashes)
    good = [b for b, r in zip(batches, batch_results) if r.ok]
    if len(good) != len(batches):
        s.reasons.append(f"{len(batches) - len(good)} batch(es) failed signature/structure checks")
    sts: List[Mapping[str, Any]] = sorted((st for b in good for st in (b.get("statements") or [])),
                                          key=lambda st: (int(st.get("seg", 0)), int(st.get("seq", 0))))
    if not sts:
        s.checks.append(("hid_chain", False, "no verified witness statements"))
        return s
    s.windows = len(sts)

    # -- chain per segment + gapless windows
    chain_ok, chain_detail = True, ""
    segments: Dict[int, List[Mapping[str, Any]]] = {}
    for st in sts:
        segments.setdefault(int(st.get("seg", 0)), []).append(st)
    s.segments = len(segments)
    for seg, seg_sts in segments.items():
        for n, st in enumerate(seg_sts):
            if int(st.get("seq", -1)) != n:
                chain_ok, chain_detail = False, f"segment {seg}: seq {st.get('seq')} where {n} expected (missing statements)"
                break
            if n and (st.get("prev") != seg_sts[n - 1].get("hash") or int(st["t0"]) != int(seg_sts[n - 1]["t1"])):
                chain_ok, chain_detail = False, f"segment {seg}: window {n} does not continue window {n - 1}"
                break
            if int(st["t1"]) < int(st["t0"]):
                chain_ok, chain_detail = False, f"segment {seg}: window {n} ends before it starts"
                break
        if not chain_ok:
            break
    s.checks.append(("hid_chain", chain_ok, chain_detail or f"{s.windows} gapless window(s) in {s.segments} segment(s)"))

    # -- anchors: each segment's seq 0 prev/anchor is a real head of this ledger; the final one is the root
    anchor_ok, anchor_detail = True, ""
    last = sts[-1]
    for seg, seg_sts in segments.items():
        head = (seg_sts[0].get("anchor") or {}).get("head")
        if not head or seg_sts[0].get("prev") != head:
            anchor_ok, anchor_detail = False, f"segment {seg} is not anchored to a ledger head"
            break
        if known_heads is not None and head not in known_heads and head != chain_root:
            anchor_ok, anchor_detail = False, f"segment {seg} anchors to a head that is not a state of this ledger"
            break
    if anchor_ok:
        if not last.get("final"):
            anchor_ok, anchor_detail = False, "no terminal statement — the witness did not seal with the ledger"
        elif (last.get("anchor") or {}).get("head") != chain_root:
            anchor_ok, anchor_detail = False, "terminal statement is not anchored to the final chain root"
    s.checks.append(("hid_anchors", anchor_ok, anchor_detail or "segments anchored to ledger heads; terminal statement anchored to chain root"))

    # -- helper identity
    cdhashes = {str(st.get("cdhash", "")) for st in sts}
    s.helper_cdhash = next(iter(cdhashes)) if len(cdhashes) == 1 else ",".join(sorted(cdhashes))
    if len(cdhashes) != 1:
        s.helper_trusted = False
        s.checks.append(("hid_helper", False, "statements come from more than one helper build"))
    elif not trusted:
        s.helper_trusted = None
        s.checks.append(("hid_helper", True, f"helper {s.helper_cdhash[:12]}… not pinned (no trusted cdhash configured) — software witness, unverified build"))
    else:
        s.helper_trusted = s.helper_cdhash in trusted
        s.checks.append(("hid_helper", s.helper_trusted, f"helper {s.helper_cdhash[:12]}… {'is' if s.helper_trusted else 'is NOT'} a pinned build"))

    # -- self-consistency
    incons = [st for st in sts if int(st.get("kd", 0)) > 0 and int(st.get("idle_ms", 0)) > int(st["t1"]) - int(st["t0"])]
    s.checks.append(("hid_consistency", not incons,
                     f"{len(incons)} window(s) report key-downs while idle" if incons else "idle timer agrees with key-down counts"))

    # -- devices
    dev: Dict[str, Dict[str, Any]] = {}
    for st in sts:
        for d in st.get("devices") or []:
            e = dev.setdefault(str(d.get("id")), {"id": str(d.get("id")), "builtin": bool(d.get("builtin")), "kd": 0})
            e["kd"] += int(d.get("kd", 0))
    s.hw_kd = sum(int(st.get("kd", 0)) for st in sts)
    for e in dev.values():
        e["share"] = round(e["kd"] / s.hw_kd, 3) if s.hw_kd else 0.0
    s.devices = sorted(dev.values(), key=lambda e: -e["kd"])
    s.covered_ms = sum(int(st["t1"]) - int(st["t0"]) for st in sts)

    if events is None or known_heads is None:
        s.checks.append(("hid_coverage", True, "not re-checked (ledger needed)"))
        s.checks.append(("hid_correlation", True, "not re-checked (ledger needed)"))
        s.ok = all(ok for _, ok, _ in s.checks)
        s.supports_l3 = s.ok
        return s

    # -- coverage: every ledger keystroke falls in some window
    ts_list, s.correlation_basis = ledger_keystroke_ts(events)
    s.ledger_kd = len(ts_list)
    windows = [(int(st["t0"]) - SKEW_MS, int(st["t1"]) + SKEW_MS) for st in sts]
    windows.sort()
    covered = 0
    wi = 0
    for t in ts_list:
        while wi < len(windows) and windows[wi][1] <= t:
            wi += 1
        if wi < len(windows) and windows[wi][0] <= t < windows[wi][1]:
            covered += 1
    s.coverage_ratio = round(covered / s.ledger_kd, 4) if s.ledger_kd else 1.0
    cov_ok = covered == s.ledger_kd
    s.checks.append(("hid_coverage", cov_ok, f"{covered}/{s.ledger_kd} ledger keystrokes fall inside witnessed windows"
                     + (f" ({s.ledger_kd - covered} unwitnessed)" if not cov_ok else "")))
    if not cov_ok:
        s.reasons.append(f"coverage {s.coverage_ratio:.2%} — {s.ledger_kd - covered} keystrokes outside witnessed windows")

    # -- correlation per window: hardware may see more, never (much) fewer
    s.correlation_checked = True
    ti = 0
    ts_sorted = ts_list
    for st in sts:
        t0, t1 = int(st["t0"]), int(st["t1"])
        lo = _bisect(ts_sorted, t0)
        hi = _bisect(ts_sorted, t1)
        ledger_kd = hi - lo
        hw = int(st.get("kd", 0))
        if ledger_kd >= INJECTION_MIN_LEDGER and hw < INJECTION_RATIO * ledger_kd:
            s.injection_windows.append({"seg": st.get("seg"), "seq": st.get("seq"), "t0": t0, "t1": t1, "ledger_kd": ledger_kd, "hw_kd": hw})
        elif hw < ledger_kd - tolerance(ledger_kd):
            s.shortfall_windows += 1
    corr_ok = not s.injection_windows and not s.shortfall_windows
    if s.injection_windows:
        w = s.injection_windows[0]
        detail = (f"{len(s.injection_windows)} injection window(s); first: editor {w['ledger_kd']} keystrokes, hardware {w['hw_kd']} "
                  f"({_clock(w['t0'])}–{_clock(w['t1'])})")
        s.reasons.append(detail)
    elif s.shortfall_windows:
        detail = f"{s.shortfall_windows} window(s) where the editor recorded more keystrokes than the hardware saw"
        s.reasons.append(detail)
    else:
        detail = f"hardware key-downs cover editor keystrokes in all {s.windows} window(s) (editor {s.ledger_kd}, hardware {s.hw_kd})"
    s.checks.append(("hid_correlation", corr_ok, detail))
    if s.correlation_basis == "edits":
        s.reasons.append("correlation used edit events (no kd events in ledger) — weaker basis")

    s.ok = all(ok for _, ok, _ in s.checks)
    s.supports_l3 = s.ok and cov_ok and corr_ok
    return s


def _bisect(a: List[int], x: int) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _clock(ms: int) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%H:%M:%S")
