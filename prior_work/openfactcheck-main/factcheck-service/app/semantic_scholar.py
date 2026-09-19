"""
Semantic Scholar API integration for evidence retrieval.
Searches 200M+ academic papers for real-time claim verification.
"""
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_URL = f"{S2_API_BASE}/paper/search"
S2_PAPER_URL = f"{S2_API_BASE}/paper"


def _build_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY
    return headers


# ── Shared, rate-limited S2 GET ──────────────────────────────────────────────
# The key-less S2 tier allows ~1 request/second shared across the whole
# service. Concurrent claims used to fire in parallel, get 429'd, and silently
# lose their evidence (non-deterministic verdicts). Space calls out and retry
# once on 429 so evidence retrieval is repeatable.
_S2_MIN_INTERVAL = 1.05 if not settings.SEMANTIC_SCHOLAR_API_KEY else 0.12
_S2_MAX_QUEUE_WAIT = 3.0   # bound the latency any single request can spend queueing for S2
_s2_next_allowed = 0.0


async def s2_get(client: httpx.AsyncClient, url: str, params: Dict[str, Any],
                 timeout: Optional[float] = None) -> Optional[httpx.Response]:
    """GET against Semantic Scholar with global pacing + one retry on 429.
    Returns the response (any status) or None on a transport error."""
    global _s2_next_allowed
    import asyncio
    import time
    for attempt in range(2):
        now = time.monotonic()
        wait = _s2_next_allowed - now
        if wait > _S2_MAX_QUEUE_WAIT:
            # Backlog too long: skip rather than stall the request (or fire into
            # a certain 429). The caller treats None as "could not check".
            return None
        _s2_next_allowed = max(now, _s2_next_allowed) + _S2_MIN_INTERVAL
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            r = await client.get(
                url, params=params, headers=_build_headers(),
                timeout=timeout or settings.SOURCE_FETCH_TIMEOUT_SECONDS,
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"S2 request failed: {e}")
            return None
        if r.status_code == 429 and attempt == 0:
            await asyncio.sleep(2.5)
            continue
        return r
    return None


def _extract_search_query(claim: str) -> str:
    """Extract a concise search query from a claim."""
    # Remove filler words, keep substance
    claim = re.sub(r'\b(the|a|an|is|are|was|were|has|have|had|been|being)\b', ' ', claim, flags=re.IGNORECASE)
    claim = re.sub(r'\s+', ' ', claim).strip()
    # Truncate to ~100 chars for API
    if len(claim) > 100:
        claim = claim[:100].rsplit(' ', 1)[0]
    return claim


async def search_papers(
    query: str,
    limit: int = 5,
    fields: str = "title,abstract,year,authors,citationCount,isOpenAccess,externalIds",
) -> List[Dict[str, Any]]:
    """
    Search Semantic Scholar for papers matching a query.
    Returns list of paper dicts with title, abstract, year, authors, etc.
    """
    if not query.strip():
        return []

    params = {
        "query": query,
        "limit": limit,
        "fields": fields,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await s2_get(client, S2_SEARCH_URL, params)
            if resp is None:
                return []
            if resp.status_code == 429:
                logger.warning("Semantic Scholar rate limited")
                return []
            if resp.status_code != 200:
                logger.debug(f"S2 search returned {resp.status_code}")
                return []

            data = resp.json()
            return data.get("data", [])
    except Exception as e:
        logger.debug(f"Semantic Scholar search error: {e}")
        return []


async def get_paper_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    """Fetch paper details by DOI from Semantic Scholar."""
    fields = "title,abstract,year,authors,citationCount,isOpenAccess,venue,referenceCount,tldr"
    try:
        async with httpx.AsyncClient() as client:
            resp = await s2_get(client, f"{S2_PAPER_URL}/DOI:{doi}", {"fields": fields})
            if resp is None or resp.status_code != 200:
                return None
            return resp.json()
    except Exception as e:
        logger.debug(f"S2 DOI lookup error: {e}")
        return None


async def check_retraction(doi: str) -> Optional[Dict[str, Any]]:
    """
    Check if a paper has been retracted via Semantic Scholar metadata.
    Returns retraction info if found, None otherwise.
    """
    try:
        paper = await get_paper_by_doi(doi)
        if not paper:
            return None

        # Check for retraction markers in title or abstract
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()

        retraction_markers = [
            "retracted", "retraction", "withdrawn", "withdrawal",
            "erratum", "correction notice", "expression of concern",
        ]

        for marker in retraction_markers:
            if marker in title or marker in abstract:
                return {
                    "doi": doi,
                    "retracted": True,
                    "title": paper.get("title"),
                    "marker": marker,
                }

        return None
    except Exception as e:
        logger.debug(f"Retraction check error: {e}")
        return None


async def get_evidence_for_claim(claim: str) -> List[Dict[str, Any]]:
    """
    Search Semantic Scholar for evidence supporting or refuting a claim.
    Returns list of evidence items with source, snippet, url.
    """
    if not settings.ENABLE_SEMANTIC_SCHOLAR:
        return []

    query = _extract_search_query(claim)
    papers = await search_papers(query, limit=3)

    evidence = []
    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        year = paper.get("year")
        authors = paper.get("authors", [])
        citation_count = paper.get("citationCount", 0)
        paper_id = paper.get("paperId", "")

        # Build author string
        author_names = [a.get("name", "") for a in authors[:3]]
        author_str = ", ".join(author_names)
        if len(authors) > 3:
            author_str += " et al."

        # Build snippet from abstract
        snippet = ""
        if abstract:
            # Take first 300 chars of abstract
            snippet = abstract[:300]
            if len(abstract) > 300:
                snippet = snippet.rsplit(' ', 1)[0] + "..."

        # Use TLDR if available
        tldr = paper.get("tldr")
        if tldr and tldr.get("text"):
            snippet = tldr["text"]

        if not snippet:
            snippet = f"{title} ({year})" if year else title

        # Build citation info
        source = f"Semantic Scholar ({author_str}, {year})" if year else f"Semantic Scholar ({author_str})"
        if citation_count:
            source += f" [{citation_count} citations]"

        # Build URL
        url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

        # Check for DOI
        ext_ids = paper.get("externalIds", {})
        if ext_ids and ext_ids.get("DOI"):
            url = f"https://doi.org/{ext_ids['DOI']}"

        evidence.append({
            "source": source,
            "snippet": snippet,
            "url": url,
        })

    return evidence
