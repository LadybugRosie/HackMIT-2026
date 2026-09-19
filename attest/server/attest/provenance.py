"""Piece table that tracks where every span of the document came from.

Origins: T (typed), INT (pasted text that was copied from this document within the last
30 s), EXT (pasted from outside, or restored via checkpoint). The client's `src` hint is
ignored here — internal-ness is re-derived from `copy` events in the ledger itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

INTERNAL_COPY_WINDOW_MS = 30_000
ORIGINS = ("T", "INT", "EXT")
_BOUNDARY = " \n\t.,;:!?"


@dataclass
class Piece:
    start: int
    end: int
    origin: str
    source_id: Optional[str] = None
    ts: int = 0

    @property
    def length(self) -> int:
        return self.end - self.start

    def shifted(self, delta: int) -> "Piece":
        return Piece(self.start + delta, self.end + delta, self.origin, self.source_id, self.ts)


class PieceTable:
    def __init__(self) -> None:
        self.pieces: List[Piece] = []
        self.length = 0
        self._copies: List[Tuple[int, str]] = []
        self._paste_n = 0

    # -- event application ------------------------------------------------------------

    def apply(self, ev: Mapping[str, Any]) -> None:
        kind = ev.get("k")
        ts = int(ev.get("ts", 0))
        if kind == "copy":
            self._copies.append((ts, ev.get("i") or ""))
            return
        if kind == "ckpt":
            text = ev.get("i") or ""
            self.pieces = [Piece(0, len(text), "EXT", "ckpt", ts)] if text else []
            self.length = len(text)
            return
        if kind not in ("type", "paste"):
            return
        p, d, ins = int(ev.get("p", 0)), int(ev.get("d", 0)), ev.get("i") or ""
        if d:
            self.delete(p, d)
        if ins:
            if kind == "type":
                origin, source = "T", None
            else:
                origin, source = self._classify_paste(ins, ts)
            self.insert(p, len(ins), origin, source, ts)

    def apply_all(self, events: Iterable[Mapping[str, Any]]) -> "PieceTable":
        for ev in events:
            self.apply(ev)
        return self

    def _classify_paste(self, text: str, ts: int) -> Tuple[str, str]:
        self._paste_n += 1
        needle = text.strip()
        for copy_ts, copied in reversed(self._copies):
            if ts - copy_ts > INTERNAL_COPY_WINDOW_MS:
                break
            if needle and copied.strip() == needle:
                return "INT", f"copy@{copy_ts}"
        return "EXT", f"paste#{self._paste_n}"

    # -- structural edits -------------------------------------------------------------

    def insert(self, pos: int, n: int, origin: str, source_id: Optional[str], ts: int) -> None:
        if n <= 0:
            return
        if pos < 0 or pos > self.length:
            raise ValueError(f"insert at {pos} outside [0, {self.length}]")
        new_piece = Piece(pos, pos + n, origin, source_id, ts)
        out: List[Piece] = []
        placed = False
        for pc in self.pieces:
            if placed:
                out.append(pc.shifted(n))
            elif pos <= pc.start:
                out.append(new_piece)
                out.append(pc.shifted(n))
                placed = True
            elif pc.start < pos < pc.end:
                out.append(Piece(pc.start, pos, pc.origin, pc.source_id, pc.ts))
                out.append(new_piece)
                out.append(Piece(pos + n, pc.end + n, pc.origin, pc.source_id, pc.ts))
                placed = True
            else:
                out.append(pc)
        if not placed:
            out.append(new_piece)
        self.pieces = self._merge(out)
        self.length += n

    def delete(self, pos: int, n: int) -> None:
        if n <= 0:
            return
        end = pos + n
        if pos < 0 or end > self.length:
            raise ValueError(f"delete [{pos}, {end}) outside [0, {self.length}]")
        out: List[Piece] = []
        for pc in self.pieces:
            if pc.end <= pos:
                out.append(pc)
            elif pc.start >= end:
                out.append(pc.shifted(-n))
            else:
                if pc.start < pos:
                    out.append(Piece(pc.start, pos, pc.origin, pc.source_id, pc.ts))
                if pc.end > end:
                    out.append(Piece(pos, pc.end - n, pc.origin, pc.source_id, pc.ts))
        self.pieces = self._merge(out)
        self.length -= n

    @staticmethod
    def _merge(pieces: List[Piece]) -> List[Piece]:
        merged: List[Piece] = []
        for pc in pieces:
            if pc.length <= 0:
                continue
            last = merged[-1] if merged else None
            if last and last.end == pc.start and last.origin == pc.origin and last.source_id == pc.source_id:
                last.end = pc.end
            else:
                merged.append(Piece(pc.start, pc.end, pc.origin, pc.source_id, pc.ts))
        return merged

    # -- read-outs --------------------------------------------------------------------

    def composition(self) -> Dict[str, float]:
        totals = {o: 0 for o in ORIGINS}
        for pc in self.pieces:
            totals[pc.origin] += pc.length
        if self.length == 0:
            return {"typed": 0.0, "internal": 0.0, "external": 0.0}
        return {
            "typed": totals["T"] / self.length,
            "internal": totals["INT"] / self.length,
            "external": totals["EXT"] / self.length,
        }

    def external_spans(self) -> List[Tuple[int, int]]:
        return [(pc.start, pc.end) for pc in self.pieces if pc.origin == "EXT"]

    def paste_count(self) -> int:
        return self._paste_n
