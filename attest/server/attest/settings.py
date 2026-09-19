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


settings = Settings()
