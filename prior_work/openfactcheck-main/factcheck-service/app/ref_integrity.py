"""
Reference integrity checking: DOI and URL validation.
Uses Crossref and DataCite APIs for DOI resolution.
"""
import asyncio
import hashlib
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .settings import settings

logger = logging.getLogger(__name__)


class DOIStatus(str, Enum):
    VALID = "valid"
    NOT_FOUND = "not_found"
    INVALID = "invalid"
    MISMATCH = "mismatch"
    TIMEOUT = "timeout"
    ERROR = "error"


class URLStatus(str, Enum):
    OK = "ok"
    BROKEN = "broken"        # 404 / 410 / 5xx — resource genuinely gone or failing
    BLOCKED = "blocked"      # 401 / 403 / 429 — reachable but refuses automated access
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class DOIMetadata:
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi_url: Optional[str] = None


@dataclass
class DOIResult:
    doi: str
    status: DOIStatus
    registrar: Optional[str] = None  # crossref, datacite, unknown
    resolved_url: Optional[str] = None
    metadata: Optional[DOIMetadata] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doi": self.doi,
            "status": self.status.value,
            "registrar": self.registrar,
            "resolved_url": self.resolved_url,
            "metadata": {
                "title": self.metadata.title,
                "authors": self.metadata.authors,
                "year": self.metadata.year,
                "venue": self.metadata.venue,
            } if self.metadata else None,
            "note": self.note,
        }


@dataclass
class URLResult:
    url: str
    status: URLStatus
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status.value,
            "http_status": self.http_status,
            "final_url": self.final_url,
            "note": self.note,
        }


# DOI regex pattern — suffix may legitimately contain parentheses,
# e.g. 10.1016/S0140-6736(20)31142-9 (Lancet-style DOIs)
DOI_PATTERN = re.compile(
    r'\b(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)?'
    r'(10\.\d{4,9}/[-._;()/:<>A-Za-z0-9]+)',
    re.IGNORECASE
)

# Unicode dash variants that frequently appear in copy-pasted DOIs
# (en dash, em dash, minus sign) — all mapped to ASCII hyphen.
_DASH_TRANSLATION = str.maketrans({
    "–": "-",  # – en dash
    "—": "-",  # — em dash
    "−": "-",  # − minus sign
})


def normalize_dashes(text: str) -> str:
    """Replace Unicode dash variants with ASCII hyphens."""
    return text.translate(_DASH_TRANSLATION)

# URL pattern
URL_PATTERN = re.compile(
    r'https?://[^\s\]\)>,;\"\'<]+',
    re.IGNORECASE
)


def normalize_doi(doi: str) -> str:
    """Normalize DOI by stripping prefixes and cleaning."""
    doi = normalize_dashes(doi.strip())
    # Remove common prefixes
    for prefix in ["doi:", "DOI:", "https://doi.org/", "http://doi.org/",
                   "https://dx.doi.org/", "http://dx.doi.org/"]:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
    # Strip trailing punctuation; strip a trailing ')' ONLY if unbalanced
    # (parentheses are legal inside DOI suffixes, e.g. ...(20)31142-9)
    doi = doi.rstrip(".,;:\"'")
    while doi.endswith(")") and doi.count(")") > doi.count("("):
        doi = doi[:-1].rstrip(".,;:\"'")
    # Strip a duplicate ".arXiv:<id>" suffix some BibTeX/arXiv exports append to
    # arXiv DOIs (10.48550/arXiv.2510.06743.arXiv:2510.06743 -> .../arXiv.2510.06743).
    # The colon form is never valid inside a DOI, so this only removes junk and
    # prevents a false "not found" on a perfectly real arXiv citation.
    doi = re.sub(r'\.arxiv:[0-9v.]+$', '', doi, flags=re.IGNORECASE)
    return doi.strip()


# A DOI suffix never legitimately ends on one of these — a capture that does
# was cut short (PDF line-wrap, trailing-punctuation strip, etc.).
_TRUNCATION_TAIL = "-._/:;(,"


def _is_truncation_fragment(doi: str) -> bool:
    """True if `doi` looks like an incomplete capture in its own right.

    Two structural signals, both of which a complete DOI never exhibits:
      * it ends on a separator character (e.g. "10.1038/s41586-021-"), or
      * it has an unclosed '(' (e.g. "10.1016/S0140-6736(20").
    """
    suffix = doi.split("/", 1)[1] if "/" in doi else ""
    if not suffix:
        return True
    if suffix[-1] in _TRUNCATION_TAIL:
        return True
    return suffix.count("(") > suffix.count(")")


def extract_dois(text: str) -> List[str]:
    """Extract unique DOIs from text (Unicode dashes normalized first)."""
    matches = DOI_PATTERN.findall(normalize_dashes(text))
    # Normalize and dedupe
    seen = set()
    result = []
    for doi in matches:
        normalized = normalize_doi(doi)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    # Drop truncation fragments. A partial capture is identified by its own
    # SHAPE (trailing separator / unbalanced parenthesis), not merely by being
    # a prefix of another DOI: two legitimately distinct DOIs can stand in a
    # prefix relationship (e.g. ".../fake.2021.1234" and ".../fake.2021.12345"),
    # and dropping the shorter one silently skipped verification for it — the
    # wrong failure direction for an integrity tool, and an evasion vector.
    deduped = [
        d for d in result
        if not (
            _is_truncation_fragment(d)
            and any(other != d and other.startswith(d) for other in result)
        )
    ]
    return deduped[:settings.MAX_REFERENCES_TO_CHECK]


def extract_urls(text: str) -> List[str]:
    """Extract unique URLs from text (excluding DOI URLs)."""
    matches = URL_PATTERN.findall(text)
    seen = set()
    result = []
    for raw in matches:
        # PDF extraction sometimes glues two URLs together with no space
        # ("…/leggomanzoni/2https://dlrc…") — split on an embedded scheme.
        for url in re.split(r'(?=https?://)', raw):
            url = url.strip().rstrip(".,;:\"')")
            if not url.lower().startswith("http"):
                continue
            # Skip DOI URLs
            if "doi.org" in url.lower():
                continue
            # Strip a duplicate ".arXiv:<id>" suffix (BibTeX/arXiv export junk):
            # https://arxiv.org/abs/2509.23488.arXiv:2509.23488 -> .../abs/2509.23488
            url = re.sub(r'\.arxiv:[0-9v.]+$', '', url, flags=re.IGNORECASE)
            if url and url not in seen:
                seen.add(url)
                result.append(url)
    return result[:settings.MAX_URLS_TO_CHECK]


def doi_cache_key(doi: str) -> str:
    """Generate cache key for DOI result."""
    return f"doi:{hashlib.sha256(doi.encode()).hexdigest()[:16]}"


def url_cache_key(url: str) -> str:
    """Generate cache key for URL result."""
    return f"url:{hashlib.sha256(url.encode()).hexdigest()[:16]}"


# Registry lookup outcome. `definitive` is True only when the registry itself
# answered "no such DOI" (an HTTP 404). A timeout / 5xx / connection error is
# NOT evidence of fabrication — it must never be reported as "not found".
async def _resolve_doi_org(client: httpx.AsyncClient, doi: str) -> Tuple[bool, Optional[str], bool]:
    """Check if DOI resolves via doi.org. Returns (resolves, final_url, definitive)."""
    url = f"https://doi.org/{doi}"
    try:
        resp = await client.head(url, follow_redirects=True, timeout=settings.DOI_TIMEOUT_SECONDS)
        if resp.status_code in (200, 302, 301, 303, 307, 308):
            return True, str(resp.url), True
        # Some publisher landing pages reject HEAD (403/405) but the DOI itself
        # resolved (doi.org redirected us there). Only a 404 from doi.org is a
        # definitive "no such DOI"; anything else is inconclusive.
        if resp.status_code == 404 and "doi.org" in str(resp.url):
            return False, None, True
        if resp.status_code in (403, 405) and "doi.org" not in str(resp.url):
            return True, str(resp.url), True
        return False, None, False
    except httpx.TimeoutException:
        return False, None, False
    except Exception as e:
        logger.debug(f"DOI resolution error for {doi}: {e}")
        return False, None, False


async def _fetch_crossref(client: httpx.AsyncClient, doi: str) -> Tuple[Optional[DOIMetadata], bool]:
    """Fetch DOI metadata from Crossref. Returns (metadata, definitive_negative)."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = await client.get(
            url,
            timeout=settings.DOI_TIMEOUT_SECONDS,
            headers={"Accept": "application/json",
                     "User-Agent": "factcheck-service (mailto:factcheck-service@openfactcheck.local)"}
        )
        if resp.status_code == 404:
            return None, True
        if resp.status_code != 200:
            return None, False
        data = resp.json()
        message = data.get("message", {})
        
        # Extract title
        titles = message.get("title", [])
        title = titles[0] if titles else None
        
        # Extract authors
        authors = []
        for author in message.get("author", []):
            name_parts = []
            if author.get("given"):
                name_parts.append(author["given"])
            if author.get("family"):
                name_parts.append(author["family"])
            if name_parts:
                authors.append(" ".join(name_parts))
        
        # Extract year
        year = None
        published = message.get("published") or message.get("created")
        if published and "date-parts" in published:
            date_parts = published["date-parts"]
            if date_parts and date_parts[0]:
                year = date_parts[0][0]
        
        # Extract venue
        venue = None
        container = message.get("container-title", [])
        if container:
            venue = container[0]
        
        return DOIMetadata(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi_url=f"https://doi.org/{doi}"
        ), False
    except Exception as e:
        logger.debug(f"Crossref error for {doi}: {e}")
        return None, False


async def _fetch_datacite(client: httpx.AsyncClient, doi: str) -> Tuple[Optional[DOIMetadata], bool]:
    """Fetch DOI metadata from DataCite. Returns (metadata, definitive_negative)."""
    url = f"https://api.datacite.org/dois/{doi}"
    try:
        resp = await client.get(
            url,
            timeout=settings.DOI_TIMEOUT_SECONDS,
            headers={"Accept": "application/json"}
        )
        if resp.status_code == 404:
            return None, True
        if resp.status_code != 200:
            return None, False
        data = resp.json()
        attrs = data.get("data", {}).get("attributes", {})
        
        # Extract title
        titles = attrs.get("titles", [])
        title = titles[0].get("title") if titles else None
        
        # Extract authors
        authors = []
        for creator in attrs.get("creators", []):
            name = creator.get("name") or ""
            if creator.get("givenName") and creator.get("familyName"):
                name = f"{creator['givenName']} {creator['familyName']}"
            if name:
                authors.append(name)
        
        # Extract year
        year = attrs.get("publicationYear")
        
        # Extract venue/publisher
        venue = attrs.get("publisher")
        
        return DOIMetadata(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi_url=f"https://doi.org/{doi}"
        ), False
    except Exception as e:
        logger.debug(f"DataCite error for {doi}: {e}")
        return None, False


# Full-string DOI syntax: 10.<registrant: 4-9 digits>/<suffix>
_DOI_SYNTAX = re.compile(r'^10\.\d{4,9}/[-._;()/:<>A-Za-z0-9]+$', re.IGNORECASE)


def _is_valid_doi_format(doi: str) -> bool:
    """
    Check if the string matches DOI syntax (10.<4-9 digit registrant>/<suffix>).

    This is a purely syntactic check: a string that matches DOI syntax but
    does not exist in any registry must be reported as NOT_FOUND, never
    INVALID. INVALID is reserved strictly for strings that fail DOI syntax.
    """
    return bool(_DOI_SYNTAX.match(doi))


async def check_doi(doi: str, client: Optional[httpx.AsyncClient] = None) -> DOIResult:
    """
    Validate a DOI:
    1. Check format
    2. Resolve via doi.org
    3. Fetch metadata from Crossref or DataCite
    """
    doi = normalize_doi(doi)
    
    # Check format
    if not _is_valid_doi_format(doi):
        return DOIResult(
            doi=doi,
            status=DOIStatus.INVALID,
            note="String does not match DOI syntax (expected 10.<registrant>/<suffix>)"
        )
    
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    
    try:
        # doi.org + Crossref + DataCite in parallel; one retry for the lookups
        # that were inconclusive (timeout / 5xx). "Not found" is asserted ONLY
        # when at least one registry definitively answered 404 — a transient
        # network failure must never be reported as a fabricated citation.
        async def _lookup_all():
            return await asyncio.gather(
                _resolve_doi_org(client, doi),
                _fetch_crossref(client, doi),
                _fetch_datacite(client, doi),
            )

        (resolves, resolved_url, doi_def), (cr_meta, cr_def), (dc_meta, dc_def) = await _lookup_all()
        if not (resolves or cr_meta or dc_meta) and not (doi_def or cr_def or dc_def):
            # Everything was inconclusive (timeouts / errors) — retry once.
            (resolves, resolved_url, doi_def), (cr_meta, cr_def), (dc_meta, dc_def) = await _lookup_all()

        metadata = cr_meta or dc_meta
        registrar = "crossref" if cr_meta else ("datacite" if dc_meta else None)
        definitive_negative = doi_def or cr_def or dc_def

        # Determine status
        if metadata:
            return DOIResult(
                doi=doi,
                status=DOIStatus.VALID,
                registrar=registrar,
                resolved_url=resolved_url or f"https://doi.org/{doi}",
                metadata=metadata,
                note=None
            )
        elif resolves:
            return DOIResult(
                doi=doi,
                status=DOIStatus.VALID,
                registrar="unknown",
                resolved_url=resolved_url,
                metadata=None,
                note="DOI resolves but metadata not found in Crossref/DataCite"
            )
        elif definitive_negative:
            return DOIResult(
                doi=doi,
                status=DOIStatus.NOT_FOUND,
                note="DOI not found in doi.org, Crossref, or DataCite"
            )
        else:
            return DOIResult(
                doi=doi,
                status=DOIStatus.TIMEOUT,
                note="DOI registries did not answer in time (inconclusive — not evidence of fabrication)"
            )
    
    except httpx.TimeoutException:
        return DOIResult(
            doi=doi,
            status=DOIStatus.TIMEOUT,
            note="Timeout during DOI validation"
        )
    except Exception as e:
        logger.warning(f"DOI check error for {doi}: {e}")
        return DOIResult(
            doi=doi,
            status=DOIStatus.ERROR,
            note=str(e)
        )
    finally:
        if own_client:
            await client.aclose()


def _is_url_safe(url: str) -> bool:
    """SSRF guard: allow only http(s) URLs that resolve to PUBLIC IP addresses.
    Blocks localhost / private / link-local / reserved ranges so a user-supplied
    reference can't make the server probe internal services."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        try:
            infos = socket.getaddrinfo(p.hostname, None)
        except Exception:
            return False
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


async def check_url(url: str, client: Optional[httpx.AsyncClient] = None) -> URLResult:
    """
    Validate a URL:
    1. HEAD request first
    2. GET fallback if HEAD fails
    """
    if not _is_url_safe(url):
        return URLResult(url=url, status=URLStatus.ERROR, note="Blocked: non-public URL (SSRF guard)")
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    
    try:
        # Try HEAD first
        try:
            resp = await client.head(
                url,
                follow_redirects=True,
                timeout=settings.URL_TIMEOUT_SECONDS
            )
            if resp.status_code < 400:
                return URLResult(
                    url=url,
                    status=URLStatus.OK,
                    http_status=resp.status_code,
                    final_url=str(resp.url)
                )
        except Exception:
            pass
        
        # Fallback to GET
        resp = await client.get(
            url,
            follow_redirects=True,
            timeout=settings.URL_TIMEOUT_SECONDS
        )
        
        if resp.status_code < 400:
            return URLResult(
                url=url,
                status=URLStatus.OK,
                http_status=resp.status_code,
                final_url=str(resp.url)
            )
        elif resp.status_code in (401, 403, 429):
            # Reachable, but the site refuses automated access (bot protection,
            # rate limit, auth wall) — NOT the same as a dead link.
            return URLResult(
                url=url,
                status=URLStatus.BLOCKED,
                http_status=resp.status_code,
                note=f"HTTP {resp.status_code} — access blocked (page may still be valid in a browser)"
            )
        else:
            return URLResult(
                url=url,
                status=URLStatus.BROKEN,
                http_status=resp.status_code,
                note=f"HTTP {resp.status_code}"
            )
    
    except httpx.TimeoutException:
        return URLResult(
            url=url,
            status=URLStatus.TIMEOUT,
            note="Request timed out"
        )
    except Exception as e:
        return URLResult(
            url=url,
            status=URLStatus.ERROR,
            note=str(e)
        )
    finally:
        if own_client:
            await client.aclose()


async def check_dois_batch(dois: List[str]) -> List[DOIResult]:
    """Check multiple DOIs concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = [check_doi(doi, client) for doi in dois]
        return await asyncio.gather(*tasks)


async def check_urls_batch(urls: List[str]) -> List[URLResult]:
    """Check multiple URLs concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = [check_url(url, client) for url in urls]
        return await asyncio.gather(*tasks)


@dataclass
class ReferenceReport:
    dois: List[DOIResult] = field(default_factory=list)
    urls: List[URLResult] = field(default_factory=list)
    
    @property
    def valid_doi_count(self) -> int:
        return sum(1 for d in self.dois if d.status == DOIStatus.VALID)
    
    @property
    def invalid_doi_count(self) -> int:
        return sum(1 for d in self.dois if d.status in (DOIStatus.INVALID, DOIStatus.NOT_FOUND))
    
    @property
    def broken_url_count(self) -> int:
        # Genuinely dead/failing links only — a BLOCKED (403/429) URL is
        # reachable in a browser, so it is not counted as broken.
        return sum(1 for u in self.urls if u.status in (URLStatus.BROKEN, URLStatus.ERROR))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dois": [d.to_dict() for d in self.dois],
            "urls": [u.to_dict() for u in self.urls],
            "summary": {
                "total_dois": len(self.dois),
                "valid_dois": self.valid_doi_count,
                "invalid_dois": self.invalid_doi_count,
                "total_urls": len(self.urls),
                "broken_urls": self.broken_url_count,
            }
        }
    
    def get_warnings(self) -> List[str]:
        """Generate warnings for invalid references."""
        warnings = []
        # A DOI that failed lookup but is a strict prefix of one that resolved is
        # most likely a line-wrapped capture of that longer DOI, not a fabricated
        # citation. Report it as such rather than as a missing reference — the
        # entry is still surfaced, never silently discarded.
        resolved = {d.doi for d in self.dois if d.status == DOIStatus.VALID}
        for d in self.dois:
            if d.status == DOIStatus.INVALID:
                warnings.append(f"Invalid DOI format: {d.doi}")
            elif d.status == DOIStatus.NOT_FOUND:
                longer = next(
                    (r for r in resolved if r != d.doi and r.startswith(d.doi)), None
                )
                if longer:
                    warnings.append(
                        f"Possible truncated DOI capture: {d.doi} "
                        f"(prefix of resolved {longer}) - verify manually"
                    )
                else:
                    warnings.append(f"DOI not found in registries: {d.doi}")
            elif d.status == DOIStatus.MISMATCH:
                warnings.append(f"DOI metadata mismatch: {d.doi} - {d.note}")
        for u in self.urls:
            if u.status == URLStatus.BROKEN:
                warnings.append(f"Broken URL ({u.http_status}): {u.url}")
            elif u.status == URLStatus.TIMEOUT:
                warnings.append(f"URL timeout: {u.url}")
        return warnings
    
    def build_context(self) -> str:
        """Build context string from verified DOI metadata for OpenFactCheck."""
        parts = []
        for d in self.dois:
            if d.status == DOIStatus.VALID and d.metadata:
                m = d.metadata
                info = f"[Verified Reference] DOI: {d.doi}"
                if m.title:
                    info += f", Title: {m.title}"
                if m.authors:
                    info += f", Authors: {', '.join(m.authors[:3])}"
                if m.year:
                    info += f", Year: {m.year}"
                if m.venue:
                    info += f", Venue: {m.venue}"
                parts.append(info)
        return "\n".join(parts)


async def check_references(text: str) -> ReferenceReport:
    """Extract and validate all references in text."""
    dois = extract_dois(text)
    urls = extract_urls(text)
    
    doi_results = await check_dois_batch(dois) if dois else []
    url_results = await check_urls_batch(urls) if urls else []
    
    return ReferenceReport(dois=doi_results, urls=url_results)
