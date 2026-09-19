"""Standard-library-only cryptography needed to *verify* attestations (Stage 3).

Nothing here is used to protect secrets on the server: the private keys live in the student's
Secure Enclave / authenticator and in the timestamp authority's HSM. We only ever check
signatures, so a small, readable, auditable implementation beats a dependency — and it lets the
offline verifier CLI stay stdlib-only.

    p256.py     ECDSA over NIST P-256 (verify; sign only for tests / fake authenticators)
    der.py      minimal ASN.1 DER reader/writer (RFC 3161 requests and responses, X.509 keys)
    cbor.py     minimal CBOR decoder (WebAuthn attestationObject / COSE keys)
    rsa.py      RSASSA-PKCS1-v1_5 verify (timestamp authority signatures)
"""
