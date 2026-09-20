from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATTEST_", env_file=".env", extra="ignore")

    STORE: str = "memory"  # memory | sqlite (Stage 2)
    SQLITE_PATH: str = "./attest.db"
    CORS_ORIGINS: List[str] = ["http://localhost:9100", "http://127.0.0.1:9100"]
    MAX_EVENTS_PER_BATCH: int = 5000
    MAX_EVENT_TEXT_CHARS: int = 200_000
    STYLOMETRY_BASE: str = ""  # empty -> deterministic local stub (Stage 5)

    # Issuer key: the server's seal on every certificate. Empty -> ephemeral key (tests).
    ISSUER_KEY_PATH: str = "./data/attest-issuer-key.json"

    # Stage 3 (L2): device attestation via WebAuthn + RFC 3161 timestamps
    WEBAUTHN_RP_ID: str = "localhost"          # must be the origin's host (or a registrable suffix of it)
    WEBAUTHN_RP_NAME: str = "attest"
    WEBAUTHN_ORIGINS: List[str] = ["http://localhost:9100", "http://localhost:8090"]
    TSA_URL: str = "https://freetsa.org/tsr"   # empty string disables trusted timestamps
    TSA_TIMEOUT_S: float = 8.0
    TSA_TRUSTED_FINGERPRINTS: List[str] = []   # extra TSA signer-cert SHA-256s beyond the built-in list

    # Stage 4 (L3): hardware witness helper (native/attest-hid)
    HID_TRUSTED_CDHASHES: List[str] = []       # code-directory hashes of accepted helper builds; empty = accept any, flag unverified


settings = Settings()
