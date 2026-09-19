"""Aggregate composition + signals into scores, an overall verdict and neutral warnings.

Innocence-protecting by construction: `suspicious` needs several weighted votes, and any
verdict is downgraded to `review` when too little could be measured.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .models import IntegrityWarning, Scores, Signal

WEIGHTS: Dict[str, float] = {
    "inter_key_interval": 1.0,
    "typed_speed": 1.5,
    "transcription_cadence": 1.5,
    "revision_effort": 1.0,
    "edit_locality": 0.75,
}
DEFAULT_WEIGHT = 0.5
EXTERNAL_WARN_RATIO = 0.3


def composition_scores(mix: Dict[str, float]) -> Scores:
    penalty = min(40, round(100 * mix.get("external", 0.0)))
    return Scores(trust=100 - penalty, composition=round(100 * mix.get("typed", 0.0)))


def aggregate(signals: Sequence[Signal]) -> Tuple[str, float]:
    if not signals:
        return "insufficient_data", 0.0
    genuine_w = suspicious_w = 0.0
    genuine_n = suspicious_n = no_data = 0
    for s in signals:
        w = WEIGHTS.get(s.name, DEFAULT_WEIGHT)
        if s.verdict == "genuine":
            genuine_w += w; genuine_n += 1
        elif s.verdict == "suspicious":
            suspicious_w += w; suspicious_n += 1
        elif s.verdict == "insufficient_data":
            no_data += 1
    if no_data >= 3:
        return "review", 0.3
    if suspicious_w >= 2.0 and suspicious_n >= 2:
        return "suspicious", round(suspicious_w / (suspicious_w + genuine_w + 0.01), 2)
    if genuine_n >= 4 and suspicious_n == 0:
        return "genuine", round(min(0.95, genuine_n / len(signals)), 2)
    if suspicious_n >= 1 or (genuine_n < 3):
        return "review", 0.5
    return "genuine", round(min(0.95, genuine_w / (suspicious_w + genuine_w + 0.01)), 2)


def build_warnings(mix: Dict[str, float], signals: Sequence[Signal], verdict: str) -> List[IntegrityWarning]:
    out: List[IntegrityWarning] = []
    ext = mix.get("external", 0.0)
    if ext >= EXTERNAL_WARN_RATIO:
        out.append(IntegrityWarning(severity="medium", code="external_content",
                                    reason=f"{ext:.0%} of the current text was pasted from outside this document"))
    for s in signals:
        if s.verdict == "suspicious":
            out.append(IntegrityWarning(severity="high", code=s.name, reason=s.label))
    if verdict == "review" and not out:
        out.append(IntegrityWarning(severity="low", code="needs_review",
                                    reason="Some process signals could not be measured or were mixed — not enough evidence either way"))
    return out
