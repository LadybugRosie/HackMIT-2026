"""Level policy: which verified attestations raise a certificate from L1 to L2.

Kept free of pydantic so the offline verifier CLI can import it with the standard library only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .base import AttestationResult, Attestor, compute_assurance_level, verify_attestations

LEVEL_CHAIN_VALID = "L0"
LEVEL_DOC_BOUND = "L1"
LEVEL_DEVICE_BOUND = "L2"


def assess_attestations(attestations: Sequence[Mapping[str, Any]], attestors: Mapping[str, Attestor],
                        chain_root: str, known_heads: Optional[Set[str]]) -> Tuple[str, List[AttestationResult], Dict[str, Any]]:
    """Verify every attestation over its own head and decide the level (L1 -> L2 policy):

      * an attestation only counts if its head is a real state of *this* ledger (genesis or an
        event hash); with `known_heads=None` (certificate-only verification) only the final head
        can be checked, and earlier checkpoints are reported as unconfirmed;
      * the level is raised to L2 only by a verified device signature over the *final* chain root —
        so the whole ledger, not just some prefix, was on the device when it was sealed;
      * intermediate device signatures are "checkpoints" and timestamps are "timestamps": both are
        reported (they carry the elapsed-time argument) but neither raises the level by itself.
    """
    results = verify_attestations(attestors, None, attestations)
    summary: Dict[str, Any] = {"device_checkpoints": 0, "timestamps": 0, "final_head_signed": False,
                               "uv_at_seal": False, "first_timestamp": None, "last_timestamp": None, "unconfirmed": 0}
    raising: List[AttestationResult] = []
    for att, res in zip(attestations, results):
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
    level = compute_assurance_level(LEVEL_DOC_BOUND, raising)
    return level, results, summary
