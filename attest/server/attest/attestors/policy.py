"""Level policy: which verified attestations raise a certificate from L1 to L2 to L3.

Kept free of pydantic so the offline verifier CLI can import it with the standard library only.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .base import AttestationResult, Attestor, compute_assurance_level, verify_attestations
from .hid import HidSummary, assess_hid

LEVEL_CHAIN_VALID = "L0"
LEVEL_DOC_BOUND = "L1"
LEVEL_DEVICE_BOUND = "L2"
LEVEL_HARDWARE_WITNESS = "L3"


def assess_attestations(attestations: Sequence[Mapping[str, Any]], attestors: Mapping[str, Attestor],
                        chain_root: str, known_heads: Optional[Set[str]],
                        events: Optional[Sequence[Mapping[str, Any]]] = None,
                        trusted_cdhashes: Iterable[str] = ()) -> Tuple[str, List[AttestationResult], Dict[str, Any]]:
    """Verify every attestation and decide the level.

    L1 -> L2 (device):
      * a head-signing attestation only counts if its head is a real state of *this* ledger
        (genesis or an event hash); with `known_heads=None` (certificate-only verification) only
        the final head can be checked, and earlier checkpoints are reported as unconfirmed;
      * the level is raised to L2 only by a verified device signature over the *final* chain root —
        so the whole ledger, not just some prefix, was on the device when it was sealed;
      * intermediate device signatures are "checkpoints" and timestamps are "timestamps": both are
        reported (they carry the elapsed-time argument) but neither raises the level by itself.

    L2 -> L3 (hardware witness, see hid.py):
      * requires L2, a gapless signed witness chain anchored to this ledger at both ends, every
        ledger keystroke inside a witnessed window, and no window where the editor recorded
        keystrokes the hardware did not see. With `events=None` coverage/correlation cannot be
        re-checked and the claimed level stands if everything checkable passes.
    """
    results = verify_attestations(attestors, None, attestations)
    summary: Dict[str, Any] = {"device_checkpoints": 0, "timestamps": 0, "final_head_signed": False,
                               "uv_at_seal": False, "first_timestamp": None, "last_timestamp": None, "unconfirmed": 0}
    raising: List[AttestationResult] = []
    hid_batches: List[Mapping[str, Any]] = []
    hid_results: List[AttestationResult] = []
    for att, res in zip(attestations, results):
        if att.get("kind") == "hid":
            hid_batches.append(att)
            hid_results.append(res)
            continue
        head = str(att.get("head", ""))
        in_chain = head == chain_root or (known_heads is not None and head in known_heads)
        if not res.ok:
            continue
        if not in_chain:
            if known_heads is None and head != chain_root:
                summary["unconfirmed"] += 1  # verifiable signature, but we lack the ledger to place it
            else:
                res.ok, res.detail = False, "head is not a state of this ledger"
            continue
        if res.kind == "webauthn":
            summary["device_checkpoints"] += 1
            if head == chain_root:
                summary["final_head_signed"] = True
                summary["uv_at_seal"] = summary["uv_at_seal"] or bool(res.data.get("uv"))
                raising.append(res)
        elif res.kind == "timestamp":
            summary["timestamps"] += 1
            t = res.data.get("gen_time")
            summary["first_timestamp"] = min(filter(None, [summary["first_timestamp"], t]), default=None)
            summary["last_timestamp"] = max(filter(None, [summary["last_timestamp"], t]), default=None)

    if hid_batches:
        hs: HidSummary = assess_hid(hid_batches, hid_results, events, chain_root, known_heads, trusted_cdhashes)
        summary["hid"] = hs.as_dict()
        summary["hid_checks"] = [{"name": n, "ok": ok, "detail": d} for n, ok, d in hs.checks]
        if hs.supports_l3:
            raising.append(AttestationResult(kind="hid", ok=True, level=LEVEL_HARDWARE_WITNESS, key_id=hs.helper_cdhash[:12],
                                             detail="hardware witness agrees with the ledger"))
    level = compute_assurance_level(LEVEL_DOC_BOUND, raising)
    return level, results, summary
