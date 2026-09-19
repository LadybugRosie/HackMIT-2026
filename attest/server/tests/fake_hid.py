"""A software stand-in for native/attest-hid: emits signed, hash-chained window statements
byte-compatible with the real helper. Modes let tests fabricate the failure cases the verifier
must catch (injection, gaps, wrong anchors, tampering, a second device, an unwitnessed prefix)."""
from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict, List, Mapping, Optional, Sequence

from attest.attestors.hid import statement_hash
from attest.crypto import ec

BUILTIN = {"id": "05ac:0341#9f2c", "builtin": True}
GADGET = {"id": "1a86:7523#0001", "builtin": False}


class FakeHelper:
    def __init__(self, cdhash: str = "a4f1" + "0" * 36, window_ms: int = 5000):
        self.d = ec.generate_private()
        self.pub = ec.public_from_private(self.d)
        self.cdhash = cdhash
        self.window_ms = window_ms
        self.key_id = hashlib.sha256(ec.encode_uncompressed(self.pub)).hexdigest()[:16]

    # -- identity / enrollment -------------------------------------------------------------
    @property
    def public_key_hex(self) -> str:
        return ec.encode_uncompressed(self.pub).hex()

    def sign_bytes(self, data: bytes) -> str:
        der = ec.sig_to_der(ec.sign(self.d, hashlib.sha256(data).digest()))
        return base64.urlsafe_b64encode(der).decode().rstrip("=")

    def enroll_payload(self, challenge: bytes) -> Dict[str, Any]:
        return {"public_key": self.public_key_hex, "key_id": self.key_id, "cdhash": self.cdhash,
                "key_backend": "software", "signature": self.sign_bytes(challenge), "helper_version": "test"}

    # -- statements --------------------------------------------------------------------------
    def _sign(self, st: Dict[str, Any]) -> Dict[str, Any]:
        st["hash"] = statement_hash(st)
        st["sig"] = self.sign_bytes(st["hash"].encode("ascii"))
        return st

    def witness(self, sid: str, anchor_head: str, final_head: str, keystroke_ts: Sequence[int],
                t_start: Optional[int] = None, t_end: Optional[int] = None, seg: int = 0,
                inject_window: Optional[int] = None, drop_window: Optional[int] = None,
                extra_per_window: int = 0, gadget_share: float = 0.0, idle_lie_window: Optional[int] = None,
                no_final: bool = False) -> List[Dict[str, Any]]:
        """Honest witness of `keystroke_ts` (the ledger's kd timestamps) over fixed windows from
        t_start to t_end, then a terminal statement anchored at `final_head`.
        inject_window: report 0 hardware key-downs in that window (an injection went unnoticed by hardware).
        drop_window:   omit that statement entirely (a gap).
        extra_per_window: hardware saw this many more key-downs than the editor (shortcuts etc.).
        gadget_share:  fraction of key-downs attributed to an external device.
        idle_lie_window: report idle_ms longer than the window while claiming key-downs."""
        ts = sorted(keystroke_ts)
        t0 = t_start if t_start is not None else (ts[0] - 1500 if ts else 1_700_000_000_000)
        end = t_end if t_end is not None else (ts[-1] + 800 if ts else t0 + self.window_ms)
        out: List[Dict[str, Any]] = []
        prev = anchor_head
        seq = 0
        cur = t0
        while cur < end:
            t1 = min(cur + self.window_ms, end)
            n = sum(1 for t in ts if cur <= t < t1)
            hw = 0 if seq == inject_window else n + (extra_per_window if n or extra_per_window else 0)
            gadget = round(hw * gadget_share)
            devices = []
            if hw - gadget:
                devices.append({**BUILTIN, "kd": hw - gadget})
            if gadget:
                devices.append({**GADGET, "kd": gadget})
            idle = (t1 - cur) + 1000 if seq == idle_lie_window else (0 if hw else t1 - cur)
            st = {"v": 1, "sid": sid, "seg": seg, "seq": seq, "t0": cur, "t1": t1, "kd": hw, "devices": devices,
                  "idle_ms": idle, "cdhash": self.cdhash, "anchor": {"head": anchor_head} if seq == 0 else None,
                  "final": False, "prev": prev}
            self._sign(st)
            if seq != drop_window:
                out.append(st)
            prev = st["hash"]
            seq += 1
            cur = t1
        if not no_final:
            st = {"v": 1, "sid": sid, "seg": seg, "seq": seq, "t0": cur, "t1": cur, "kd": 0, "devices": [], "idle_ms": 0,
                  "cdhash": self.cdhash, "anchor": {"head": final_head}, "final": True, "prev": prev}
            out.append(self._sign(st))
        return out

    def batch(self, statements: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        """Attestation record as the server stores it / the certificate carries it."""
        return {"kind": "hid", "key_id": self.key_id, "cdhash": self.cdhash, "key_backend": "software",
                "public_key": {"crv": "P-256", "x": f"{self.pub[0]:064x}", "y": f"{self.pub[1]:064x}"},
                "statements": [dict(s) for s in statements]}


def random_head() -> str:
    return secrets.token_hex(32)
