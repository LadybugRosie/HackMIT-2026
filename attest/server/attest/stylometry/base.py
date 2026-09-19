from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Protocol

StyloVerdict = Literal["verified", "flagged", "unknown"]


@dataclass
class StylometryResult:
    verdict: StyloVerdict
    score: Optional[float] = None       # similarity to the author's profile, 0–1, if the backend gives one
    backend: str = ""
    detail: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class StylometryClient(Protocol):
    backend: str

    def verify(self, text: str, author_id: str, course_id: Optional[str] = None) -> StylometryResult: ...
