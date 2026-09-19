"""Synthetic writing sessions with distinct process fingerprints, for signal tests."""
from __future__ import annotations

import random
from typing import Any, Dict, List

T0 = 1_700_000_000_000
BOUNDARY = set(" \n.,;:!?")


def human_composition(text: str, seed: int = 1, revisions: int = 20) -> List[Dict[str, Any]]:
    """Jittery keystrokes, thinking pauses at word/clause boundaries, some backward revisions."""
    rng = random.Random(seed)
    ops: List[Dict[str, Any]] = []
    ts = T0
    for n, ch in enumerate(text):
        ts += max(40, int(rng.gauss(190, 70))) if n else 0  # strictly increasing
        if n and text[n - 1] in BOUNDARY and rng.random() < 0.45:
            ts += rng.randint(900, 3200)  # thinking pause at a boundary
        ops.append({"ts": ts, "p": n, "d": 0, "i": ch, "k": "type"})
    # Backward revisions: delete a short run somewhere earlier and re-type it (net zero change).
    for _ in range(revisions):
        k = rng.randint(1, 3)
        pos = rng.randint(0, max(0, len(text) - k - 1))
        ts += rng.randint(400, 2500)
        ops.append({"ts": ts, "p": pos, "d": k, "i": "", "k": "type"})
        for j, ch in enumerate(text[pos:pos + k]):
            ts += rng.randint(120, 320)
            ops.append({"ts": ts, "p": pos + j, "d": 0, "i": ch, "k": "type"})
    return ops


def transcription(text: str, seed: int = 2, chunk: int = 9) -> List[Dict[str, Any]]:
    """Steady ~9-char chunks with a memory-refill pause after each, regardless of syntax."""
    rng = random.Random(seed)
    ops: List[Dict[str, Any]] = []
    ts = T0
    for n, ch in enumerate(text):
        if n:
            ts += int(rng.gauss(150, 25))
            if n % chunk == 0:
                ts += rng.randint(1000, 1400)
        ops.append({"ts": ts, "p": n, "d": 0, "i": ch, "k": "type"})
    return ops


def scripted(text: str, interval_ms: int = 20) -> List[Dict[str, Any]]:
    """Injected keystrokes: metronomic and superhuman."""
    return [{"ts": T0 + interval_ms * n, "p": n, "d": 0, "i": ch, "k": "type"} for n, ch in enumerate(text)]


def paste_dump(text: str) -> List[Dict[str, Any]]:
    return [{"ts": T0, "p": 0, "d": 0, "i": text, "k": "paste", "src": "ext"}]


SAMPLE = (
    "The hash chain gives us tamper evidence, but it says nothing about who pressed the keys. "
    "That is why the second layer matters: hardware attestation tells us the input came from a "
    "physical device, and the timing statistics tell us whether the hand behind it was composing "
    "or merely copying. Neither claim is absolute, so we report levels, not verdicts of guilt."
)
