"""Password hashing (stdlib scrypt) and opaque bearer tokens stored only as SHA-256 digests."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Tuple

SCRYPT_R = 8
SCRYPT_P = 1
DKLEN = 32


def hash_password(password: str, n: int = 2**14) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=SCRYPT_R, p=SCRYPT_P, dklen=DKLEN)
    return f"scrypt${n}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest_hex)))
        return hmac.compare_digest(digest, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def mint_token() -> Tuple[str, str]:
    """Returns (token handed to the client, digest stored in the database)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)
