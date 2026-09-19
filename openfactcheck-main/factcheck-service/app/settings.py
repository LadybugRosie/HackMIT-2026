from enum import Enum
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvidenceMode(str, Enum):
    """
    Evidence retrieval modes:
    - REGISTRY_ONLY: DOI/URL registry verification + local knowledge (default, free)
    - OFFLINE_ONLY: No external calls, only local knowledgebase
    - HYBRID: Registry + optional web retrieval for unresolved claims
    """
    REGISTRY_ONLY = "REGISTRY_ONLY"
    OFFLINE_ONLY = "OFFLINE_ONLY"
    HYBRID = "HYBRID"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    SERVICE_NAME: str = "factcheck-service"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"

    # Redis
    REDIS_URL: str = "memory://"
    CACHE_TTL_SECONDS: int = 60 * 60 * 24 * 7  # 7 days

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Evidence mode
    EVIDENCE_MODE: EvidenceMode = EvidenceMode.REGISTRY_ONLY

    # Timeouts
    REQUEST_TIMEOUT_SECONDS: int = 180  # claim extraction headroom for long papers
    DOI_TIMEOUT_SECONDS: float = 3.0
    URL_TIMEOUT_SECONDS: float = 3.0
    # Metadata / abstract fetches (Crossref, OpenAlex, DataCite, S2, Unpaywall,
    # Wikipedia, ROR) — slower than a doi.org HEAD, and a timeout here silently
    # turns into "source could not be retrieved" / "no plausible match", i.e. a
    # missed or FALSE finding. Give them more headroom than the DOI HEAD check.
    SOURCE_FETCH_TIMEOUT_SECONDS: float = 8.0

    # Limits — sized for full academic papers / theses (built for serious authors)
    MAX_TEXT_CHARS: int = 400000          # ~66k words / ~130 pages (was 40k)
    MAX_REFERENCES_TO_CHECK: int = 300    # full bibliographies (was 50)
    MAX_URLS_TO_CHECK: int = 200          # (was 50)

    # API keys as comma-separated string (avoids JSON parsing issues with empty values)
    API_KEYS: str = ""
    # Fail closed: when True, /v1/verify REQUIRES a valid x-api-key. If API_KEYS is
    # unset the service refuses requests (503) instead of silently serving the public.
    # Set REQUIRE_API_KEY=false only for a deliberately open, non-cost-bearing deploy.
    REQUIRE_API_KEY: bool = True
    ASYNC_MODE: bool = False
    ENABLE_DOCS: bool = False  # do not expose interactive API docs by default

    # Optional features
    ENABLE_WIKIPEDIA_EVIDENCE: bool = True  # Free, low-cost evidence source
    ENABLE_OPENAI_WEBSEARCH: bool = False  # Cost control: disabled by default

    # LLM verification (OpenAI)
    ENABLE_LLM_VERIFICATION: bool = True
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5.4-mini"  # 6/6 verdict accuracy at ~30% of gpt-4o cost (see commit msg); override via env

    # Semantic Scholar
    ENABLE_SEMANTIC_SCHOLAR: bool = True
    SEMANTIC_SCHOLAR_API_KEY: str = ""

    # Confidence scoring
    ENABLE_CONFIDENCE_SCORING: bool = True

    # Claim decomposition
    ENABLE_CLAIM_DECOMPOSITION: bool = True

    # ── New hallucination-detection modules ────────────────────────────────
    # Citation-content alignment: for each cited DOI, fetch abstract via
    # OpenAlex/Unpaywall/Crossref/S2 and ask the configured backend whether
    # the source actually supports the claim. Strict-RAG, no parametric
    # memory.
    ENABLE_CITATION_ALIGNMENT: bool = True
    MAX_ALIGNMENT_DOIS: int = 150  # align far more in-text citations on long papers (was 25)
    # Full-text escalation: when an EVIDENTIAL cite's abstract verdict is weak,
    # fetch the OA full text (arXiv/Unpaywall) + re-align. Default OFF to keep
    # token cost predictable — enable in prod with ENABLE_FULLTEXT_ESCALATION=true
    # (Railway env) when the extra accuracy is wanted. The rest of the
    # citation-integrity accuracy work (function classifier, honest verdict,
    # over-flag fix) is always on and actually REDUCES tokens.
    ENABLE_FULLTEXT_ESCALATION: bool = False
    MAX_FULLTEXT_FETCHES: int = 12  # per-document budget for full-text escalations
    # Numbered-citation alignment for published papers: parse the reference
    # list, map in-text markers ([14], [2]-[5], [1,3]) to their reference
    # entries, resolve each to its real source, and align the citing sentence
    # against it. This is what lets the engine audit IEEE/journal papers where
    # the DOI lives only in the reference list, not next to the claim.
    ENABLE_NUMBERED_CITATIONS: bool = True
    # Which backend to use for citation alignment:
    #   "openai"    — gpt-4o strict-RAG (default; needs OPENAI_API_KEY).
    #   "minicheck" — Bespoke-MiniCheck-7B local HF model (highest accuracy,
    #                 SOTA on LLM-AggreFact; ~14 GB, GPU strongly recommended,
    #                 CC-BY-NC-4.0).
    #   "nli"       — MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli
    #                 (~440 MB, pure-PyTorch, MIT-style license, no
    #                 trust_remote_code; works on CPU and on macOS where the
    #                 HHEM custom loader deadlocks on abseil).
    #   "hhem"      — Vectara HHEM-2.1-Open (~600 MB, Apache-2.0). Known
    #                 hang on macOS due to Vectara's TF init path.
    #   "ensemble"  — run minicheck + nli + hhem (whichever are installed)
    #                 and average their scores.
    # Install requirements-local.txt to enable any non-openai backend.
    ALIGNMENT_BACKEND: str = "openai"
    LOCAL_MODEL_CACHE_DIR: str = "./ckpts"
    # Fabrication detectors: numeric/venue/institution/ghost-author checks
    # against OpenAlex /sources and ROR.
    ENABLE_FABRICATION_DETECTORS: bool = True
    # Bibliography ↔ in-text citation consistency
    ENABLE_BIBLIOGRAPHY_REPORT: bool = True
    # Internal numeric-consistency pass (ADDITIVE, separate stage). Scans the
    # document for figures reporting different values for the SAME quantity
    # (e.g. abstract 98.7% vs Table 94.2%). Emits its own INTERNAL_MISMATCH /
    # INTERNALLY_CONSISTENT findings; never touches the claim classifier.
    ENABLE_INTERNAL_CONSISTENCY: bool = True
    # Forensic-integrity checks (ADDITIVE, deterministic, separate field):
    # statcheck (recompute p-values), GRIM (impossible percentages/means),
    # dangling cross-references, retracted-citation screening. Zero-false-positive
    # by construction — fires only when the math/reference is provably broken.
    ENABLE_FORENSIC_CHECKS: bool = True

    def get_api_keys(self) -> List[str]:
        """Parse API_KEYS into a list."""
        if not self.API_KEYS:
            return []
        return [k.strip() for k in self.API_KEYS.split(",") if k.strip()]


settings = Settings()
