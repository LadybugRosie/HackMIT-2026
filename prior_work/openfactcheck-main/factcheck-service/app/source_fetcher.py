"""
Source fetcher for citation-content alignment.

For a given DOI / arXiv ID / title, pulls together everything we can get
from FREE, KEY-LESS public APIs:

  - Crossref           → title, authors, year, venue, references, update-to (retraction)
  - DataCite           → titles, creators, year, publisher (arXiv lives here)
  - OpenAlex           → abstract (reconstructed from inverted_index), concepts,
                         referenced_works count, is_retracted flag, host_venue
  - Unpaywall          → OA full-text PDF/HTML URL
  - Semantic Scholar   → abstract, TLDR (one-line auto-summary), authors w/ S2 ids

The fetcher returns a SourceRecord that gives the rest of the pipeline a
single grounded blob to reason about. No LLM here; just HTTP and JSON.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from .cache import get_redis
from .settings import settings

logger = logging.getLogger(__name__)

# A polite mailto helps Crossref / OpenAlex / Unpaywall give us the fast lane.
_POLITE_EMAIL = "factcheck-service@openfactcheck.local"

# Cap text we keep, to bound LLM token cost on alignment.
_MAX_ABSTRACT_CHARS = 4000


@dataclass
class SourceAuthor:
    name: str
    s2_id: Optional[str] = None
    openalex_id: Optional[str] = None


@dataclass
class SourceRecord:
    """Everything we know about one cited source."""
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    openalex_id: Optional[str] = None

    title: Optional[str] = None
    authors: List[SourceAuthor] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    publisher: Optional[str] = None

    abstract: Optional[str] = None
    tldr: Optional[str] = None
    oa_url: Optional[str] = None

    is_retracted: bool = False
    retraction_note: Optional[str] = None

    sources_consulted: List[str] = field(default_factory=list)

    def best_text(self) -> str:
        """Return the longest grounded text we can give an LLM."""
        parts: List[str] = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.authors:
            parts.append("Authors: " + ", ".join(a.name for a in self.authors[:8]))
        if self.year:
            parts.append(f"Year: {self.year}")
        if self.venue:
            parts.append(f"Venue: {self.venue}")
        if self.tldr:
            parts.append(f"TL;DR: {self.tldr}")
        if self.abstract:
            parts.append(f"Abstract: {self.abstract}")
        return "\n".join(parts)


# ────────────────────────────────────────────────────────────────────────────
# tiny async-cache helper (reuses the redis layer; falls back to memory).
# ────────────────────────────────────────────────────────────────────────────
async def _cache_get(key: str) -> Optional[dict]:
    try:
        r = get_redis()
        raw = await r.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


async def _cache_set(key: str, value: dict, ttl: int = 60 * 60 * 24 * 7) -> None:
    try:
        r = get_redis()
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────────────
# Crossref
# ────────────────────────────────────────────────────────────────────────────
async def fetch_crossref(client: httpx.AsyncClient, doi: str) -> Dict[str, Any]:
    url = f"https://api.crossref.org/works/{doi}"
    try:
        r = await client.get(
            url,
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": f"factcheck-service (mailto:{_POLITE_EMAIL})"},
        )
        if r.status_code != 200:
            return {}
        return r.json().get("message", {}) or {}
    except Exception as e:
        logger.debug(f"Crossref fetch failed for {doi}: {e}")
        return {}


def _crossref_to_record(msg: Dict[str, Any], rec: SourceRecord) -> SourceRecord:
    if not msg:
        return rec
    titles = msg.get("title") or []
    rec.title = rec.title or (titles[0] if titles else None)
    if not rec.authors:
        for a in msg.get("author", []) or []:
            name = " ".join(p for p in [a.get("given"), a.get("family")] if p)
            if name:
                rec.authors.append(SourceAuthor(name=name))
    if not rec.year:
        for k in ("published-print", "published-online", "published", "issued", "created"):
            dp = (msg.get(k) or {}).get("date-parts")
            if dp and dp[0]:
                rec.year = dp[0][0]
                break
    if not rec.venue:
        ct = msg.get("container-title") or []
        if ct:
            rec.venue = ct[0]
    if not rec.publisher:
        rec.publisher = msg.get("publisher")
    if not rec.abstract:
        abstract = msg.get("abstract")
        if abstract:
            # Crossref abstracts often have <jats:p> tags
            abstract = re.sub(r"<[^>]+>", " ", abstract)
            abstract = re.sub(r"\s+", " ", abstract).strip()
            rec.abstract = abstract[:_MAX_ABSTRACT_CHARS]
    # Retraction: Crossref signals via `update-to` with type "retraction".
    for upd in msg.get("update-to") or []:
        if (upd.get("type") or "").lower() == "retraction":
            rec.is_retracted = True
            rec.retraction_note = f"Crossref update-to: retracted {upd.get('updated', {}).get('date-time') or ''}".strip()
            break
    rec.sources_consulted.append("crossref")
    return rec


# ────────────────────────────────────────────────────────────────────────────
# DataCite (arXiv DOIs land here)
# ────────────────────────────────────────────────────────────────────────────
async def fetch_datacite(client: httpx.AsyncClient, doi: str) -> Dict[str, Any]:
    url = f"https://api.datacite.org/dois/{doi}"
    try:
        r = await client.get(url, timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS, headers={"Accept": "application/json"})
        if r.status_code != 200:
            return {}
        return ((r.json().get("data") or {}).get("attributes") or {})
    except Exception as e:
        logger.debug(f"DataCite fetch failed for {doi}: {e}")
        return {}


def _datacite_to_record(attrs: Dict[str, Any], rec: SourceRecord) -> SourceRecord:
    if not attrs:
        return rec
    titles = attrs.get("titles") or []
    if not rec.title and titles:
        rec.title = titles[0].get("title")
    if not rec.year:
        rec.year = attrs.get("publicationYear")
    if not rec.publisher:
        rec.publisher = attrs.get("publisher")
    if not rec.authors:
        for c in attrs.get("creators") or []:
            name = c.get("name") or " ".join(p for p in [c.get("givenName"), c.get("familyName")] if p)
            if name:
                rec.authors.append(SourceAuthor(name=name))
    if not rec.abstract:
        descriptions = attrs.get("descriptions") or []
        for d in descriptions:
            if (d.get("descriptionType") or "").lower() == "abstract":
                txt = re.sub(r"\s+", " ", d.get("description") or "").strip()
                if txt:
                    rec.abstract = txt[:_MAX_ABSTRACT_CHARS]
                    break
    rec.sources_consulted.append("datacite")
    return rec


# ────────────────────────────────────────────────────────────────────────────
# OpenAlex — free, no key. Abstract is encoded as inverted index.
# ────────────────────────────────────────────────────────────────────────────
def _decode_inverted_abstract(idx: Optional[Dict[str, List[int]]]) -> Optional[str]:
    if not idx:
        return None
    # Position → word; assemble in order.
    positions: List[tuple[int, str]] = []
    for word, pos_list in idx.items():
        for p in pos_list:
            positions.append((p, word))
    if not positions:
        return None
    positions.sort()
    text = " ".join(w for _, w in positions)
    return text[:_MAX_ABSTRACT_CHARS]


async def fetch_openalex(client: httpx.AsyncClient, doi: Optional[str], arxiv_id: Optional[str]) -> Dict[str, Any]:
    base = "https://api.openalex.org"
    if doi:
        url = f"{base}/works/https://doi.org/{doi}"
    elif arxiv_id:
        url = f"{base}/works/https://arxiv.org/abs/{arxiv_id}"
    else:
        return {}
    try:
        r = await client.get(
            url,
            params={"mailto": _POLITE_EMAIL},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return {}
        return r.json() or {}
    except Exception as e:
        logger.debug(f"OpenAlex fetch failed: {e}")
        return {}


def _openalex_to_record(data: Dict[str, Any], rec: SourceRecord) -> SourceRecord:
    if not data:
        return rec
    rec.openalex_id = data.get("id")
    if not rec.title:
        rec.title = data.get("title")
    if not rec.year:
        rec.year = data.get("publication_year")
    if not rec.venue:
        host = (data.get("primary_location") or {}).get("source") or (data.get("host_venue") or {})
        if host:
            rec.venue = host.get("display_name")
    if not rec.authors:
        for ap in data.get("authorships") or []:
            author = ap.get("author") or {}
            name = author.get("display_name")
            if name:
                rec.authors.append(SourceAuthor(name=name, openalex_id=author.get("id")))
    if not rec.abstract:
        ab = _decode_inverted_abstract(data.get("abstract_inverted_index"))
        if ab:
            rec.abstract = ab
    if not rec.oa_url:
        oa = data.get("open_access") or {}
        rec.oa_url = oa.get("oa_url")
    # OpenAlex marks retractions on `is_retracted`.
    if data.get("is_retracted"):
        rec.is_retracted = True
        rec.retraction_note = rec.retraction_note or "OpenAlex flags this work as retracted"
    rec.sources_consulted.append("openalex")
    return rec


# ────────────────────────────────────────────────────────────────────────────
# Unpaywall — needs only an email, no key.
# ────────────────────────────────────────────────────────────────────────────
async def fetch_unpaywall(client: httpx.AsyncClient, doi: str) -> Dict[str, Any]:
    url = f"https://api.unpaywall.org/v2/{doi}"
    try:
        r = await client.get(url, params={"email": _POLITE_EMAIL}, timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS)
        if r.status_code != 200:
            return {}
        return r.json() or {}
    except Exception as e:
        logger.debug(f"Unpaywall fetch failed for {doi}: {e}")
        return {}


def _unpaywall_to_record(data: Dict[str, Any], rec: SourceRecord) -> SourceRecord:
    if not data:
        return rec
    if not rec.oa_url:
        best = data.get("best_oa_location") or {}
        rec.oa_url = best.get("url_for_pdf") or best.get("url")
    rec.sources_consulted.append("unpaywall")
    return rec


# ────────────────────────────────────────────────────────────────────────────
# Semantic Scholar — TLDR is great for alignment.
# ────────────────────────────────────────────────────────────────────────────
async def fetch_semantic_scholar(client: httpx.AsyncClient, doi: Optional[str], arxiv_id: Optional[str]) -> Dict[str, Any]:
    if doi:
        pid = f"DOI:{doi}"
    elif arxiv_id:
        pid = f"ARXIV:{arxiv_id}"
    else:
        return {}
    url = f"https://api.semanticscholar.org/graph/v1/paper/{pid}"
    try:
        from .semantic_scholar import s2_get
        r = await s2_get(
            client, url,
            {"fields": "title,abstract,tldr,year,venue,authors,authors.authorId,authors.name"},
        )
        if r is None or r.status_code != 200:
            return {}
        return r.json() or {}
    except Exception as e:
        logger.debug(f"S2 fetch failed: {e}")
        return {}


def _s2_to_record(data: Dict[str, Any], rec: SourceRecord) -> SourceRecord:
    if not data:
        return rec
    if not rec.title:
        rec.title = data.get("title")
    if not rec.year:
        rec.year = data.get("year")
    if not rec.venue:
        rec.venue = data.get("venue") or rec.venue
    if not rec.abstract and data.get("abstract"):
        rec.abstract = data["abstract"][:_MAX_ABSTRACT_CHARS]
    if not rec.tldr:
        t = data.get("tldr") or {}
        rec.tldr = t.get("text")
    if not rec.authors and data.get("authors"):
        for a in data["authors"]:
            name = a.get("name")
            if name:
                rec.authors.append(SourceAuthor(name=name, s2_id=a.get("authorId")))
    rec.sources_consulted.append("semantic_scholar")
    return rec


# ────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ────────────────────────────────────────────────────────────────────────────
def _cache_key(doi: Optional[str], arxiv_id: Optional[str]) -> str:
    return f"src:{doi or ''}|{arxiv_id or ''}"


async def fetch_source(
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> SourceRecord:
    """
    Pull a SourceRecord for the given identifier.
    Hits Crossref/DataCite/OpenAlex/Unpaywall/S2 in parallel.
    Caches the merged result for CACHE_TTL_SECONDS.
    """
    if not doi and not arxiv_id:
        return SourceRecord()

    key = _cache_key(doi, arxiv_id)
    cached = await _cache_get(key)
    if cached:
        return SourceRecord(
            doi=cached.get("doi"),
            arxiv_id=cached.get("arxiv_id"),
            openalex_id=cached.get("openalex_id"),
            title=cached.get("title"),
            authors=[SourceAuthor(**a) for a in cached.get("authors", [])],
            year=cached.get("year"),
            venue=cached.get("venue"),
            publisher=cached.get("publisher"),
            abstract=cached.get("abstract"),
            tldr=cached.get("tldr"),
            oa_url=cached.get("oa_url"),
            is_retracted=cached.get("is_retracted", False),
            retraction_note=cached.get("retraction_note"),
            sources_consulted=cached.get("sources_consulted", []),
        )

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    rec = SourceRecord(doi=doi, arxiv_id=arxiv_id)
    try:
        results = await asyncio.gather(
            fetch_crossref(client, doi) if doi else asyncio.sleep(0, result={}),
            fetch_datacite(client, doi) if doi else asyncio.sleep(0, result={}),
            fetch_openalex(client, doi, arxiv_id),
            fetch_unpaywall(client, doi) if doi else asyncio.sleep(0, result={}),
            fetch_semantic_scholar(client, doi, arxiv_id),
            return_exceptions=True,
        )
        crossref, datacite, openalex, unpaywall, s2 = [
            (r if not isinstance(r, Exception) else {}) for r in results
        ]
        _crossref_to_record(crossref, rec)
        _datacite_to_record(datacite, rec)
        _openalex_to_record(openalex, rec)
        _unpaywall_to_record(unpaywall, rec)
        _s2_to_record(s2, rec)
    finally:
        if own_client:
            await client.aclose()

    payload = {
        "doi": rec.doi,
        "arxiv_id": rec.arxiv_id,
        "openalex_id": rec.openalex_id,
        "title": rec.title,
        "authors": [{"name": a.name, "s2_id": a.s2_id, "openalex_id": a.openalex_id} for a in rec.authors],
        "year": rec.year,
        "venue": rec.venue,
        "publisher": rec.publisher,
        "abstract": rec.abstract,
        "tldr": rec.tldr,
        "oa_url": rec.oa_url,
        "is_retracted": rec.is_retracted,
        "retraction_note": rec.retraction_note,
        "sources_consulted": rec.sources_consulted,
    }
    await _cache_set(key, payload, ttl=settings.CACHE_TTL_SECONDS)
    return rec


async def fetch_by_title(title: str, client: Optional[httpx.AsyncClient] = None) -> Optional[SourceRecord]:
    """
    Title-only lookup (used when a claim cites a paper without DOI/arXiv).
    Tries OpenAlex search first; returns the top match if title similarity ≥ 0.55.
    """
    if not title or len(title) < 8:
        return None
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    try:
        r = await client.get(
            "https://api.openalex.org/works",
            params={"search": title, "per-page": "3", "mailto": _POLITE_EMAIL},
            timeout=10.0,  # 3s (DOI_TIMEOUT) was too short → mass "could not retrieve"
        )
        if r.status_code != 200:
            return None
        results = (r.json() or {}).get("results") or []
        if not results:
            return None
        from .arxiv_verify import _title_similarity
        best = max(results, key=lambda w: _title_similarity(title, w.get("title") or ""))
        sim = _title_similarity(title, best.get("title") or "")
        if sim < 0.55:
            return None
        doi = (best.get("doi") or "").replace("https://doi.org/", "") or None
        rec = SourceRecord(doi=doi)
        _openalex_to_record(best, rec)
        return rec
    except Exception as e:
        logger.debug(f"Title search failed: {e}")
        return None
    finally:
        if own_client:
            await client.aclose()


async def fetch_by_reference(ref_text: str, client: Optional[httpx.AsyncClient] = None) -> Optional[SourceRecord]:
    """
    Resolve a full reference STRING of ANY citation style (Vancouver, APA, MLA,
    Chicago, IEEE, Harvard, AMA, …) to a source via Crossref bibliographic
    matching, then enrich it (abstract, retraction, …) via fetch_source().

    Style-agnostic on purpose: it matches the ENTIRE reference against Crossref's
    index instead of parsing each format, so it handles references whose title
    isn't quoted (where the per-style parser yields no title). This unlocks the
    source so the alignment step can check whether it supports the citing sentence
    — reference integrity ≠ claim integrity.
    """
    if not ref_text or len(ref_text.strip()) < 15:
        return None
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()
    try:
        r = await client.get(
            "https://api.crossref.org/works",
            params={
                "query.bibliographic": ref_text.strip()[:350],
                "rows": "1",
                "select": "DOI,title,score",
                "mailto": _POLITE_EMAIL,
            },
            timeout=12.0,
        )
        if r.status_code != 200:
            return None
        items = ((r.json() or {}).get("message") or {}).get("items") or []
        if not items:
            return None
        top = items[0]
        doi = (top.get("DOI") or "").lower() or None
        title = (top.get("title") or [""])[0] if top.get("title") else ""
        if not doi or not title or (top.get("score") or 0) < 40:
            return None
        # Guard against spurious matches: most distinctive words of the matched
        # title must actually appear in the reference string.
        words = {w for w in re.findall(r"[a-z0-9]{4,}", title.lower())}
        if words:
            overlap = sum(1 for w in words if w in ref_text.lower()) / len(words)
            if overlap < 0.55:
                return None
        rec = await fetch_source(doi=doi, client=client)
        if rec is not None:
            rec.sources_consulted.append("crossref-bib")
        return rec
    except Exception as e:
        logger.debug(f"Reference (bibliographic) resolution failed: {e}")
        return None
    finally:
        if own_client:
            await client.aclose()


# ── Full-text retrieval (open-access only) ───────────────────────────────────
_MAX_FULLTEXT_CHARS = 60000


def _pdf_bytes_to_text(data: bytes) -> Optional[str]:
    try:
        import io
        from pypdf import PdfReader
        txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        return txt or None
    except Exception:
        return None


def _html_to_text(html: str) -> Optional[str]:
    try:
        h = re.sub(r"(?is)<(script|style|nav|header|footer|figure|table)\b.*?</\1>", " ", html)
        h = re.sub(r"(?s)<[^>]+>", " ", h)
        h = re.sub(r"\s+", " ", h)
        return h or None
    except Exception:
        return None


async def fetch_full_text(rec: "SourceRecord", client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
    """Best-effort full text of a source from an OPEN-ACCESS location — arXiv PDF,
    Unpaywall OA PDF, or OA HTML. Returns extracted text (capped) or None. Never
    raises: alignment must continue (falling back to the abstract) if this fails.
    Lets the engine verify claims whose support is in the body, not the abstract."""
    own = client is None
    if own:
        client = httpx.AsyncClient(follow_redirects=True)
    try:
        candidates: List[tuple] = []
        aid = getattr(rec, "arxiv_id", None)
        # Derive the arXiv id from a synthetic arXiv DOI (10.48550/arXiv.XXXX) when
        # the record didn't carry arxiv_id — the common case when a reference was
        # resolved via the synthetic DOI, which left arxiv_id/oa_url unset.
        if not aid and getattr(rec, "doi", None):
            m = re.match(r"10\.48550/arxiv\.(.+)$", rec.doi, re.IGNORECASE)
            if m:
                aid = m.group(1)
        if aid:
            aid = aid.replace("arXiv:", "").strip()
            candidates.append(("pdf", f"https://arxiv.org/pdf/{aid}"))
        if getattr(rec, "oa_url", None):
            candidates.append(("auto", rec.oa_url))
        for kind, url in candidates:
            try:
                r = await client.get(url, timeout=30.0)
            except Exception:
                continue
            if r.status_code != 200 or not r.content:
                continue
            ct = (r.headers.get("content-type") or "").lower()
            txt = None
            if "pdf" in ct or r.content[:5] == b"%PDF-":
                txt = await asyncio.to_thread(_pdf_bytes_to_text, r.content)
            elif "html" in ct or kind == "auto":
                txt = _html_to_text(r.text)
            if txt and len(txt) > 2000:
                return txt[:_MAX_FULLTEXT_CHARS]
        return None
    except Exception as e:
        logger.debug(f"Full-text fetch failed: {e}")
        return None
    finally:
        if own:
            await client.aclose()


# ── Cited-work resolution by TITLE (no DOI / arXiv id in the text) ───────────
# "Park & Williams (2022) 'Causal Transformers for Time-Series Forecasting'" —
# the dominant fabricated-citation shape in LLM-written text carries no
# identifier at all. Resolve the title across the three big free indexes so the
# engine can (a) ground a real citation (authors / venue / year / abstract) and
# (b) say, with evidence, that no such work exists. `conclusive` counts how many
# registries actually ANSWERED (a timeout / 429 is not "not found").
def _light_tokens(s: str) -> set:
    stop = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "via", "by"}
    out = set()
    for w in re.findall(r"[a-z0-9]+", (s or "").lower()):
        if w in stop:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]  # light plural/singular normalisation
        out.add(w)
    return out


def title_similarity(a: str, b: str) -> float:
    """Token-overlap similarity with light stemming (0..1)."""
    ta, tb = _light_tokens(a), _light_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


async def _oa_title_search(client: httpx.AsyncClient, title: str, year: Optional[int] = None):
    # Title-only search (filter=title.search) is far more precise than the
    # general `search=` (which ranks unrelated full-text hits above an exact
    # title). With a cite year, also prefer the original record over later
    # reprints / chapters carrying the same title.
    safe_title = re.sub(r"[,|:]", " ", title)[:300]
    flt = f"title.search:{safe_title}"
    if year:
        flt += f",publication_year:{year - 1}|{year}|{year + 1}"
    params = {"filter": flt, "per-page": "5", "sort": "cited_by_count:desc", "mailto": _POLITE_EMAIL}
    try:
        r = await client.get(
            "https://api.openalex.org/works",
            params=params,
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return [], False
        out = []
        for w in (r.json() or {}).get("results") or []:
            rec = SourceRecord(doi=((w.get("doi") or "").replace("https://doi.org/", "") or None))
            _openalex_to_record(w, rec)
            out.append((rec, title_similarity(title, w.get("title") or "")))
        return out, True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"OpenAlex title search failed: {e}")
        return [], False


async def _oa_general_search(client: httpx.AsyncClient, title: str):
    try:
        r = await client.get(
            "https://api.openalex.org/works",
            params={"search": title[:300], "per-page": "5", "mailto": _POLITE_EMAIL},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return [], False
        out = []
        for w in (r.json() or {}).get("results") or []:
            rec = SourceRecord(doi=((w.get("doi") or "").replace("https://doi.org/", "") or None))
            _openalex_to_record(w, rec)
            out.append((rec, title_similarity(title, w.get("title") or "")))
        return out, True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"OpenAlex general search failed: {e}")
        return [], False


_ARXIV_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.S)


async def _arxiv_title_search(client: httpx.AsyncClient, title: str):
    """arXiv API title search (free, no key, generous limits) — covers CS /
    physics / math preprints that Crossref lacks and S2 may be too busy to serve."""
    q = re.sub(r"[^A-Za-z0-9 ]+", " ", title)
    q = " AND ".join(f"ti:{w}" for w in q.split()[:12] if len(w) > 2)
    if not q:
        return [], False
    try:
        r = await client.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": q, "max_results": "5"},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return [], False
        out = []
        for entry in _ARXIV_ENTRY_RE.findall(r.text):
            t = re.search(r"<title>(.*?)</title>", entry, re.S)
            t = re.sub(r"\s+", " ", t.group(1)).strip() if t else ""
            aid = re.search(r"<id>https?://arxiv\.org/abs/([^<v]+)", entry)
            summ = re.search(r"<summary>(.*?)</summary>", entry, re.S)
            pub = re.search(r"<published>(\d{4})", entry)
            rec = SourceRecord(arxiv_id=aid.group(1) if aid else None, title=t or None,
                               year=int(pub.group(1)) if pub else None, venue="arXiv")
            rec.authors = [SourceAuthor(name=n.strip()) for n in re.findall(r"<name>(.*?)</name>", entry)][:20]
            if summ:
                rec.abstract = re.sub(r"\s+", " ", summ.group(1)).strip()[:_MAX_ABSTRACT_CHARS]
            rec.sources_consulted.append("arxiv")
            out.append((rec, title_similarity(title, t)))
        return out, True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"arXiv title search failed: {e}")
        return [], False


async def _cr_title_search(client: httpx.AsyncClient, title: str):
    try:
        r = await client.get(
            "https://api.crossref.org/works",
            params={
                "query.title": title[:300], "rows": "5",
                "select": "DOI,title,author,container-title,issued,published-print,published-online,abstract",
                "mailto": _POLITE_EMAIL,
            },
            headers={"User-Agent": f"factcheck-service (mailto:{_POLITE_EMAIL})"},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return [], False
        out = []
        for it in ((r.json() or {}).get("message") or {}).get("items") or []:
            rec = SourceRecord(doi=(it.get("DOI") or "").lower() or None)
            _crossref_to_record(it, rec)
            t = (it.get("title") or [""])[0] if it.get("title") else ""
            out.append((rec, title_similarity(title, t)))
        return out, True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Crossref title search failed: {e}")
        return [], False


async def _s2_title_search(client: httpx.AsyncClient, title: str):
    try:
        from .semantic_scholar import s2_get
        r = await s2_get(
            client, "https://api.semanticscholar.org/graph/v1/paper/search",
            {"query": title[:300], "limit": "5",
             "fields": "title,abstract,tldr,year,venue,authors,externalIds"},
        )
        if r is None or r.status_code != 200:
            return [], False
        out = []
        for pdata in (r.json() or {}).get("data") or []:
            ext = pdata.get("externalIds") or {}
            rec = SourceRecord(doi=(ext.get("DOI") or "").lower() or None,
                               arxiv_id=ext.get("ArXiv"))
            _s2_to_record(pdata, rec)
            out.append((rec, title_similarity(title, pdata.get("title") or "")))
        return out, True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"S2 title search failed: {e}")
        return [], False


async def search_work(title: str, client: Optional[httpx.AsyncClient] = None,
                      year: Optional[int] = None):
    """Resolve a cited work by title across OpenAlex + Crossref + Semantic Scholar.

    Returns (candidates, answered) where candidates is a list of
    (SourceRecord, similarity) sorted best-first (all registries merged) and
    `answered` lists the registries that actually responded (subset of
    openalex / crossref / semantic_scholar / arxiv). A registry that did not
    answer is "could not check", never "no such work".
    """
    if not title or len(title.split()) < 2:
        return [], []
    own = client is None
    if own:
        client = httpx.AsyncClient()
    try:
        searches = [
            _oa_title_search(client, title, year),
            _cr_title_search(client, title),
            _s2_title_search(client, title),
            _arxiv_title_search(client, title),
            _oa_general_search(client, title),          # relevance fallback
        ]
        if year:
            searches.append(_oa_title_search(client, title))  # unfiltered title fallback
        results = await asyncio.gather(*searches, return_exceptions=True)
    finally:
        if own:
            await client.aclose()
    cands = []
    answered: List[str] = []
    names = ["openalex", "crossref", "semantic_scholar", "arxiv", "openalex", "openalex"]
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            continue
        items, ok = res
        if ok and names[i] not in answered:
            answered.append(names[i])
        cands.extend(items)
    cands.sort(key=lambda x: x[1], reverse=True)
    return cands, answered
