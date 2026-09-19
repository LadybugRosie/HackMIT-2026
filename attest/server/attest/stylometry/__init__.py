"""Stylometry reconciliation (Stage 5): offline-first. The ledger and certificate never wait on
this; a verdict is attached later as an addendum when a client is reachable."""
from __future__ import annotations

from ..settings import Settings
from .base import StylometryClient, StylometryResult
from .stub import StubStylometryClient


def get_client(cfg: Settings) -> StylometryClient:
    if cfg.STYLOMETRY_BASE:
        from .http import HttpStylometryClient
        return HttpStylometryClient(cfg.STYLOMETRY_BASE)
    return StubStylometryClient()


__all__ = ["StylometryClient", "StylometryResult", "StubStylometryClient", "get_client"]
