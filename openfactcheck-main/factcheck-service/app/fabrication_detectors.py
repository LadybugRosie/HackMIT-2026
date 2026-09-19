"""
Fabrication detectors for research-grade hallucinations.

Each detector runs *cheaply* on the in-text claim and pulls free public APIs
to either ground or flag specific assertions that the article (Athaluri et al.
2023, Ji et al. 2023, Berberette et al. 2024) calls out as the dominant
research hallucinations:

  - numeric_unanchored : precise stats / p-values / sample sizes that are not
                         attached to a DOI, URL, or KB-resolved fact.
  - fabricated_venue   : a journal / conference name that does not exist in
                         OpenAlex `/sources` (closest fuzzy candidate offered).
  - fabricated_institution :
                         a named institute / centre / department that ROR
                         does not know.
  - ghost_author       : authors cited in text whose surname does not appear
                         in Crossref / S2 author list for the cited DOI.

Every detector returns a list of FabricationFlag dicts; the API merges them
into the claim payload.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .ref_integrity import extract_dois, extract_urls
from .settings import settings
from .source_fetcher import SourceRecord, fetch_source

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Regex catalogues
# ────────────────────────────────────────────────────────────────────────────
_PCT_RE       = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?%")
_P_VALUE_RE   = re.compile(r"\bp\s*[<>=]\s*0?\.\d+\b", re.IGNORECASE)
_N_EQ_RE      = re.compile(r"\bn\s*=\s*\d[\d,]*\b", re.IGNORECASE)
_CI_RE        = re.compile(r"\b\d{1,3}\s?%\s*(?:CI|confidence interval)\b", re.IGNORECASE)
_HR_RE        = re.compile(r"\b(?:HR|hazard ratio|odds ratio|OR|relative risk|RR)\s*[:=]?\s*\d", re.IGNORECASE)
_IMPACT_RE    = re.compile(r"\bimpact factor\b[^.]{0,40}\b\d+(?:\.\d+)?\b", re.IGNORECASE)
_HINDEX_RE    = re.compile(r"\bh[-\s]?index\b[^.]{0,30}\b\d{1,3}\b", re.IGNORECASE)

# Venue-name extraction. A venue phrase is a run of Capitalised tokens (plus the
# function words of/on/for/in/the/and/&) that contains a journal-style head noun.
# Only JOURNAL-LIKE venues are checked against OpenAlex /sources — workshops,
# symposia and conference *instances* ("14th ACL Workshop on …") are not
# indexed as sources, so checking them would only produce false alarms.
_VENUE_HEAD_RE = re.compile(
    r"^(?:Journal|Transactions|Annals|Reviews?|Letters|Bulletin|Proceedings|Archives|Magazine)$"
)
_VENUE_FUNCTION_WORDS = {"of", "on", "for", "in", "the", "and", "&", "de", "der", "et"}
_VENUE_SKIP_RE = re.compile(r"\b(Workshop|Symposium|Conference|Meeting|Congress|Seminar)\b|\b\d+(?:st|nd|rd|th)\b")
_VENUE_LEADIN = {"The", "In", "Published", "Presented", "Appeared", "Reported", "See", "Cf"}

# Organisation-LEVEL names only. ROR indexes universities, institutes, labs,
# hospitals, foundations — NOT departments / schools / centres inside them, so
# checking a "Department of X" against ROR would flag every real department.
_INSTITUTION_RE = re.compile(
    r"(?:at|from|of)\s+(?:the\s+)?"
    r"((?:[A-Z][A-Za-z]+\s+){0,3}"
    r"(?:University|Institute|Laboratory|Laboratories|Labs?|College|Academy|Foundation|Hospital|Observatory)\b"
    r"(?:\s+(?:of|for|on)\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4})?)",
)

# Catches "Smith et al.", "Wang et al. (2024)", "Li & Thompson (2023)"
_AUTHOR_CITE_RE = re.compile(
    r"\b([A-Z][a-z]+(?:[-’ʼ'][A-Z][a-z]+)?)"               # surname
    r"(?:\s*(?:&|and)\s+[A-Z][a-z]+(?:[-’ʼ'][A-Z][a-z]+)?)?"  # co-author
    r"\s+et al\.?",
)


@dataclass
class FabricationFlag:
    kind: str
    detail: str
    span: Optional[str] = None
    candidate: Optional[str] = None
    score: float = 0.0
    sources_consulted: List[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# 1. Numeric hallucination guard
# ────────────────────────────────────────────────────────────────────────────
def _numeric_signals(claim: str) -> List[str]:
    """Return the precise numeric spans found in the claim."""
    found: List[str] = []
    for rx in (_PCT_RE, _P_VALUE_RE, _N_EQ_RE, _CI_RE, _HR_RE, _IMPACT_RE, _HINDEX_RE):
        for m in rx.finditer(claim):
            found.append(m.group(0))
    # de-dupe preserving order
    seen, out = set(), []
    for f in found:
        k = f.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out


def detect_numeric_unanchored(claim: str) -> List[FabricationFlag]:
    """A precise numeric assertion without a DOI/URL anchor is suspect."""
    signals = _numeric_signals(claim)
    if not signals:
        return []
    has_anchor = bool(extract_dois(claim)) or bool(extract_urls(claim))
    if has_anchor:
        return []
    # If the claim mentions a generic authority but no resolvable source,
    # treat as unanchored. This catches "According to the WHO, 47.2% of …"
    return [
        FabricationFlag(
            kind="numeric_unanchored",
            detail=(
                "Precise numeric assertion(s) with no DOI/URL anchor: "
                + ", ".join(signals)
            ),
            score=0.85,
        )
    ]


# ────────────────────────────────────────────────────────────────────────────
# 2. Fabricated venue (OpenAlex /sources)
# ────────────────────────────────────────────────────────────────────────────
def _name_similarity(a: str, b: str) -> float:
    """Token similarity with light stemming + containment: 'Bell Labs' inside
    'Nokia Bell Labs', 'Max Planck Institute' inside 'Max Planck Institute for
    Intelligent Systems', 'Science' ~ 'Sciences' all count as a match."""
    from .source_fetcher import title_similarity
    # Only the CLAIMED name nested as a contiguous phrase inside a real name
    # counts ('Bell Labs' in 'Nokia Bell Labs', 'Max Planck Institute' in 'Max
    # Planck Institute for Intelligent Systems'). Token-set containment is too
    # loose: 'British Medical Journal of Medicine' has every token of 'British
    # Journal of Medicine and Medical Research' yet names a different journal;
    # and the reverse direction ('MIT' inside 'MIT Department of X') would let
    # a real parent vouch for a fabricated sub-unit.
    na, nb = _norm_phrase(a), _norm_phrase(b)
    if na and nb and f" {na} " in f" {nb} ":
        return 1.0
    return title_similarity(a, b)


def _norm_phrase(s: str) -> str:
    """Lower-case, stop-word-free, lightly stemmed word sequence."""
    from .source_fetcher import _light_tokens
    out = []
    for w in re.findall(r"[a-z0-9]+", (s or "").lower()):
        if w in {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "via", "by", "&"}:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return " ".join(out)


def extract_venue_phrases(claim: str) -> List[str]:
    """Journal-like venue names mentioned in the claim (see _VENUE_HEAD_RE)."""
    # Keep punctuation as separate tokens so a phrase stops at ( , . ; :
    toks = re.findall(r"[A-Za-z&][A-Za-z&\-']*|[(),.;:]", claim)
    found: List[str] = []
    for i, t in enumerate(toks):
        if not _VENUE_HEAD_RE.match(t):
            continue
        # expand left over Capitalised tokens (not sentence lead-ins)
        lo = i
        while lo - 1 >= 0 and re.match(r"^[A-Z][A-Za-z&\-']*$", toks[lo - 1]) and toks[lo - 1] not in _VENUE_LEADIN:
            lo -= 1
        # expand right over Capitalised tokens and function words
        hi = i
        while hi + 1 < len(toks) and (
            re.match(r"^[A-Z][A-Za-z&\-']*$", toks[hi + 1]) or toks[hi + 1] in _VENUE_FUNCTION_WORDS
        ):
            hi += 1
        words = toks[lo:hi + 1]
        while words and words[-1] in _VENUE_FUNCTION_WORDS:
            words.pop()
        while words and words[0] in _VENUE_FUNCTION_WORDS:
            words.pop(0)
        phrase = " ".join(words)
        # "Physical Review Letters and in the Journal of X" -> two venues.
        parts = [phrase]
        if re.search(r"\s+and\s+", phrase):
            cand = re.split(r"\s+and\s+(?:in\s+)?(?:the\s+)?", phrase)
            if len(cand) > 1 and all(any(_VENUE_HEAD_RE.match(w) for w in c.split()) for c in cand):
                parts = cand
        for part in parts:
            pw = part.split()
            while pw and pw[0] in _VENUE_FUNCTION_WORDS:
                pw.pop(0)
            part = " ".join(pw)
            if len(pw) < 2 or _VENUE_SKIP_RE.search(part):
                continue
            caps = [w for w in pw if w[:1].isupper() and not _VENUE_HEAD_RE.match(w)]
            if not caps:
                continue
            if part not in found:
                found.append(part)
    return found


async def _openalex_venue_lookup(client: httpx.AsyncClient, name: str) -> Tuple[Optional[str], float, bool]:
    """
    Search OpenAlex for a venue by name; return (best_match, similarity, conclusive).
    conclusive=False means the lookup itself failed (timeout / non-200) — the
    caller must NOT flag on that.
    """
    try:
        r = await client.get(
            "https://api.openalex.org/sources",
            params={"search": name, "per-page": "5", "mailto": "factcheck-service@openfactcheck.local"},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return None, 0.0, False
        items = (r.json() or {}).get("results") or []
        if not items:
            return None, 0.0, True
        scored = []
        for it in items:
            names = [it.get("display_name") or ""] + list(it.get("alternate_titles") or []) + list(it.get("abbreviated_title") and [it.get("abbreviated_title")] or [])
            best_local = max(((n, _name_similarity(name, n)) for n in names if n), key=lambda x: x[1], default=("", 0.0))
            scored.append((it.get("display_name") or best_local[0], best_local[1]))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0], scored[0][1], True
    except Exception as e:
        logger.debug(f"OpenAlex venue lookup failed: {e}")
        return None, 0.0, False


async def detect_fabricated_venue(claim: str, client: Optional[httpx.AsyncClient] = None) -> List[FabricationFlag]:
    flags: List[FabricationFlag] = []
    venues = extract_venue_phrases(claim)
    if not venues:
        return flags
    own = client is None
    if own:
        client = httpx.AsyncClient()
    try:
        for venue in venues:
            if len(venue) < 6:
                continue
            best, sim, conclusive = await _openalex_venue_lookup(client, venue)
            if not conclusive:
                continue  # could not check — never a finding
            if sim >= 0.85:
                # Looks real (and matches closely). Skip.
                continue
            if best and sim >= 0.55:
                flags.append(FabricationFlag(
                    kind="fabricated_venue",
                    detail=f"Cited venue '{venue}' not found in OpenAlex; closest real venue: '{best}' (similarity {sim:.2f}).",
                    span=venue,
                    candidate=best,
                    score=1.0 - sim,
                    sources_consulted=["openalex"],
                ))
            else:
                flags.append(FabricationFlag(
                    kind="fabricated_venue",
                    detail=f"Cited venue '{venue}' has no plausible match in OpenAlex /sources.",
                    span=venue,
                    score=0.9,
                    sources_consulted=["openalex"],
                ))
    finally:
        if own:
            await client.aclose()
    return flags


# ────────────────────────────────────────────────────────────────────────────
# 3. Fabricated institution (ROR)
# ────────────────────────────────────────────────────────────────────────────
def _ror_item_names(it: Dict[str, Any]) -> List[str]:
    """
    Extract display-worthy names from a ROR record.
    ROR v2 stores names under `names[]` with `types` containing `ror_display`,
    `label`, `alias`, etc.; older responses also exposed `name` at the top
    level. Be resilient to either.
    """
    out: List[str] = []
    top = it.get("name") or it.get("display_name")
    if top:
        out.append(top)
    for n in it.get("names") or []:
        v = n.get("value")
        if v:
            out.append(v)
    return out


async def _ror_lookup(client: httpx.AsyncClient, name: str) -> Tuple[Optional[str], float, bool]:
    """Returns (best_name, similarity, conclusive). conclusive=False = lookup failed."""
    try:
        r = await client.get(
            "https://api.ror.org/organizations",
            params={"query": name},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return None, 0.0, False
        items = (r.json() or {}).get("items") or []
        if not items:
            return None, 0.0, True
        best_name: Optional[str] = None
        best_sim = 0.0
        for it in items[:5]:
            for nm in _ror_item_names(it):
                sim = _name_similarity(name, nm)
                if sim > best_sim:
                    best_sim, best_name = sim, nm
        return best_name, best_sim, True
    except Exception as e:
        logger.debug(f"ROR lookup failed: {e}")
        return None, 0.0, False


async def _wikipedia_knows_institution(name: str) -> bool:
    """True if an English Wikipedia article exists whose title contains the
    claimed institution name (not a disambiguation page)."""
    try:
        from .wikipedia import get_wikipedia_summary
        from .source_fetcher import _light_tokens
        summary = await get_wikipedia_summary(name)
        if not summary or not summary.get("title"):
            return False
        want = _light_tokens(name)
        have = _light_tokens(summary["title"])
        return bool(want) and want <= have
    except Exception:  # noqa: BLE001
        return False


async def detect_fabricated_institution(claim: str, client: Optional[httpx.AsyncClient] = None) -> List[FabricationFlag]:
    flags: List[FabricationFlag] = []
    matches = list(_INSTITUTION_RE.finditer(claim))
    if not matches:
        return flags
    own = client is None
    if own:
        client = httpx.AsyncClient()
    try:
        seen: set = set()
        for m in matches:
            name = m.group(1).strip().rstrip(",.;:")
            key = name.lower()
            if key in seen or len(name) < 6:
                continue
            seen.add(key)
            best, sim, conclusive = await _ror_lookup(client, name)
            if not conclusive:
                continue  # could not check — never a finding
            if sim >= 0.85:
                continue  # real institution
            # ROR's search ranking misses some famous organisations outright
            # ("Bell Labs" -> Bell Canada). Before flagging, accept a Wikipedia
            # article whose title contains the claimed name as proof it exists.
            if await _wikipedia_knows_institution(name):
                continue
            if best and sim >= 0.55:
                flags.append(FabricationFlag(
                    kind="fabricated_institution",
                    detail=f"Institution '{name}' not in ROR; closest real org: '{best}' (similarity {sim:.2f}).",
                    span=name,
                    candidate=best,
                    score=1.0 - sim,
                    sources_consulted=["ror"],
                ))
            else:
                flags.append(FabricationFlag(
                    kind="fabricated_institution",
                    detail=f"Institution '{name}' has no plausible match in ROR.",
                    span=name,
                    score=0.85,
                    sources_consulted=["ror"],
                ))
    finally:
        if own:
            await client.aclose()
    return flags


# ────────────────────────────────────────────────────────────────────────────
# 4. Ghost author — cited "Smith et al." but Smith isn't a real author of the
#    cited DOI.
# ────────────────────────────────────────────────────────────────────────────
def _surnames_in_text(claim: str) -> List[str]:
    out: List[str] = []
    for m in _AUTHOR_CITE_RE.finditer(claim):
        surname = m.group(1)
        if surname and surname not in out:
            out.append(surname)
    return out


def _author_surnames_in_record(rec: SourceRecord) -> List[str]:
    """Pull surnames (last token) from a SourceRecord's authors."""
    out: List[str] = []
    for a in rec.authors:
        if not a.name:
            continue
        tokens = re.split(r"\s+", a.name.strip())
        if tokens:
            out.append(tokens[-1])
    return out


def _surname_matches(surname: str, rec: SourceRecord) -> bool:
    """True if `surname` is a surname of any author on the record (handles
    multi-token surnames such as 'van Rossum' and accents loosely)."""
    s = surname.lower()
    for a in rec.authors:
        toks = [t.lower().strip(".,") for t in re.split(r"\s+", (a.name or "").strip())]
        if s in toks or (a.name or "").lower().endswith(s):
            return True
    return False


def ghost_author_flags(cited_surnames: List[str], rec: SourceRecord, label: str) -> List[FabricationFlag]:
    """Flag every cited surname that is not an author of the resolved record."""
    if not rec or not rec.authors:
        return []
    flags: List[FabricationFlag] = []
    for surname in cited_surnames:
        if _surname_matches(surname, rec):
            continue
        flags.append(FabricationFlag(
            kind="ghost_author",
            detail=(f"In-text citation names '{surname}' but {label} is authored by: "
                    f"{', '.join([a.name for a in rec.authors[:5]])}."),
            span=surname,
            candidate=", ".join(_author_surnames_in_record(rec)[:5]),
            score=0.85,
            sources_consulted=list(rec.sources_consulted),
        ))
    return flags


async def detect_ghost_author(claim: str) -> List[FabricationFlag]:
    from .citation_alignment import extract_arxiv_ids
    dois = extract_dois(claim)
    arxivs = extract_arxiv_ids(claim)
    if not dois and not arxivs:
        return []
    cited_surnames = _surnames_in_text(claim)
    if not cited_surnames:
        return []
    flags: List[FabricationFlag] = []
    for doi in dois:
        rec = await fetch_source(doi=doi)
        flags.extend(ghost_author_flags(cited_surnames, rec, f"DOI {doi}"))
    for aid in arxivs:
        rec = await fetch_source(arxiv_id=aid)
        flags.extend(ghost_author_flags(cited_surnames, rec, f"arXiv:{aid}"))
    return flags


# ────────────────────────────────────────────────────────────────────────────
# 5. Fabricated grant number — NSF award API + NIH RePORTER (free, no key).
#    Funding statements are a classic LLM confabulation ("NSF Grant IIS-2134567",
#    "NIH R01-GM123456"); both agencies expose public lookups, so a number that
#    does not exist is a grounded finding. Only flags on a definitive empty
#    answer — timeouts / non-200 are inconclusive.
# ────────────────────────────────────────────────────────────────────────────
_NSF_GRANT_RE = re.compile(r"\bNSF\b[^.;]{0,50}?\b(?:[A-Z]{2,4}-)?(\d{7})\b")
_NIH_GRANT_RE = re.compile(r"\b([A-Z]\d{2}|[A-Z]{2}\d|[A-Z]\d[A-Z])\s?-?\s?([A-Z]{2})\s?-?\s?(\d{6})\b")


async def _nsf_award_exists(client: httpx.AsyncClient, award_id: str) -> Optional[bool]:
    try:
        r = await client.get(f"https://api.nsf.gov/services/v1/awards/{award_id}.json",
                             timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS)
        if r.status_code != 200:
            return None
        awards = ((r.json() or {}).get("response") or {}).get("award") or []
        return bool(awards)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"NSF lookup failed: {e}")
        return None


async def _nih_project_exists(client: httpx.AsyncClient, activity: str, ic: str, serial: str) -> Optional[bool]:
    try:
        r = await client.post(
            "https://api.reporter.nih.gov/v2/projects/search",
            json={"criteria": {"project_num_split": {"activity_code": activity, "ic_code": ic,
                                                     "serial_num": serial}},
                  "limit": 3, "include_fields": ["ProjectNum"]},
            timeout=settings.SOURCE_FETCH_TIMEOUT_SECONDS,
        )
        if r.status_code != 200:
            return None
        return bool((r.json() or {}).get("results"))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"NIH RePORTER lookup failed: {e}")
        return None


async def detect_fabricated_grant(claim: str, client: Optional[httpx.AsyncClient] = None) -> List[FabricationFlag]:
    nsf_ids = [m.group(1) for m in _NSF_GRANT_RE.finditer(claim)]
    nih_ids = []
    if re.search(r"\bNIH\b|National Institutes of Health", claim):
        for m in _NIH_GRANT_RE.finditer(claim):
            nih_ids.append((m.group(0), m.group(1), m.group(2), m.group(3)))
    if not nsf_ids and not nih_ids:
        return []
    own = client is None
    if own:
        client = httpx.AsyncClient()
    flags: List[FabricationFlag] = []
    try:
        for aid in nsf_ids:
            exists = await _nsf_award_exists(client, aid)
            if exists is False:
                flags.append(FabricationFlag(
                    kind="fabricated_grant",
                    detail=f"NSF award {aid} does not exist in the NSF Award Search API.",
                    span=aid, score=0.9, sources_consulted=["nsf"],
                ))
        for raw, activity, ic, serial in nih_ids:
            exists = await _nih_project_exists(client, activity, ic, serial)
            if exists is False:
                flags.append(FabricationFlag(
                    kind="fabricated_grant",
                    detail=f"NIH grant {raw} is not in NIH RePORTER (covers FY1985+).",
                    span=raw, score=0.85, sources_consulted=["nih_reporter"],
                ))
    finally:
        if own:
            await client.aclose()
    return flags


# ────────────────────────────────────────────────────────────────────────────
# Public entry-point — run every detector concurrently
# ────────────────────────────────────────────────────────────────────────────
async def detect_all(claim: str) -> List[FabricationFlag]:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            asyncio.to_thread(detect_numeric_unanchored, claim),
            detect_fabricated_venue(claim, client),
            detect_fabricated_institution(claim, client),
            detect_ghost_author(claim),
            detect_fabricated_grant(claim, client),
            return_exceptions=True,
        )
    flags: List[FabricationFlag] = []
    for r in results:
        if isinstance(r, Exception):
            logger.debug(f"Detector failed: {r}")
            continue
        flags.extend(r)
    return flags


def flag_to_dict(f: FabricationFlag) -> Dict[str, Any]:
    return {
        "kind": f.kind,
        "detail": f.detail,
        "span": f.span,
        "candidate": f.candidate,
        "score": f.score,
        "sources_consulted": f.sources_consulted,
    }
