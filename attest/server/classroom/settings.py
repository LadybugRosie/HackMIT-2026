from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class ClassroomSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLASSROOM_", env_file=".env", extra="ignore")

    DB_PATH: str = "./data/classroom.db"  # shared with the attest ledger tables
    CORS_ORIGINS: List[str] = ["http://localhost:9100", "http://127.0.0.1:9100"]
    TOKEN_TTL_DAYS: int = 14
    SCRYPT_N: int = 2**14
    CROSSREF_MAILTO: str = ""
    HTTP_TIMEOUT_S: float = 6.0
    SIMILARITY_K: int = 5
    SIMILARITY_W: int = 4


settings = ClassroomSettings()
