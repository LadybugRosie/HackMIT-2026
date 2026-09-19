"""Inter-key interval distribution: humans are irregular; scripts are metronomic or superhuman."""
from __future__ import annotations

import statistics

from ..models import Signal
from .context import SessionContext

MIN_INTERVALS = 30
MAX_INTERVAL_MS = 5000          # longer gaps are pauses, not typing rhythm
UNIFORM_CV = 0.15               # coefficient of variation below this is not a hand
SUPERHUMAN_MEDIAN_MS = 40


def inter_key_interval(ctx: SessionContext) -> Signal:
    ts = ctx.keystroke_ts
    ikis = [b - a for a, b in zip(ts, ts[1:]) if 0 <= b - a <= MAX_INTERVAL_MS]
    if len(ikis) < MIN_INTERVALS:
        return Signal(name="inter_key_interval", verdict="insufficient_data", confidence=0.0,
                      label=f"Need {MIN_INTERVALS}+ timed keystrokes ({len(ikis)} so far)",
                      data={"n": len(ikis), "source": ctx.timing_source})
    median = statistics.median(ikis)
    mean = statistics.fmean(ikis)
    cv = (statistics.pstdev(ikis) / mean) if mean else 0.0
    data = {"n": len(ikis), "median_ms": round(median, 1), "cv": round(cv, 3), "source": ctx.timing_source}

    if cv < UNIFORM_CV:
        return Signal(name="inter_key_interval", verdict="suspicious", confidence=0.8,
                      label=f"Keystroke intervals unusually uniform (CV {cv:.2f}) — consistent with scripted input", data=data)
    if median < SUPERHUMAN_MEDIAN_MS:
        return Signal(name="inter_key_interval", verdict="suspicious", confidence=0.75,
                      label=f"Median interval {median:.0f} ms is below the human range", data=data)
    if cv < 0.3 or median < 70:
        return Signal(name="inter_key_interval", verdict="review", confidence=0.5,
                      label=f"Typing rhythm is very regular (median {median:.0f} ms, CV {cv:.2f})", data=data)
    return Signal(name="inter_key_interval", verdict="genuine", confidence=min(0.95, 0.5 + len(ikis) / 400),
                  label=f"Natural keystroke variability (median {median:.0f} ms, CV {cv:.2f})", data=data)
