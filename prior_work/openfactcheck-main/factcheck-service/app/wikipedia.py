"""
Wikipedia evidence retrieval for fact verification.
Uses Wikipedia REST API (free, no key required).
"""
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/api.php"


async def search_wikipedia(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Search Wikipedia for relevant articles.
    Returns list of {title, snippet, url}.
    """
    if not settings.ENABLE_WIKIPEDIA_EVIDENCE:
        return []
    
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "srprop": "snippet",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                WIKIPEDIA_SEARCH_URL,
                params=params,
                timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            results = []
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                # Clean HTML from snippet
                snippet = re.sub(r'<[^>]+>', '', snippet)
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                })
            return results
    except Exception as e:
        logger.debug(f"Wikipedia search error: {e}")
        return []


async def get_wikipedia_summary(title: str) -> Optional[Dict[str, Any]]:
    """
    Get Wikipedia article summary.
    Returns {title, extract, url} or None.
    """
    if not settings.ENABLE_WIKIPEDIA_EVIDENCE:
        return None
    
    try:
        # URL encode the title
        encoded_title = title.replace(" ", "_")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{WIKIPEDIA_API_URL}{encoded_title}",
                timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            if data.get("type") == "disambiguation":
                return None
            
            return {
                "title": data.get("title", title),
                "extract": data.get("extract", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{encoded_title}"),
            }
    except Exception as e:
        logger.debug(f"Wikipedia summary error for {title}: {e}")
        return None


def extract_search_terms(claim: str) -> List[str]:
    """
    Extract key search terms from a claim for Wikipedia lookup.
    """
    # Remove common words and extract potential entities
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but',
        'if', 'or', 'because', 'until', 'while', 'that', 'this', 'these',
        'those', 'it', 'its', 'they', 'them', 'their', 'he', 'she', 'him',
        'her', 'his', 'we', 'us', 'our', 'you', 'your', 'i', 'me', 'my',
    }
    
    # Find capitalized phrases (potential proper nouns)
    proper_nouns = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', claim)
    
    # Filter and return
    terms = []
    for term in proper_nouns:
        if term.lower() not in stopwords and len(term) > 2:
            terms.append(term)
    
    # Limit to top 3 terms
    return terms[:3]


def _extract_key_entities(claim: str) -> List[str]:
    """
    Extract key entities from a claim for Wikipedia lookup.
    More aggressive than extract_search_terms for better coverage.
    """
    # Extract proper nouns (capitalized words/phrases)
    proper_nouns = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', claim)
    
    # Extract potential topics (noun phrases)
    topics = []
    
    # Common factual patterns
    patterns = [
        r'(\w+\s+\w+)\s+(?:is|are|was|were)',  # X is/was Y
        r'(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # The X
        r'(\d{4})',  # Years
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, claim)
        topics.extend(matches)
    
    # Combine and deduplicate
    all_terms = proper_nouns + topics
    seen = set()
    result = []
    for term in all_terms:
        term = term.strip()
        if term and term.lower() not in seen and len(term) > 2:
            seen.add(term.lower())
            result.append(term)
    
    return result[:5]  # Limit to top 5


async def get_evidence_for_claim(claim: str) -> List[Dict[str, Any]]:
    """
    Try to find Wikipedia evidence for a claim.
    Returns list of evidence items with verdict hints.
    """
    if not settings.ENABLE_WIKIPEDIA_EVIDENCE:
        return []
    
    evidence = []
    
    # Try direct entity lookup
    search_terms = extract_search_terms(claim)
    for term in search_terms:
        summary = await get_wikipedia_summary(term)
        if summary and summary.get("extract"):
            evidence.append({
                "source": "Wikipedia",
                "snippet": summary["extract"][:500],
                "url": summary["url"],
            })
            break
    
    # If no direct match, try broader search
    if not evidence:
        entities = _extract_key_entities(claim)
        if entities:
            # Search with full claim context
            results = await search_wikipedia(claim[:200], limit=2)
            for r in results:
                if r.get("snippet"):
                    evidence.append({
                        "source": "Wikipedia",
                        "snippet": r["snippet"],
                        "url": r["url"],
                    })
                    break
    
    return evidence
