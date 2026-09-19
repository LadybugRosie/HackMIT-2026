"""Deterministic replay of the event stream into document text.

Text-mutating kinds: type / paste (replace `d` code points at `p` with `i`), ckpt (reset to `i`).
Every other kind (copy, kd, ku) is a no-op for the document but still part of the chain.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

TEXT_KINDS = ("type", "paste")


class ReplayError(ValueError):
    def __init__(self, index: int, message: str):
        super().__init__(f"event {index}: {message}")
        self.index = index


def apply_event(text: str, ev: Mapping[str, Any], index: int = -1) -> str:
    kind = ev.get("k")
    if kind == "ckpt":
        return ev.get("i") or ""
    if kind in TEXT_KINDS:
        p, d = int(ev.get("p", 0)), int(ev.get("d", 0))
        if p < 0 or d < 0 or p > len(text) or p + d > len(text):
            raise ReplayError(index, f"edit out of range (p={p}, d={d}, len={len(text)})")
        return text[:p] + (ev.get("i") or "") + text[p + d:]
    return text


def replay(events: Iterable[Mapping[str, Any]], initial: str = "") -> str:
    text = initial
    for idx, ev in enumerate(events):
        text = apply_event(text, ev, idx)
    return text
