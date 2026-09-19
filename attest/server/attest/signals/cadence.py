"""Composition vs. transcription cadence.

Someone composing pauses to think at word/clause boundaries and types bursts of very
variable length. Someone copying from a second screen pauses wherever their working
memory runs out — roughly every 5–15 characters, regardless of syntax — so pauses land
mid-word and burst lengths cluster tightly.
"""
from __future__ import annotations

import statistics

from ..models import Signal
from .context import SessionContext

PAUSE_MS = 800
MIN_PAUSES = 12
BOUNDARY_CHARS = set(" \n\t.,;:!?—-\"')")
LOW_BOUNDARY_RATIO = 0.35
REVIEW_BOUNDARY_RATIO = 0.5
LOW_BURST_CV = 0.5


def transcription_cadence(ctx: SessionContext) -> Signal:
    evs = [e for e in ctx.type_events if e.get("i")]
    pauses = boundaries = 0
    burst_lengths: list[int] = []
    burst = 0
    for prev, cur in zip(evs, evs[1:]):
        burst += len(prev["i"])
        if int(cur["ts"]) - int(prev["ts"]) > PAUSE_MS:
            pauses += 1
            if prev["i"][-1] in BOUNDARY_CHARS:
                boundaries += 1
            burst_lengths.append(burst)
            burst = 0
    if pauses < MIN_PAUSES:
        return Signal(name="transcription_cadence", verdict="insufficient_data", confidence=0.0,
                      label=f"Need {MIN_PAUSES}+ thinking pauses to judge cadence ({pauses} so far)",
                      data={"pauses": pauses})
    boundary_ratio = boundaries / pauses
    mean_burst = statistics.fmean(burst_lengths)
    burst_cv = statistics.pstdev(burst_lengths) / mean_burst if mean_burst else 0.0
    data = {"pauses": pauses, "boundary_ratio": round(boundary_ratio, 3), "mean_burst_chars": round(mean_burst, 1),
            "burst_cv": round(burst_cv, 3)}
    confidence = min(0.9, 0.4 + pauses / 100)

    if boundary_ratio < LOW_BOUNDARY_RATIO and burst_cv < LOW_BURST_CV:
        return Signal(name="transcription_cadence", verdict="suspicious", confidence=confidence,
                      label=f"Pauses fall mid-word ({boundary_ratio:.0%} at boundaries) in steady ~{mean_burst:.0f}-char chunks — a transcription-like rhythm",
                      data=data)
    if boundary_ratio < REVIEW_BOUNDARY_RATIO or burst_cv < LOW_BURST_CV:
        return Signal(name="transcription_cadence", verdict="review", confidence=confidence * 0.7,
                      label=f"Mixed cadence: {boundary_ratio:.0%} of pauses at boundaries, burst variability {burst_cv:.2f}",
                      data=data)
    return Signal(name="transcription_cadence", verdict="genuine", confidence=confidence,
                  label=f"Pauses land at word/clause boundaries ({boundary_ratio:.0%}) with variable bursts — composition-like",
                  data=data)
