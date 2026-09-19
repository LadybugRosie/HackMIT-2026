from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..provenance import PieceTable
from ..replay import replay

MIN_KEYDOWNS_FOR_TIMING = 20


@dataclass
class SessionContext:
    events: Sequence[Mapping[str, Any]]
    text: str
    table: PieceTable
    composition: Dict[str, float]
    type_events: List[Mapping[str, Any]] = field(default_factory=list)
    text_events: List[Mapping[str, Any]] = field(default_factory=list)  # type + paste + ckpt
    keystroke_ts: List[int] = field(default_factory=list)
    timing_source: str = "none"  # keydown | edits | none


def build_context(events: Sequence[Mapping[str, Any]], text: Optional[str] = None) -> SessionContext:
    if text is None:
        text = replay(events)
    table = PieceTable().apply_all(events)
    type_events = [e for e in events if e.get("k") == "type"]
    text_events = [e for e in events if e.get("k") in ("type", "paste", "ckpt")]
    keydowns = sorted(int(e["ts"]) for e in events if e.get("k") == "kd")
    if len(keydowns) >= MIN_KEYDOWNS_FOR_TIMING:
        keystroke_ts, source = keydowns, "keydown"
    else:
        keystroke_ts, source = sorted(int(e["ts"]) for e in type_events), "edits"
    return SessionContext(
        events=events, text=text, table=table, composition=table.composition(),
        type_events=type_events, text_events=text_events,
        keystroke_ts=keystroke_ts, timing_source=source if keystroke_ts else "none",
    )
