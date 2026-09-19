"""Revision effort and edit locality: composing leaves fingerprints of rework; transcribing
and pasting are monotonic, forward-only, and low-effort relative to the final length."""
from __future__ import annotations

from ..models import Signal
from .context import SessionContext

MIN_FINAL_CHARS = 40
MIN_EDITS = 40


def revision_effort(ctx: SessionContext) -> Signal:
    final = len(ctx.text)
    if final < MIN_FINAL_CHARS:
        return Signal(name="revision_effort", verdict="insufficient_data", confidence=0.0,
                      label="Document too short to judge effort", data={"final_chars": final})
    typed = sum(len(e.get("i") or "") for e in ctx.type_events)
    deleted = sum(int(e.get("d", 0)) for e in ctx.text_events)
    ratio = (typed + deleted) / final
    data = {"typed_chars": typed, "deleted_chars": deleted, "final_chars": final, "ratio": round(ratio, 2)}
    if ratio >= 1.1:
        return Signal(name="revision_effort", verdict="genuine", confidence=0.7,
                      label=f"{ratio:.2f}× keystrokes per final character — visible revision", data=data)
    if ratio >= 0.85:
        return Signal(name="revision_effort", verdict="review", confidence=0.4,
                      label=f"Little revision ({ratio:.2f}× keystrokes per final character)", data=data)
    return Signal(name="revision_effort", verdict="suspicious", confidence=0.6,
                  label=f"Only {ratio:.2f}× keystrokes per final character — most text was not typed here", data=data)


def edit_locality(ctx: SessionContext) -> Signal:
    """Fraction of edits that touch text *before* the tail of the document."""
    running = 0
    total = backward = 0
    for e in ctx.text_events:
        k = e.get("k")
        if k == "ckpt":
            running = len(e.get("i") or "")
            continue
        p, d, ins = int(e.get("p", 0)), int(e.get("d", 0)), len(e.get("i") or "")
        total += 1
        if p + d < running:
            backward += 1
        running += ins - d
    if total < MIN_EDITS:
        return Signal(name="edit_locality", verdict="insufficient_data", confidence=0.0,
                      label=f"Need {MIN_EDITS}+ edits to judge ({total} so far)", data={"edits": total})
    ratio = backward / total
    data = {"edits": total, "backward_edits": backward, "backward_ratio": round(ratio, 3)}
    if ratio >= 0.05:
        return Signal(name="edit_locality", verdict="genuine", confidence=0.6,
                      label=f"{ratio:.0%} of edits revisit earlier text", data=data)
    if ratio >= 0.01:
        return Signal(name="edit_locality", verdict="review", confidence=0.4,
                      label=f"Almost strictly linear writing ({ratio:.1%} backward edits)", data=data)
    return Signal(name="edit_locality", verdict="suspicious", confidence=0.55,
                  label="Strictly forward, append-only writing with no revisits", data=data)
