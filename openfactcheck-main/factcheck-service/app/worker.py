import asyncio
import json
import logging
from typing import Dict, List

from celery import Celery
from .cache import claim_cache_key, get_sync_redis
from .ofc_engine import evaluate_text
from .schemas import ClaimResult, EvidenceItem, FactcheckResponse, Summary
from .settings import settings


logger = logging.getLogger(__name__)

celery_app = Celery("factcheck-service", broker=settings.REDIS_URL)


def _get_redis():
    return get_sync_redis()


def _build_summary(claims: List[ClaimResult]) -> Summary:
    summary = Summary()
    for claim in claims:
        if claim.verdict == "supported":
            summary.supported += 1
        elif claim.verdict == "unsupported":
            summary.unsupported += 1
        elif claim.verdict == "contradicted":
            summary.contradicted += 1
        else:
            summary.unknown += 1
    return summary


def _apply_cache(
    redis: Redis,
    claims_raw: List[dict],
    context: str | None,
    include_evidence: bool,
) -> List[ClaimResult]:
    keys = [
        claim_cache_key(item["claim"], settings.EVIDENCE_MODE.value, context)
        for item in claims_raw
    ]
    cached_values = redis.mget(keys)
    cache_updates: Dict[str, dict] = {}
    claims: List[ClaimResult] = []

    for item, key, cached in zip(claims_raw, keys, cached_values):
        if cached:
            cached_item = json.loads(cached)
            claims.append(
                ClaimResult(
                    claim=cached_item["claim"],
                    verdict=cached_item["verdict"],
                    evidence=[
                        EvidenceItem(**ev) for ev in cached_item.get("evidence", [])
                    ]
                    if include_evidence
                    else [],
                )
            )
            continue

        evidence_items = [
            EvidenceItem(**ev) for ev in (item.get("evidence") or [])
        ]
        claim_result = ClaimResult(
            claim=item["claim"],
            verdict=item["verdict"],
            evidence=evidence_items,
        )
        claims.append(
            ClaimResult(
                claim=claim_result.claim,
                verdict=claim_result.verdict,
                evidence=claim_result.evidence if include_evidence else [],
            )
        )
        cache_updates[key] = claim_result.model_dump()

    if cache_updates:
        pipe = redis.pipeline()
        for key, value in cache_updates.items():
            pipe.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(value))
        pipe.execute()

    return claims


@celery_app.task(name="factcheck.process")
def process_factcheck(job_id: str, payload: dict) -> None:
    redis = _get_redis()
    try:
        claims_raw, warnings = asyncio.run(
            evaluate_text(payload["text"], payload.get("context"), settings.EVIDENCE_MODE)
        )
        claims = _apply_cache(
            redis,
            claims_raw,
            payload.get("context"),
            payload.get("include_evidence", True),
        )
        response = FactcheckResponse(
            summary=_build_summary(claims),
            claims=claims,
            warnings=warnings,
        )
        job_payload = {
            "job_id": job_id,
            "status": "completed",
            "result": response.model_dump(),
        }
    except Exception as exc:
        logger.exception("Job failed", extra={"job_id": job_id})
        job_payload = {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
        }

    redis.setex(
        f"job:{job_id}",
        settings.CACHE_TTL_SECONDS,
        json.dumps(job_payload),
    )
