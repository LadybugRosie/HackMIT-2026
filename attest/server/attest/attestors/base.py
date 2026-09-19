from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Protocol, Sequence

LEVELS = ("none", "L0", "L1", "L2", "L3")


@dataclass
class AttestationResult:
    kind: str                   # webauthn | secure_enclave | hid | timestamp
    ok: bool
    level: str                  # highest level this attestation supports when ok
    key_id: str = ""
    detail: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class Attestor(Protocol):
    kind: str

    def verify(self, statement: bytes, attestation: Mapping[str, Any]) -> AttestationResult:
        """`statement` is what was signed (normally the chain head as ASCII hex bytes)."""
        ...


def verify_attestations(attestors: Mapping[str, Attestor], statement: bytes,
                        attestations: Sequence[Mapping[str, Any]]) -> List[AttestationResult]:
    results: List[AttestationResult] = []
    for att in attestations:
        kind = str(att.get("kind", ""))
        a = attestors.get(kind)
        if a is None:
            results.append(AttestationResult(kind=kind or "?", ok=False, level="none", detail="no verifier for this kind"))
            continue
        results.append(a.verify(statement, att))
    return results


def compute_assurance_level(base_level: str, results: Sequence[AttestationResult]) -> str:
    """Levels are only ever raised by *verified* attestations, never by client claims."""
    level = base_level if base_level in LEVELS else "none"
    for r in results:
        if r.ok and LEVELS.index(r.level) == LEVELS.index(level) + 1:
            level = r.level
    # A second pass lets L2 + L3 attestations arrive in any order.
    for r in results:
        if r.ok and LEVELS.index(r.level) == LEVELS.index(level) + 1:
            level = r.level
    return level
