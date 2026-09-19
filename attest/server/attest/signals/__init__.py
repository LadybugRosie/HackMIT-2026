"""Pluggable statistical signals. Add a module with a `SignalFn` and list it in SIGNALS."""
from __future__ import annotations

from typing import Callable, List

from ..models import Signal
from .context import SessionContext, build_context
from .cadence import transcription_cadence
from .effort import edit_locality, revision_effort
from .speed import typed_speed
from .timing import inter_key_interval

SignalFn = Callable[[SessionContext], Signal]

SIGNALS: List[SignalFn] = [
    inter_key_interval,
    typed_speed,
    transcription_cadence,
    revision_effort,
    edit_locality,
]


def run_all(ctx: SessionContext) -> List[Signal]:
    return [fn(ctx) for fn in SIGNALS]


__all__ = ["SIGNALS", "SignalFn", "SessionContext", "build_context", "run_all"]
