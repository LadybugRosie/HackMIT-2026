"""
arXiv and CrossRef verification for citation claims.
Verifies: arXiv paper existence, DOI resolution, venue matching.
Free APIs, no keys needed.
"""
import logging
import re
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def verify_arxiv_id(arxiv_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if an arXiv paper exists and return its metadata.
    Uses the arXiv API (free, no key).
    """
    # Normalize ID
    arxiv_id = arxiv_id.strip()
    if arxiv_id.lower().startswith("arxiv:"):
        arxiv_id = arxiv_id[6:]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://export.arxiv.org/api/query?id_list={arxiv_id}",
                timeout=5.0,
            )
            if resp.status_code != 200:
                return None

            text = resp.text
            # Check if paper was found (arXiv API returns XML)
            if "<title>Error</title>" in text or "is not a valid arXiv identifier" in text:
                return {"exists": False, "arxiv_id": arxiv_id}

            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
            titles = re.findall(r'<title>(.*?)</title>', text, re.DOTALL)
            # First title is the feed title, second is the paper title
            paper_title = titles[1].strip() if len(titles) > 1 else None

            if not paper_title or paper_title == "Error":
                return {"exists": False, "arxiv_id": arxiv_id}

            # Extract authors
            authors = re.findall(r'<name>(.*?)</name>', text)

            return {
                "exists": True,
                "arxiv_id": arxiv_id,
                "title": paper_title,
                "authors": authors[:5],
            }
    except Exception as e:
        logger.debug(f"arXiv verification failed: {e}")
        return None


async def verify_crossref_title(title: str, claimed_venue: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Search CrossRef for a paper by title and verify venue.
    Free API, no key needed (polite pool).
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.crossref.org/works",
                params={
                    "query.title": title,
                    "rows": 3,
                    "select": "title,container-title,published-print,author,DOI",
                },
                headers={"User-Agent": "OpenFactCheck/1.0 (mailto:noreply@openfactcheck.org)"},
                timeout=8.0,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            items = data.get("message", {}).get("items", [])
            if not items:
                return {"found": False, "title": title}

            # Find best match by title similarity
            title_lower = title.lower().strip()
            for item in items:
                item_titles = item.get("title", [])
                for t in item_titles:
                    if _title_similarity(title_lower, t.lower()) > 0.7:
                        venue = (item.get("container-title") or [""])[0]
                        result = {
                            "found": True,
                            "title": t,
                            "venue": venue,
                            "doi": item.get("DOI"),
                        }
                        # Check venue if claimed
                        if claimed_venue and venue:
                            venue_match = _title_similarity(
                                claimed_venue.lower(), venue.lower()
                            ) > 0.6
                            result["venue_match"] = venue_match
                            result["actual_venue"] = venue
                        return result

            return {"found": False, "title": title}
    except Exception as e:
        logger.debug(f"CrossRef verification failed: {e}")
        return None


def _title_similarity(a: str, b: str) -> float:
    """Simple token overlap similarity."""
    tokens_a = set(re.findall(r'\w+', a.lower()))
    tokens_b = set(re.findall(r'\w+', b.lower()))
    stop = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or'}
    tokens_a -= stop
    tokens_b -= stop
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
