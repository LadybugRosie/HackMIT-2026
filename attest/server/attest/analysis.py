"""Provenance → signals → scoring, in one call. Pure: no store, no I/O."""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .models import IntegrityResponse, Mix, Span
from .scoring import aggregate, build_warnings, composition_scores
from .signals import build_context, run_all


def analyze(events: Sequence[Mapping[str, Any]], text: Optional[str] = None) -> IntegrityResponse:
    ctx = build_context(events, text)
    signals = run_all(ctx)
    verdict, confidence = aggregate(signals)
    mix = ctx.composition
    return IntegrityResponse(
        scores=composition_scores(mix),
        mix=Mix(**mix),
        ext_spans=[Span(start=s, end=e) for s, e in ctx.table.external_spans()],
        signals=signals,
        verdict=verdict,
        confidence=confidence,
        warnings=build_warnings(mix, signals, verdict),
        coverage={
            "events": len(events),
            "typed_events": len(ctx.type_events),
            "timed_keystrokes": len(ctx.keystroke_ts),
            "timing_source": ctx.timing_source,
            "measured_signals": sum(1 for s in signals if s.verdict != "insufficient_data"),
            "total_signals": len(signals),
        },
    )
