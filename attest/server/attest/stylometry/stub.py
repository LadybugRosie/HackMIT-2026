"""Deterministic local stand-in so the reconciliation path can be exercised without a
network or a real stylometry engine. Verdict depends only on (author_id, text) so demos
and tests are repeatable."""
from __future__ import annotations

import hashlib
from typing import Optional

from .base import StylometryResult

MIN_WORDS = 50


class StubStylometryClient:
    backend = "stub"

    def verify(self, text: str, author_id: str, course_id: Optional[str] = None) -> StylometryResult:
        words = len(text.split())
        if words < MIN_WORDS:
            return StylometryResult("unknown", None, self.backend, f"needs {MIN_WORDS}+ words ({words})")
        digest = hashlib.sha256(f"{author_id}:{text}".encode("utf-8")).digest()
        score = 0.5 + (digest[0] / 255) * 0.5          # 0.5–1.0, deterministic
        verdict = "verified" if score >= 0.6 else "flagged"
        return StylometryResult(verdict, round(score, 3), self.backend, "stub — replace via ATTEST_STYLOMETRY_BASE",
                                {"words": words, "author_id": author_id, "course_id": course_id})
