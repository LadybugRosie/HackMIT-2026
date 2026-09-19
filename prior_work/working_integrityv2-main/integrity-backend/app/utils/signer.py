"""Cryptographic signing for integrity verification"""
import os
import hmac
import hashlib
import base64
import json
from typing import Dict, Any


# FIX #6: No hardcoded fallback -- require env var in production
_raw_key = os.getenv("INTEGRITY_SIGNING_KEY")
if not _raw_key:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("CRITICAL: INTEGRITY_SIGNING_KEY must be set in production!")
    _raw_key = "dev-key-DO-NOT-USE-" + os.urandom(16).hex()  # Random per-process in dev
    print(f"WARNING: INTEGRITY_SIGNING_KEY not set. Using random dev key (signatures won't persist across restarts).")
SIGNING_KEY = _raw_key.encode('utf-8')


def sign(payload: Dict[str, Any]) -> str:
    """Sign a payload using HMAC-SHA256"""
    # Sort keys for consistent hashing
    sorted_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    
    # Create HMAC signature
    signature = hmac.new(
        SIGNING_KEY,
        sorted_payload.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # Return base64 encoded signature
    return base64.b64encode(signature).decode('utf-8')


def verify(payload: Dict[str, Any], signature: str) -> bool:
    """Verify a payload signature"""
    try:
        expected_signature = sign(payload)
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        print(f"⚠️ Signature verification error: {e}")
        return False


def create_signed_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a signed response payload"""
    signature = sign(payload)
    return {
        **payload,
        "signature": signature,
        "verified": True
    }

