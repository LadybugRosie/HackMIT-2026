"""Attestation verifiers (Stages 3–4). Each attestor checks one kind of signature over a
chain head and reports the assurance level it can vouch for.

    L0  chain valid                 L2  + device-signed head (webauthn), trusted timestamps enrich
    L1  + document bound (Stage 1)  L3  + hardware witness: physical key-downs agree with the ledger (hid)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional

from .base import AttestationResult, Attestor, compute_assurance_level, verify_attestations
from .hid import HidAttestor
from .policy import LEVEL_CHAIN_VALID, LEVEL_DEVICE_BOUND, LEVEL_DOC_BOUND, LEVEL_HARDWARE_WITNESS, assess_attestations
from .timestamp import KNOWN_TSAS, TimestampAttestor
from .webauthn import WebAuthnAttestor


def server_attestors(rp_id: str, origins, lookup: Callable[[str], Optional[Mapping[str, Any]]],
                     extra_tsa_fingerprints=()) -> Dict[str, Attestor]:
    """Authoritative verifiers for the issuing server: enforce RP/origin policy and look keys up."""
    return {"webauthn": WebAuthnAttestor(rp_id, origins, lookup), "timestamp": TimestampAttestor(extra_tsa_fingerprints),
            "hid": HidAttestor(lookup)}


def offline_attestors(extra_tsa_fingerprints=()) -> Dict[str, Attestor]:
    """Verifiers for a certificate in hand: keys and RP come from the attestation records themselves."""
    return {"webauthn": WebAuthnAttestor(None, None, None), "timestamp": TimestampAttestor(extra_tsa_fingerprints),
            "hid": HidAttestor(None)}


__all__ = ["AttestationResult", "Attestor", "HidAttestor", "KNOWN_TSAS", "LEVEL_HARDWARE_WITNESS", "LEVEL_CHAIN_VALID", "LEVEL_DEVICE_BOUND", "LEVEL_DOC_BOUND", "assess_attestations", "TimestampAttestor", "WebAuthnAttestor",
           "compute_assurance_level", "offline_attestors", "server_attestors", "verify_attestations"]
