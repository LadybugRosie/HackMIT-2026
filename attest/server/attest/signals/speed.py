"""Typed-only words-per-minute in sliding windows. Pastes are excluded — provenance already
reports them — so this catches text that *claims* to be typed but arrived too fast."""
from __future__ import annotations

from ..models import Signal
from .context import SessionContext

WINDOW_MS = 10_000
MIN_CHARS_PER_WINDOW = 20
REVIEW_WPM = 140
SUSPICIOUS_WPM = 200


def typed_speed(ctx: SessionContext) -> Signal:
    evs = ctx.type_events
    if not evs:
        return Signal(name="typed_speed", verdict="insufficient_data", confidence=0.0,
                      label="No typed text yet", data={"windows": 0})
    t0 = int(evs[0]["ts"])
    buckets: dict[int, int] = {}
    for e in evs:
        buckets[(int(e["ts"]) - t0) // WINDOW_MS] = buckets.get((int(e["ts"]) - t0) // WINDOW_MS, 0) + len(e.get("i") or "")
    wpms = [chars / 5 * (60_000 / WINDOW_MS) for chars in buckets.values() if chars >= MIN_CHARS_PER_WINDOW]
    if not wpms:
        return Signal(name="typed_speed", verdict="insufficient_data", confidence=0.0,
                      label="Not enough typing in any 10 s window yet", data={"windows": len(buckets)})
    peak = max(wpms)
    data = {"windows": len(buckets), "measured_windows": len(wpms), "peak_typed_wpm": round(peak),
            "median_typed_wpm": round(sorted(wpms)[len(wpms) // 2]), "pastes": ctx.table.paste_count()}
    if peak > SUSPICIOUS_WPM:
        return Signal(name="typed_speed", verdict="suspicious", confidence=0.8,
                      label=f"Typed text arrived at {peak:.0f} WPM — beyond plausible human typing", data=data)
    if peak > REVIEW_WPM:
        return Signal(name="typed_speed", verdict="review", confidence=0.5,
                      label=f"Peak typing burst of {peak:.0f} WPM", data=data)
    return Signal(name="typed_speed", verdict="genuine", confidence=0.7,
                  label=f"Typing speed within human range (peak {peak:.0f} WPM)", data=data)
