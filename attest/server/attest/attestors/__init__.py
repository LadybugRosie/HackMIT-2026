"""Attestation verifiers (Stages 3–4). Each attestor checks one kind of signature over a
chain head and reports the assurance level it can vouch for. Register new kinds in ATTESTORS.

    L0  chain valid                 L2  + device-signed checkpoints (webauthn / secure_enclave)
    L1  + document bound (Stage 1)  L3  + hardware-origin keystrokes (hid)
"""
from __future__ import annotations

from .base import AttestationResult, Attestor, compute_assurance_level, verify_attestations

ATTESTORS: dict[str, Attestor] = {}


def register(kind: str, attestor: Attestor) -> None:
    ATTESTORS[kind] = attestor


__all__ = ["ATTESTORS", "AttestationResult", "Attestor", "compute_assurance_level", "register", "verify_attestations"]
