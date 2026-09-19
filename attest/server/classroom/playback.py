"""Turn a ledger into a playback payload: text events labelled with provenance, plus pauses.

Origins come from the same PieceTable the integrity analysis uses, applied event by event,
so the replay a teacher watches colours spans exactly as the mix bar counts them.
"""
from __future__ import annotations

from typing import Any, Dict, List

from attest.provenance import PieceTable
from attest.replay import replay
from attest.storage.base import SessionRecord

PAUSE_MS = 800
TEXT_KINDS = ("type", "paste", "ckpt")


def build_playback(rec: SessionRecord) -> Dict[str, Any]:
    table = PieceTable()
    events: List[Dict[str, Any]] = []
    pauses: List[Dict[str, int]] = []
    counts = {"keystroke_events": 0, "paste_events": 0, "internal_paste_events": 0, "deletion_events": 0, "checkpoints": 0}
    prev = None
    for ev in rec.events:
        table.apply(ev)
        kind = ev.get("k")
        if kind not in TEXT_KINDS:
            continue
        ts, p, d, text = int(ev["ts"]), int(ev.get("p", 0)), int(ev.get("d", 0)), ev.get("i") or ""
        if kind == "type":
            origin = "T"
            counts["keystroke_events"] += 1
        elif kind == "ckpt":
            origin = "EXT"
            counts["checkpoints"] += 1
        else:
            origin = _origin_at(table, p) if text else "EXT"
            counts["paste_events"] += 1
            if origin == "INT":
                counts["internal_paste_events"] += 1
        if d:
            counts["deletion_events"] += 1
        if prev is not None and ts - prev["ts"] > PAUSE_MS:
            pauses.append({"after_seq": prev["seq"], "ms": ts - prev["ts"]})
        out = {"seq": ev["seq"], "ts": ts, "k": kind, "p": p, "d": d, "i": text, "origin": origin}
        events.append(out)
        prev = out

    mix = table.composition()
    return {
        "session_id": rec.session_id,
        "genesis": rec.genesis,
        "final_text": replay(rec.events),
        "duration_ms": (events[-1]["ts"] - events[0]["ts"]) if events else 0,
        "events": events,
        "pauses": pauses,
        "summary": {**counts, "pauses": len(pauses), "ext_chars": round(mix["external"] * table.length),
                    "int_chars": round(mix["internal"] * table.length), "typed_chars": round(mix["typed"] * table.length),
                    "final_chars": table.length},
    }


def _origin_at(table: PieceTable, pos: int) -> str:
    for pc in table.pieces:
        if pc.start <= pos < pc.end:
            return pc.origin
    return "EXT"
