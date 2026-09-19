"""HTTP client for an external stylometry service exposing POST {base}/course/verify with
{student_id, class_id, submission_text} → {verdict, cosine_score, ...}. Any failure is an
`unknown` result, never an exception: reconciliation must degrade, not block."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from .base import StylometryResult


class HttpStylometryClient:
    backend = "http"

    def __init__(self, base: str, timeout_s: float = 8.0) -> None:
        self.base = base.rstrip("/")
        self.timeout_s = timeout_s

    def verify(self, text: str, author_id: str, course_id: Optional[str] = None) -> StylometryResult:
        body = json.dumps({"student_id": author_id, "class_id": course_id or "default",
                           "submission_text": text, "absorb": False}).encode("utf-8")
        req = urllib.request.Request(f"{self.base}/course/verify", data=body, method="POST",
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                payload = json.load(r)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            return StylometryResult("unknown", None, self.backend, f"unreachable: {exc}")
        verdict = payload.get("verdict")
        if verdict not in ("verified", "flagged"):
            verdict = "unknown"
        return StylometryResult(verdict, payload.get("cosine_score"), self.backend, "", payload)
