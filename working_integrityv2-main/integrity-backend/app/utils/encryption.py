"""
Encryption Utilities
Secure handling of sensitive data like API keys
"""

import os
import base64
import hashlib
import secrets
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# ============================================================================
# KEY DERIVATION
# ============================================================================

def get_encryption_key() -> bytes:
    """
    Get or generate the encryption key from environment
    Uses PBKDF2 to derive a key from the secret
    """
    secret = os.getenv("ENCRYPTION_SECRET")
    
    # FIX #6: No hardcoded fallback secrets
    if not secret:
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError("CRITICAL: ENCRYPTION_SECRET must be set in production!")
        secret = secrets.token_hex(32)
        print(f"WARNING: No ENCRYPTION_SECRET set. Generated temporary key (won't persist across restarts).")
    
    salt_env = os.getenv("ENCRYPTION_SALT")
    if not salt_env:
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError("CRITICAL: ENCRYPTION_SALT must be set in production!")
        salt_env = "dev-salt-" + secrets.token_hex(8)
        print(f"WARNING: No ENCRYPTION_SALT set. Using temporary salt.")
    salt = salt_env.encode()
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key


# Global Fernet instance
_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Get the Fernet encryption instance"""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


# ============================================================================
# ENCRYPTION FUNCTIONS
# ============================================================================

def encrypt_value(value: str) -> str:
    """
    Encrypt a string value
    Returns base64-encoded encrypted string
    """
    if not value:
        return ""
    
    fernet = get_fernet()
    encrypted = fernet.encrypt(value.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt an encrypted string value
    Returns the original string
    """
    if not encrypted_value:
        return ""
    
    try:
        fernet = get_fernet()
        encrypted = base64.urlsafe_b64decode(encrypted_value.encode())
        decrypted = fernet.decrypt(encrypted)
        return decrypted.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""


def encrypt_api_key(api_key: str) -> dict:
    """
    Encrypt an API key with additional metadata
    Returns dict with encrypted key and verification hash
    """
    if not api_key:
        return {"encrypted": "", "hash": ""}
    
    encrypted = encrypt_value(api_key)
    
    # Store a hash of the last 4 chars for verification display
    key_hash = hashlib.sha256(api_key[-4:].encode()).hexdigest()[:8]
    
    return {
        "encrypted": encrypted,
        "hash": key_hash,
        "preview": f"...{api_key[-4:]}"  # Last 4 chars for display
    }


def decrypt_api_key(encrypted_data: dict) -> str:
    """
    Decrypt an API key from encrypted data
    """
    if not encrypted_data or not encrypted_data.get("encrypted"):
        return ""
    
    return decrypt_value(encrypted_data["encrypted"])


# ============================================================================
# HASHING FUNCTIONS
# ============================================================================

def hash_sensitive_data(data: str, salt: Optional[str] = None) -> str:
    """
    Create a one-way hash of sensitive data
    Used for data that doesn't need to be decrypted (e.g., for comparison)
    """
    if not data:
        return ""
    
    if salt is None:
        salt = os.getenv("HASH_SALT")
        if not salt:
            if os.getenv("ENVIRONMENT") == "production":
                raise RuntimeError("CRITICAL: HASH_SALT must be set in production!")
            salt = "dev-hash-salt-unsafe"
    
    salted = f"{salt}:{data}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_hash(data: str, hash_value: str, salt: Optional[str] = None) -> bool:
    """
    Verify data against a stored hash
    """
    computed_hash = hash_sensitive_data(data, salt)
    return secrets.compare_digest(computed_hash, hash_value)


# ============================================================================
# TOKEN GENERATION
# ============================================================================

def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token
    """
    return secrets.token_urlsafe(length)


def generate_numeric_code(length: int = 6) -> str:
    """
    Generate a numeric code (e.g., for verification)
    """
    return "".join(secrets.choice("0123456789") for _ in range(length))


def generate_class_code() -> str:
    """
    Generate a unique class join code
    Format: 6 alphanumeric characters (uppercase)
    """
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Exclude confusing chars
    return "".join(secrets.choice(chars) for _ in range(6))


# ============================================================================
# DATA MASKING
# ============================================================================

def mask_email(email: str) -> str:
    """
    Mask an email address for display
    john.doe@example.com -> j***e@e***e.com
    """
    if not email or "@" not in email:
        return "***@***.***"
    
    local, domain = email.split("@", 1)
    
    # Mask local part
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    
    # Mask domain
    if "." in domain:
        domain_name, tld = domain.rsplit(".", 1)
        if len(domain_name) <= 2:
            masked_domain = domain_name[0] + "***"
        else:
            masked_domain = domain_name[0] + "***" + domain_name[-1]
        masked_domain = f"{masked_domain}.{tld}"
    else:
        masked_domain = domain[0] + "***"
    
    return f"{masked_local}@{masked_domain}"


def mask_ip(ip: str) -> str:
    """
    Mask an IP address for privacy
    192.168.1.100 -> 192.168.***
    """
    if not ip:
        return "***"
    
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.***.***"
    return ip[:len(ip)//2] + "***"
