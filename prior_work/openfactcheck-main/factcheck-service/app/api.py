import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException

from .cache import (
    claim_cache_key,
    doi_cache_key,
    get_cached_claims,
    get_cached_doi,
    get_cached_url,
    set_cached_claims,
    set_cached_doi,
    set_cached_url,
    url_cache_key,
)
from .metrics import CACHE_HITS_TOTAL, CACHE_MISSES_TOTAL
from .ofc_engine import evaluate_text
from .rate_limit import rate_limit
from .ref_integrity import (
    DOIMetadata,
    DOIResult,
    DOIStatus,
    ReferenceReport,
    URLResult,
    URLStatus,
    check_doi,
    check_url,
    extract_dois,
    extract_urls,
    normalize_doi,
)
from .schemas import (
    AuditVerdict,
    BibliographyReportResponse,
    CascadeRootModel,
    CitationAlignmentModel,
    CitationCoverage,
    CitationMatrixRow,
    ClaimResult,
    ConfidenceBreakdown,
    ConfidenceScore,
    DOIMetadataResponse,
    DOIResultResponse,
    EvidenceItem,
    FabricationFlagModel,
    FactcheckRequest,
    FactcheckResponse,
    ForensicFinding,
    ForensicReport,
    InternalConsistencyFinding,
    InternalConsistencyResult,
    ReferenceReportResponse,
    ReferenceSummary,
    RiskOverview,
    Summary,
    TaxonomyModel,
    URLResultResponse,
)
from .settings import EvidenceMode, settings
from .citation_alignment import (
    CitationAlignment,
    align_citations,
    alignment_to_dict,
    classify_citation_function,
    score_support,
    _arxiv_to_synthetic_doi,
)
from .numbered_citations import (
    align_numbered_citations,
    build_citation_matrix,
    extract_marker_citations,
    parse_reference_list,
    _resolve_entry,
    _rollup_verdict,
    _worst_support,
)
from .doc_structure import classify_zone, is_pdf_fragment, is_table_row, repair_wrapped_urls, segment_zones
from .internal_consistency import check_internal_consistency
from .forensic_checks import retraction_findings, run_forensic_text_checks
from .citation_styles import (
    detect_style,
    dehyphenate,
    extract_author_year_citations,
    lookup_ref,
    parse_author_year_references,
    parse_references_llm,
)
from .preprocessor import split_sentences
from .source_fetcher import fetch_full_text
from .fabrication_detectors import detect_all as detect_fabrications, flag_to_dict
from .taxonomy import (
    annotate_cascades,
    bib_report_to_dict,
    build_bibliography_report,
    classify as classify_taxonomy,
    taxonomy_to_dict,
)
from .confidence import compute_confidence, compute_severity, detect_domain


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1")


def _build_summary(claims: List[ClaimResult]) -> Summary:
    summary = Summary()
    for claim in claims:
        if claim.verdict == "supported":
            summary.supported += 1
        elif claim.verdict == "unsupported":
            summary.unsupported += 1
        elif claim.verdict == "contradicted":
            summary.contradicted += 1
        elif claim.verdict == "author_claim":
            summary.author_claim += 1
        else:
            summary.unknown += 1
    return summary


# Below this fraction of cited sources actually content-checked, the audit could
# not meaningfully verify the document — it must never be reported as "Looks Good"
# ("0 issues" there means "could not check", not "clean").
_LOW_COVERAGE_RATIO = 0.30


def _is_multi_citation(snippet: str) -> bool:
    """True if the citing sentence cites several references — bracket style
    ("[1, 2, 3]" / "[1-3]") OR author-year style ("(X, 2024; Y, 2022)" — ≥2 years
    or a ';' separator). One source not covering the WHOLE sentence is then
    expected, so it should not be flagged as a problem."""
    s = snippet or ""
    if re.search(r"\[\s*\d+\s*[,;–—-]\s*\d+", s):
        return True
    if ";" in s and re.search(r"(?:19|20)\d\d", s):
        return True
    return len(re.findall(r"(?:19|20)\d\d", s)) >= 2


def _citation_signal_counts(citation_matrix):
    """Split citation findings into CONFIRMED issues vs softer REVIEW flags.

    confirmed: the cited source actively conflicts (contradicted), the claim
    clearly exceeds it (overstated), or the DOI is fabricated and resolves
    nowhere. review: 'unrelated' — but since the engine reads only the ABSTRACT,
    a topically-related source whose abstract omits the cited facet looks
    'unrelated', so this is a verify-vs-full-text flag, NOT a confirmed error.
    Multi-citation sentences never count (one source backs one aspect)."""
    confirmed = review = 0
    for r in (citation_matrix or []):
        sup = getattr(r, "supports_claim", None)
        dst = getattr(r, "doi_status", None)
        scope = getattr(r, "evidence_scope", None)
        multi = _is_multi_citation(getattr(r, "claim_snippet", None))
        # Tool/dataset/method/background/example cites aren't expected to support
        # the sentence — never count their unrelated/partial/overstated as issues.
        is_reference = getattr(r, "citation_function", None) == "reference"
        if dst in ("not_found", "invalid") and scope in (None, "not_retrieved"):
            # DOI not in registries AND the source can't be found by title either.
            # Ambiguous: could be a fabricated citation, OR a truncated DOI (PDF
            # extraction) / a real DOI from an uncommon registrar (EU 10.2760, etc.)
            # on a genuine obscure source. On real peer-reviewed papers it is almost
            # always the latter -> surface for review, do NOT falsely confirm.
            review += 1
        elif sup == "contradicted":
            # A contradiction in a SINGLE-citation sentence is a real, focused
            # issue. Inside a multi-citation list ("[6,28,30,33]") a 'contradicted'
            # is usually a taxonomy/mechanism mismatch (the source backs a sibling
            # claim), so demote it to a review flag.
            if multi:
                review += 1
            else:
                confirmed += 1
        elif sup == "overstated" and not multi and not is_reference:
            # Trust 'overstated' as a CONFIRMED issue only when we read the BODY;
            # an abstract-only 'overstated' is uncertain (the body may back it).
            if scope == "full_text":
                confirmed += 1
            else:
                review += 1
        elif sup == "unrelated" and not multi and not is_reference:
            review += 1
    return confirmed, review


def _build_verdict(summary: Summary, coverage: Optional[CitationCoverage],
                   citation_matrix=None) -> AuditVerdict:
    """Coverage- AND matrix-aware top-line verdict. reference integrity != claim
    integrity: a near-zero-coverage audit (most cited sources unretrievable) says
    'limited verification', not 'looks good'; and a detected citation mismatch or
    fabricated DOI must surface as 'needs review' even if coverage is otherwise
    high (the matrix carries the truth — the headline must not hide it)."""
    confirmed, review = _citation_signal_counts(citation_matrix)
    # General mode has no citation matrix — fall back to claim verdicts there.
    if not citation_matrix:
        confirmed += summary.unsupported + summary.contradicted
    low = bool(coverage and coverage.cited and (coverage.content_checked / coverage.cited) < _LOW_COVERAGE_RATIO)

    # CONFIRMED issues (contradicted source / fabricated DOI / overstatement) are
    # the only thing that warrants "needs review". Soft REVIEW flags ('unrelated'
    # from an abstract-only check) are a "please verify" list, not an error — they
    # must NOT alarm the headline, but are surfaced (count + matrix) so nothing is
    # hidden. Low coverage means we genuinely could not check enough.
    if confirmed:
        head = f"Needs review — {confirmed} issue{'s' if confirmed != 1 else ''} found"
        if review:
            head += f"; {review} more citation{'s' if review != 1 else ''} to verify"
        return AuditVerdict(status="needs_review", headline=head,
                            is_low_coverage=low, issues_found=confirmed, review_flags=review)
    if low:
        unver = coverage.cited - coverage.content_checked
        return AuditVerdict(
            status="limited_verification",
            headline=(f"Limited verification — only {coverage.content_checked} of "
                      f"{coverage.cited} cited sources could be content-checked ({unver} unverifiable)"),
            is_low_coverage=True, issues_found=0, review_flags=review)
    if review:
        return AuditVerdict(
            status="looks_good",
            headline=(f"Looks good — {review} citation{'s' if review != 1 else ''} worth a manual check "
                      "(the cited abstract did not confirm them; verify against full text)"),
            is_low_coverage=False, issues_found=0, review_flags=review)
    return AuditVerdict(status="looks_good", headline="Looks good", review_flags=0)


def _doi_result_to_response(r: DOIResult) -> DOIResultResponse:
    metadata = None
    if r.metadata:
        metadata = DOIMetadataResponse(
            title=r.metadata.title,
            authors=r.metadata.authors,
            year=r.metadata.year,
            venue=r.metadata.venue,
        )
    return DOIResultResponse(
        doi=r.doi,
        status=r.status.value,
        registrar=r.registrar,
        resolved_url=r.resolved_url,
        metadata=metadata,
        note=r.note,
    )


def _url_result_to_response(r: URLResult) -> URLResultResponse:
    return URLResultResponse(
        url=r.url,
        status=r.status.value,
        http_status=r.http_status,
        final_url=r.final_url,
        note=r.note,
    )


def _metadata_to_dict(metadata: Optional[DOIMetadata]) -> Optional[Dict[str, Any]]:
    """Serialize DOIMetadata for caching."""
    if not metadata:
        return None
    return {
        "title": metadata.title,
        "authors": metadata.authors,
        "year": metadata.year,
        "venue": metadata.venue,
        "doi_url": metadata.doi_url,
    }


def _dict_to_metadata(data: Optional[Dict[str, Any]]) -> Optional[DOIMetadata]:
    """Deserialize DOIMetadata from cache."""
    if not data:
        return None
    return DOIMetadata(
        title=data.get("title"),
        authors=data.get("authors", []),
        year=data.get("year"),
        venue=data.get("venue"),
        doi_url=data.get("doi_url"),
    )


async def _check_references(text: str) -> ReferenceReport:
    """
    Extract and validate DOIs/URLs with caching.
    Includes full metadata caching for DOIs.
    """
    dois = extract_dois(text)
    urls = extract_urls(text)

    # Each lookup is independent network I/O, so they run concurrently under a
    # bounded semaphore. asyncio.gather preserves input order, so the report
    # still lists references in the order they appear in the document.
    sem = asyncio.Semaphore(max(1, settings.REFERENCE_CHECK_CONCURRENCY))

    async def _one_doi(doi: str) -> DOIResult:
        cache_key = doi_cache_key(doi)
        cached = await get_cached_doi(cache_key)
        if cached:
            CACHE_HITS_TOTAL.inc()
            return DOIResult(
                doi=cached["doi"],
                status=DOIStatus(cached["status"]),
                registrar=cached.get("registrar"),
                resolved_url=cached.get("resolved_url"),
                metadata=_dict_to_metadata(cached.get("metadata")),
                note=cached.get("note"),
            )
        CACHE_MISSES_TOTAL.inc()
        async with sem:
            result = await check_doi(doi)
        # Cache the result with metadata
        await set_cached_doi(cache_key, {
            "doi": result.doi,
            "status": result.status.value,
            "registrar": result.registrar,
            "resolved_url": result.resolved_url,
            "metadata": _metadata_to_dict(result.metadata),
            "note": result.note,
        })
        return result

    async def _one_url(url: str) -> URLResult:
        cache_key = url_cache_key(url)
        cached = await get_cached_url(cache_key)
        if cached:
            CACHE_HITS_TOTAL.inc()
            return URLResult(
                url=cached["url"],
                status=URLStatus(cached["status"]),
                http_status=cached.get("http_status"),
                final_url=cached.get("final_url"),
                note=cached.get("note"),
            )
        CACHE_MISSES_TOTAL.inc()
        async with sem:
            result = await check_url(url)
        # Add note for sites that return 200 for unknown routes
        if result.status == URLStatus.OK and result.http_status == 200:
            if "editorrah" in url.lower():
                result.note = "Route-level 404 not enforced by site"
        await set_cached_url(cache_key, {
            "url": result.url,
            "status": result.status.value,
            "http_status": result.http_status,
            "final_url": result.final_url,
            "note": result.note,
        })
        return result

    doi_results: List[DOIResult] = list(
        await asyncio.gather(*(_one_doi(d) for d in dois))
    )
    # Check URLs with cache (only in REGISTRY_ONLY or HYBRID mode)
    url_results: List[URLResult] = []
    if settings.EVIDENCE_MODE != EvidenceMode.OFFLINE_ONLY:
        url_results = list(await asyncio.gather(*(_one_url(u) for u in urls)))

    return ReferenceReport(dois=doi_results, urls=url_results)


def _ref_report_to_response(report: ReferenceReport) -> ReferenceReportResponse:
    return ReferenceReportResponse(
        dois=[_doi_result_to_response(d) for d in report.dois],
        urls=[_url_result_to_response(u) for u in report.urls],
        summary=ReferenceSummary(
            total_dois=len(report.dois),
            valid_dois=report.valid_doi_count,
            invalid_dois=report.invalid_doi_count,
            total_urls=len(report.urls),
            broken_urls=report.broken_url_count,
        ),
    )


def _verdict_from_reference_report(claim_text: str, report: ReferenceReport) -> Optional[str]:
    """
    Override verdict based on reference report for DOI/URL claims.
    Returns verdict override or None if no override needed.
    """
    claim_lower = claim_text.lower()
    
    # Extract DOIs from claim
    claim_dois = extract_dois(claim_text)
    
    for doi in claim_dois:
        for doi_result in report.dois:
            if doi_result.doi == doi:
                # If claim is about DOI validity/existence
                if any(keyword in claim_lower for keyword in ['doi', 'reference', 'paper', 'study', 'published']):
                    if doi_result.status in (DOIStatus.INVALID, DOIStatus.NOT_FOUND):
                        # Claims mentioning an invalid DOI should be unsupported
                        return "unsupported"
                    elif doi_result.status == DOIStatus.MISMATCH:
                        # Citation metadata mismatch
                        return "unsupported"
    
    return None


def _fuzzy_title_similarity(title1: str, title2: str) -> float:
    """
    Compute simple token overlap similarity between two titles.
    Returns value between 0 and 1.
    """
    if not title1 or not title2:
        return 0.0
    
    # Tokenize and normalize
    tokens1 = set(re.findall(r'\b\w+\b', title1.lower()))
    tokens2 = set(re.findall(r'\b\w+\b', title2.lower()))
    
    # Remove common stopwords
    stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or', 'but'}
    tokens1 = tokens1 - stopwords
    tokens2 = tokens2 - stopwords
    
    if not tokens1 or not tokens2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    
    return intersection / union if union > 0 else 0.0


def _looks_like_identifier_not_title(s: str) -> bool:
    """True if a quoted string is a URL / DOI / bare identifier rather than a
    human title. Titles contain spaces; identifiers and URLs do not."""
    t = s.strip()
    low = t.lower()
    if low.startswith(("http://", "https://", "doi:", "www.")):
        return True
    if re.match(r'^10\.\d{4,9}/', t):
        return True
    return " " not in t


def _extract_citation_metadata(text: str, doi: str) -> Dict[str, Any]:
    """
    Extract EXPLICIT citation metadata near a DOI in text.
    Returns dict with 'title' and 'year' if found.

    Only explicit citation signals count — a quoted title, or a
    citation-style year close to the DOI. Loose prose ("The study showed
    that...") must NOT be treated as citation metadata, otherwise valid
    DOIs in casual mentions get flagged as MISMATCH.
    """
    metadata = {"title": None, "year": None}

    # Find DOI position in text
    doi_pattern = re.escape(doi)
    match = re.search(doi_pattern, text, re.IGNORECASE)
    if not match:
        return metadata

    # Strip ALL DOI-like substrings from the context before mining it —
    # otherwise digits inside a NEIGHBORING DOI (e.g. 10.9999/qbt.2024.00001)
    # bleed in as a bogus citation "year" for this one.
    _doi_like = re.compile(r'10\.\d{4,9}/[-._;()/:<>A-Za-z0-9]+')

    # Year: search a TIGHT window (±80 chars) and require citation style —
    # parenthesized "(2020)" or "et al., 2020" / "Author, 2020".
    y_start = max(0, match.start() - 80)
    y_end = min(len(text), match.end() + 80)
    year_context = _doi_like.sub(' ', text[y_start:y_end])
    year_match = re.search(
        r'\(\s*(19\d{2}|20\d{2})\s*\)'        # (2020)
        r'|(?:et al\.?,?|[A-Z][a-z]+,)\s+(19\d{2}|20\d{2})\b',  # et al., 2020 / Smith, 2020
        year_context,
    )
    if year_match:
        metadata["year"] = int(year_match.group(1) or year_match.group(2))

    # Title: only an explicitly QUOTED title counts as citation metadata.
    # Pick the quoted title NEAREST the DOI — in a dense reference list several
    # entries' titles fall inside the ±200 window, so taking the first one
    # misattributes a neighbouring entry's title and produces a false MISMATCH.
    start = max(0, match.start() - 200)
    end = min(len(text), match.end() + 200)
    raw_window = text[start:end]
    doi_rel = match.start() - start
    best_title = None
    best_dist = None
    for qm in re.finditer(r'["“]([^"”]{10,})["”]', raw_window):
        cand = qm.group(1).strip()
        # A quoted string is only a TITLE if it reads like one. In HTML the
        # nearest quoted string is the href attribute value, so
        # <a href="https://doi.org/10.1038/nature14539">…</a> was mined as the
        # cited title and compared against the registry, producing a MISMATCH
        # on a perfectly correct citation.
        if _looks_like_identifier_not_title(cand):
            continue
        dist = abs(qm.start() - doi_rel)
        if best_dist is None or dist < best_dist:
            best_title, best_dist = cand, dist
    if best_title:
        metadata["title"] = best_title

    return metadata


def _detect_doi_mismatches(text: str, report: ReferenceReport) -> List[ClaimResult]:
    """
    Detect DOI metadata mismatches and create claims for them.
    Returns list of mismatch claims.
    """
    mismatch_claims = []
    
    for doi_result in report.dois:
        if doi_result.status != DOIStatus.VALID or not doi_result.metadata:
            continue
        
        # Extract citation metadata from text
        citation_meta = _extract_citation_metadata(text, doi_result.doi)
        
        # Check title similarity
        title_mismatch = False
        year_mismatch = False
        
        if citation_meta["title"] and doi_result.metadata.title:
            similarity = _fuzzy_title_similarity(citation_meta["title"], doi_result.metadata.title)
            if similarity < 0.3:  # Threshold: 30% token overlap
                title_mismatch = True
        
        # Check year
        if citation_meta["year"] and doi_result.metadata.year:
            if citation_meta["year"] != doi_result.metadata.year:
                year_mismatch = True
        
        # Create mismatch claim if detected
        if title_mismatch or year_mismatch:
            mismatch_details = []
            if title_mismatch:
                mismatch_details.append(f"Title in citation ('{citation_meta['title']}') does not match DOI metadata ('{doi_result.metadata.title}')")
            if year_mismatch:
                mismatch_details.append(f"Year in citation ({citation_meta['year']}) does not match DOI metadata ({doi_result.metadata.year})")
            
            evidence_snippet = f"DOI {doi_result.doi} metadata: {doi_result.metadata.title}"
            if doi_result.metadata.year:
                evidence_snippet += f" ({doi_result.metadata.year})"
            evidence_snippet += f". Mismatch detected: {'; '.join(mismatch_details)}"
            
            mismatch_evidence = [EvidenceItem(
                source=f"DOI Registry ({doi_result.registrar})",
                snippet=evidence_snippet,
                url=doi_result.resolved_url or f"https://doi.org/{doi_result.doi}",
            )]
            # Compute confidence for mismatch claims
            mismatch_confidence = None
            try:
                from .confidence import compute_confidence
                conf = compute_confidence(
                    verdict="unsupported",
                    evidence=[{"source": e.source, "snippet": e.snippet, "url": e.url} for e in mismatch_evidence],
                    doi_verified=True,
                )
                mismatch_confidence = ConfidenceScore(
                    score=conf["score"],
                    breakdown=ConfidenceBreakdown(
                        source_quality=conf["breakdown"]["source_quality"],
                        evidence_strength=conf["breakdown"]["evidence_strength"],
                        source_agreement=conf["breakdown"]["source_agreement"],
                    ),
                    grade=conf["grade"],
                    explanation=conf["explanation"],
                )
            except Exception:
                pass
            mismatch_claims.append(ClaimResult(
                claim=f"Citation metadata matches DOI metadata for {doi_result.doi}.",
                verdict="unsupported",
                confidence=mismatch_confidence,
                evidence=mismatch_evidence,
            ))
            
            # Update the DOI result status
            doi_result.status = DOIStatus.MISMATCH
            doi_result.note = "; ".join(mismatch_details)
    
    return mismatch_claims


def _add_doi_evidence(claims: List[ClaimResult], report: ReferenceReport,
                      parent_texts: Optional[List[Optional[str]]] = None) -> List[ClaimResult]:
    """
    Add DOI verification evidence to claims that contain DOIs.
    Enforces verdict consistency for invalid/not_found DOIs.
    `parent_texts[i]` is the sentence claim i was decomposed from (if any): a
    sub-claim inherits the DOI status of its parent sentence.
    """
    # Build DOI lookup
    doi_lookup = {d.doi: d for d in report.dois}
    
    enhanced_claims = []
    for ci, claim in enumerate(claims):
        # Check if claim text contains any DOIs (else the parent sentence's)
        lookup_text = claim.claim
        claim_dois = extract_dois(claim.claim)
        parent = parent_texts[ci] if parent_texts and ci < len(parent_texts) else None
        if not claim_dois and parent:
            claim_dois = extract_dois(parent)
            if claim_dois:
                lookup_text = parent
        additional_evidence = []
        
        for doi in claim_dois:
            if doi in doi_lookup:
                result = doi_lookup[doi]
                if result.status == DOIStatus.VALID:
                    source = f"DOI Registry ({result.registrar or 'verified'})"
                    if result.metadata and result.metadata.title:
                        snippet = f"Verified: {result.metadata.title}"
                        if result.metadata.year:
                            snippet += f" ({result.metadata.year})"
                    else:
                        snippet = f"DOI {doi} verified via {result.registrar or 'doi.org'}"
                    additional_evidence.append(EvidenceItem(
                        source=source,
                        snippet=snippet,
                        url=result.resolved_url or f"https://doi.org/{doi}",
                    ))
                elif result.status in (DOIStatus.INVALID, DOIStatus.NOT_FOUND, DOIStatus.MISMATCH):
                    additional_evidence.append(EvidenceItem(
                        source="DOI Registry",
                        snippet=result.note or f"DOI {doi} not found in registries",
                        url="https://doi.org/",
                    ))
        
        # Merge evidence
        all_evidence = list(claim.evidence) + additional_evidence
        
        # Update verdict based on DOI status (enforce consistency)
        verdict = claim.verdict
        
        # Check for verdict override from reference report
        verdict_override = _verdict_from_reference_report(lookup_text, report)
        if verdict_override:
            verdict = verdict_override
        else:
            # Default DOI handling
            for doi in claim_dois:
                if doi in doi_lookup:
                    result = doi_lookup[doi]
                    if result.status in (DOIStatus.INVALID, DOIStatus.NOT_FOUND, DOIStatus.MISMATCH):
                        # Invalid/not_found/mismatch DOI makes claim unsupported
                        if verdict in ("unknown", "supported"):
                            verdict = "unsupported"
        
        enhanced_claims.append(ClaimResult(
            claim=claim.claim,
            verdict=verdict,
            confidence=claim.confidence,
            reasoning=claim.reasoning,
            evidence=all_evidence,
            fabrication_flags=claim.fabrication_flags,
            citation_alignment=claim.citation_alignment,
            taxonomy=claim.taxonomy,
            severity=claim.severity,
            cascade_root=claim.cascade_root,
        ))

    return enhanced_claims


# ========== CONTRADICTION DETECTION ==========

def _word_to_num(word: str) -> Optional[int]:
    """Convert word number to integer."""
    word = word.lower().strip()
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12,
    }
    if word in word_map:
        return word_map[word]
    try:
        return int(word)
    except ValueError:
        return None


def _extract_entity_property_value(claim_text: str) -> Optional[Dict[str, Any]]:
    """
    Extract entity-property-value triples from claims for contradiction detection.
    """
    claim_lower = claim_text.lower()
    
    patterns = [
        # Year events: "X began/fell/started/ended in YEAR"
        (r'(?:the\s+)?(.+?)\s+(?:began|started|fell|ended|was established|was founded)\s+(?:in\s+)?(\d{4})',
         lambda m: {"entity": m.group(1).strip(), "property": "year_event", "value": int(m.group(2))}),
        
        # Berlin Wall specific
        (r'berlin wall\s+(?:fell|came down)\s+(?:in\s+)?(\d{4})',
         lambda m: {"entity": "berlin wall", "property": "year_fell", "value": int(m.group(1))}),
        
        # French Revolution specific
        (r'french revolution\s+(?:began|started)\s+(?:in\s+)?(\d{4})',
         lambda m: {"entity": "french revolution", "property": "year_began", "value": int(m.group(1))}),
        
        # Moons: "X has N moons"
        (r'(\w+)\s+has\s+(\w+|\d+)\s+(?:natural\s+)?(?:moons?|satellites?)',
         lambda m: {"entity": m.group(1).lower(), "property": "moon_count", "value": _word_to_num(m.group(2))}),
        
        # Bones: "skeleton has/contains N bones"
        (r'(?:human\s+)?(?:adult\s+)?skeleton\s+(?:has|contains|consists of)\s+(\d+)\s+bones',
         lambda m: {"entity": "skeleton", "property": "bone_count", "value": int(m.group(1))}),
        
        # Chemical symbols: "symbol for X is Y" or "X has symbol Y"
        (r'(?:chemical\s+)?symbol\s+(?:for|of)\s+(\w+)\s+is\s+(\w+)',
         lambda m: {"entity": m.group(1).lower(), "property": "chemical_symbol", "value": m.group(2).lower()}),
        (r'(\w+)\s+has\s+(?:the\s+)?(?:chemical\s+)?symbol\s+(\w+)',
         lambda m: {"entity": m.group(1).lower(), "property": "chemical_symbol", "value": m.group(2).lower()}),
        (r'(\w+)\s+symbol\s+is\s+(\w+)',
         lambda m: {"entity": m.group(1).lower(), "property": "chemical_symbol", "value": m.group(2).lower()}),
    ]
    
    for pattern, extractor in patterns:
        match = re.search(pattern, claim_lower)
        if match:
            try:
                result = extractor(match)
                if result and result.get("value") is not None:
                    return result
            except (ValueError, IndexError):
                continue
    
    return None


def _run_contradiction_pass(claims: List[ClaimResult]) -> List[ClaimResult]:
    """
    Detect contradictions within the claim set.
    Compares claims about same entity/property with different values.
    """
    # Extract entity-property-value from each claim
    claim_facts: List[Tuple[int, ClaimResult, Dict[str, Any]]] = []
    
    for i, claim in enumerate(claims):
        epv = _extract_entity_property_value(claim.claim)
        if epv:
            claim_facts.append((i, claim, epv))
    
    # Find contradictions
    contradictions_found: Dict[int, List[int]] = {}  # idx -> list of conflicting indices
    
    for i, (idx1, claim1, epv1) in enumerate(claim_facts):
        for idx2, claim2, epv2 in claim_facts[i+1:]:
            # Same entity and property but different value
            if (epv1["entity"] == epv2["entity"] and 
                epv1["property"] == epv2["property"] and
                epv1["value"] != epv2["value"]):
                
                # Mark both as contradictions
                if idx1 not in contradictions_found:
                    contradictions_found[idx1] = []
                contradictions_found[idx1].append(idx2)
                
                if idx2 not in contradictions_found:
                    contradictions_found[idx2] = []
                contradictions_found[idx2].append(idx1)
    
    # Update verdicts for contradicted claims (only if currently unknown)
    updated_claims = []
    for i, claim in enumerate(claims):
        if i in contradictions_found and claim.verdict == "unknown":
            # Add internal contradiction evidence
            conflicting_indices = contradictions_found[i]
            conflict_refs = [claims[j].claim for j in conflicting_indices]
            
            new_evidence = list(claim.evidence)
            new_evidence.append(EvidenceItem(
                source="Internal consistency check",
                snippet=f"This claim contradicts: {'; '.join(conflict_refs[:2])}",
                url=None,
            ))
            
            updated_claims.append(ClaimResult(
                claim=claim.claim,
                verdict="contradicted",
                confidence=claim.confidence,
                reasoning=claim.reasoning,
                evidence=new_evidence,
                fabrication_flags=claim.fabrication_flags,
                citation_alignment=claim.citation_alignment,
                taxonomy=claim.taxonomy,
                severity=claim.severity,
                cascade_root=claim.cascade_root,
            ))
        else:
            updated_claims.append(claim)
    
    return updated_claims


# ────────────────────────────────────────────────────────────────────────────
# Citation alignment (document-level, shared across claims that reference the
# same DOI)
# ────────────────────────────────────────────────────────────────────────────
async def _alignments_for_doc(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Run citation alignment once per document; return a {doi → alignment_dict}
    map that per-claim handlers can look up by extracted DOI.
    """
    if not settings.ENABLE_CITATION_ALIGNMENT:
        return {}
    try:
        alignments = await align_citations(text, max_dois=settings.MAX_ALIGNMENT_DOIS)
    except Exception as e:
        logger.warning(f"Citation alignment failed: {e}")
        return {}
    return {a.doi: alignment_to_dict(a) for a in alignments}


def _alignments_for_claim(
    claim_text: str,
    doc_alignments: Dict[str, Dict[str, Any]],
    numbered_alignments: Optional[List[Dict[str, Any]]] = None,
    parent_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Match the claim to document-level alignments.
    1. Direct: DOIs present in the claim text itself.
    2. Direct: arXiv IDs present in the claim text (matched against synthetic
       10.48550/arXiv.* keys).
    3. Fallback: any author surname mentioned in the claim that matches a
       surname in the alignment's source_authors (catches decomposed
       sub-claims that lost the parent's citation).
    4. Numbered citations: the claim contains the marker ("[14]") or its text
       overlaps the alignment's citing sentence (decomposed sub-claims that
       dropped the marker).
    """
    matched: Dict[str, Dict[str, Any]] = {}
    # 0. Identifiers in the claim itself — and in the PARENT sentence it was
    #    decomposed from. A sub-claim that lost its inline "(doi:…)" still
    #    inherits the citation of the sentence it came from; otherwise the
    #    fabricated / unrelated source is never attached to the facts it backs.
    from .citation_alignment import extract_arxiv_ids, _arxiv_to_synthetic_doi
    for src_text in (claim_text, parent_text or ""):
        for doi in extract_dois(src_text):
            if doi in doc_alignments:
                matched[doi] = doc_alignments[doi]
        for aid in extract_arxiv_ids(src_text):
            synth = _arxiv_to_synthetic_doi(aid)
            if synth in doc_alignments:
                matched[synth] = doc_alignments[synth]

    # Build a set of capitalised tokens from the claim (likely surnames)
    claim_tokens = {t for t in re.findall(r"\b[A-Z][a-z]{2,}\b", claim_text)}
    if claim_tokens:
        for doi, a in doc_alignments.items():
            if doi in matched:
                continue
            authors = a.get("source_authors") or []
            for full_name in authors:
                # Match on any whitespace-separated token in the author's name
                surnames = re.findall(r"\b[A-Z][a-z]{2,}\b", full_name)
                if any(s in claim_tokens for s in surnames):
                    matched[doi] = a
                    break

    # Context overlap for INLINE (doc) alignments: a decomposed sub-claim that
    # lost its inline DOI is still a fragment of the original citing sentence, so
    # attach the alignment when the claim is largely contained in that context.
    # (Mirrors the numbered-citation logic, but keyed on claim-coverage so a
    # short sub-claim still matches its longer citing sentence.)
    claim_words_lc = set(re.findall(r"[a-z0-9]+", claim_text.lower()))
    if claim_words_lc:
        for doi, a in doc_alignments.items():
            if doi in matched:
                continue
            ctx_words = set(re.findall(r"[a-z0-9]+", (a.get("claim_context") or "").lower()))
            if ctx_words and len(claim_words_lc & ctx_words) / len(claim_words_lc) >= 0.6:
                matched[doi] = a

    # Numbered-citation alignments (marker in claim, or sentence overlap)
    if numbered_alignments:
        claim_words = set(re.findall(r"[a-z0-9]+", claim_text.lower()))
        for a in numbered_alignments:
            key = f"n{a.get('cited_number')}:{a.get('claim_context')}"
            if key in matched:
                continue
            marker = a.get("marker")
            if marker and marker in claim_text:
                matched[key] = a
                continue
            ctx_words = set(re.findall(r"[a-z0-9]+", (a.get("claim_context") or "").lower()))
            if ctx_words and len(claim_words & ctx_words) / len(ctx_words) >= 0.6:
                matched[key] = a
    return list(matched.values())


def _alignment_to_pydantic(a: Dict[str, Any]) -> CitationAlignmentModel:
    return CitationAlignmentModel(**a)


def _flag_to_pydantic(f: Dict[str, Any]) -> FabricationFlagModel:
    return FabricationFlagModel(**f)


def _verdict_from_alignment_and_flags(
    base_verdict: str,
    alignments: List[Dict[str, Any]],
    flags: List[Dict[str, Any]],
) -> str:
    """
    Reconcile the base verdict (from the KB/source/LLM pipeline) with the new
    citation-alignment and fabrication-flag evidence.

    Priority order:
      1. contradiction / retraction beats everything.
      2. unrelated / partial alignment → unsupported (downgrade).
      3. fabrication flag (without supporting alignment) → unsupported.
      4. clean supporting alignment with no flags → upgrade to supported.
    """
    if any(a.get("support") == "contradicted" or a.get("is_retracted") for a in alignments):
        return "contradicted"
    # overstated ≠ contradicted, but the claim is not faithfully supported either.
    if any(a.get("support") in ("unrelated", "partial", "overstated") for a in alignments):
        if base_verdict in ("supported", "unknown"):
            return "unsupported"
    if flags:
        kinds = {f["kind"] for f in flags}
        if kinds & {"numeric_unanchored", "fabricated_venue", "fabricated_institution", "ghost_author",
                    "fabricated_citation", "fabricated_grant"}:
            if base_verdict in ("supported", "unknown"):
                return "unsupported"
    # Upgrade only when nothing above downgraded: cited source backs the
    # claim, no fabrication flags, base_verdict is not already a stronger
    # judgement.
    if (
        not flags
        and alignments
        and all(a.get("support") == "supported" for a in alignments)
        and base_verdict in ("unknown", "unsupported")
    ):
        return "supported"
    return base_verdict


def _build_risk_overview(claims: List[ClaimResult]) -> RiskOverview:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for c in claims:
        sev = c.severity or (c.confidence.severity if c.confidence else None) or "low"
        counts[sev] = counts.get(sev, 0) + 1
    return RiskOverview(**counts)


# ════════════════════════════════════════════════════════════════════════════
# Published-paper audit (mode == "published_paper") — citation-aware pipeline.
# Verifies only cited / related-work claims against their mapped reference; the
# paper's own method/result/author claims are labelled "author_claim"
# (self-reported), never externally marked unsupported. Equations / figure /
# table / reference zones are excluded upstream by segment_zones.
# ════════════════════════════════════════════════════════════════════════════
def _rag_passages(full_text: str, claim: str, k: int = 2, size: int = 1400) -> str:
    """Retrieve the chunks of full_text most relevant to the claim (keyword overlap)
    so alignment sees the supporting passage instead of the whole paper. Bounded
    to keep escalation token cost low."""
    kws = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", claim or "")}
    if not full_text:
        return ""
    if not kws:
        return full_text[:3000]
    step = max(1, size - 200)
    chunks = [full_text[i:i + size] for i in range(0, len(full_text), step)]
    def _overlap(c: str) -> int:
        return len(kws & {w.lower() for w in re.findall(r"[A-Za-z0-9\-]+", c)})
    top = sorted(chunks, key=_overlap, reverse=True)[:k]
    return "\n...\n".join(top)[:3000]


async def _align_cite(sentence: str, ref: Any, marker: str, cited_number: Optional[int],
                      ft_budget: Optional[Dict[str, int]] = None) -> CitationAlignment:
    """Resolve a cited reference (numeric ReferenceEntry or author-year AYRef) and
    align the citing sentence against its source via the shared score_support.
    Escalates to OA full text when an evidential cite's abstract is non-decisive."""
    rec = await _resolve_entry(ref)
    ref_doi = getattr(ref, "doi", None)
    ref_arxiv = getattr(ref, "arxiv_id", None)
    canonical = (
        (rec.doi if rec and rec.doi else None)
        or ref_doi
        or (_arxiv_to_synthetic_doi(ref_arxiv) if ref_arxiv else None)
        or marker
    )
    syear = rec.year if rec and rec.year else None
    if syear is None:
        try:
            syear = int(str(getattr(ref, "year", ""))[:4])
        except (ValueError, TypeError):
            syear = None
    a = CitationAlignment(
        doi=canonical,
        claim_context=sentence,
        marker=marker,
        cited_number=cited_number,
        source_title=(rec.title if rec else None) or getattr(ref, "title", None),
        source_year=syear,
        source_authors=[x.name for x in rec.authors[:8]] if rec and rec.authors else [],
        source_venue=rec.venue if rec else None,
        is_retracted=rec.is_retracted if rec else False,
        retraction_note=rec.retraction_note if rec else None,
        sources_consulted=rec.sources_consulted if rec else [],
    )
    if not rec or not rec.sources_consulted:
        a.support = "unknown"
        a.evidence_scope = "not_retrieved"
        a.notes = "Cited reference could not be resolved to a source in any registry."
        return a
    if rec.is_retracted:
        a.notes = f"Cited work is retracted ({rec.retraction_note or 'see registry'})."
    blob = rec.best_text()
    if not blob:
        a.support = "unknown"
        a.evidence_scope = "not_retrieved"
        a.notes = " ".join(p for p in [a.notes, "Source returned no abstract."] if p)
        return a
    # We only ever see the abstract/TL;DR + metadata, never the full paper body —
    # so a non-support verdict is necessarily tentative (honesty rule downstream).
    a.evidence_scope = "abstract" if (rec.abstract or rec.tldr) else "metadata_only"
    # TOKEN SAVER + correctness: skip the LLM content-alignment for REFERENCE cites
    # (tool/dataset/method/background/example) — the source isn't expected to
    # support the sentence, so the call is wasted tokens and would only yield a
    # false "unrelated". ~Half of academic cites are references.
    if classify_citation_function(sentence, marker, a.source_title) == "reference":
        a.support = "unknown"
        a.notes = " ".join(p for p in [a.notes, "Reference cite (tool/dataset/method/background) — not content-aligned."] if p) or None
        return a
    scored = await score_support(sentence, blob, source_label=marker)
    a.support = scored["support"]
    a.supporting_span = scored["supporting_span"]
    a.missing_aspects = scored["missing_aspects"]
    a.confidence = scored["confidence"]
    a.notes = " ".join(p for p in [a.notes, scored.get("notes")] if p) or None

    # ── Full-text escalation ────────────────────────────────────────────────
    # The abstract often omits a detail the citing sentence attributes to the
    # source (e.g. "8 attention heads"). When an EVIDENTIAL cite's abstract
    # verdict is non-decisive, fetch the OA full text, retrieve the relevant
    # passage, and re-check — so body-only facts aren't falsely flagged.
    if (ft_budget is not None and ft_budget.get("n", 0) < ft_budget.get("max", 0)
            and a.support in ("unrelated", "partial", "unknown")
            and classify_citation_function(sentence, marker, a.source_title) == "evidential"):
        full = await fetch_full_text(rec)
        if full:
            ft_budget["n"] = ft_budget.get("n", 0) + 1
            passages = _rag_passages(full, sentence)
            if passages:
                scored2 = await score_support(sentence, passages, source_label=marker)
                if scored2["support"] != "unknown":
                    a.support = scored2["support"]
                    a.supporting_span = scored2["supporting_span"] or a.supporting_span
                    a.missing_aspects = scored2["missing_aspects"]
                    a.confidence = scored2["confidence"]
                    a.evidence_scope = "full_text"
                    a.notes = " ".join(p for p in [a.notes, "[verified against full text]", scored2.get("notes")] if p) or None
    return a


def _pp_evidence(adicts: List[Dict[str, Any]]) -> List[EvidenceItem]:
    """First-class evidence entries from citation alignments (published paper)."""
    items: List[EvidenceItem] = []
    for a in adicts:
        doi = a.get("doi") or ""
        url = f"https://doi.org/{doi}" if doi.startswith("10.") else None
        src = f"Cited source {a.get('marker') or ''} ({a.get('source_venue') or a.get('source_title') or 'unknown'})".replace("  ", " ")
        sup = a.get("support")
        if sup == "supported" and a.get("supporting_span"):
            snippet = f"Supporting span: {a['supporting_span']}"
        elif sup == "contradicted":
            snippet = a.get("notes") or "Cited source contradicts the claim."
        elif sup == "overstated":
            snippet = a.get("notes") or "Claim overstates the cited source."
        elif sup in ("unrelated", "partial"):
            snippet = (a.get("notes") or f"Cited source is {sup} to the claim.")
        else:
            snippet = a.get("notes") or "Cited source could not be verified."
        items.append(EvidenceItem(source=src, snippet=snippet, url=url))
    return items


def _pp_claim_verdict(adicts: List[Dict[str, Any]], sentence: str = "") -> str:
    """Verdict for a CITED claim, abstract-only-honest and non-poisoning:
    any cited source that supports -> supported; abstract evidence that merely
    fails to confirm (unrelated/partial/overstated) -> needs_review (NOT
    'unsupported', since we never see the full paper body). A claim-content
    'contradicted' is only trusted for a CLEAN ATOMIC claim (short, single
    citation) — a long/messy multi-citation chunk is demoted to needs_review,
    because the contradiction may be a chunking artefact, not a real one."""
    sup = [a.get("support") for a in adicts]
    atomic = len(sentence.split()) <= 45 and len(adicts) <= 1
    if any(a.get("is_retracted") for a in adicts):
        return "contradicted"   # retracted source is a real integrity issue regardless
    if any(s == "supported" for s in sup):
        return "supported"
    if any(s == "contradicted" for s in sup):
        return "contradicted" if atomic else "needs_review"
    if any(s in ("overstated", "unrelated", "partial") for s in sup):
        return "needs_review"
    return "unknown"


def _pp_matrix_verdict(support: Optional[str], scope: Optional[str]) -> str:
    """Per-citation matrix verdict. 'unrelated' is kept (abstract clearly off-topic
    is reasonably confident); 'partial' kept; 'overstated'/inconclusive ->
    needs_review; unresolved -> could_not_retrieve."""
    if support == "supported":
        return "supported"
    if support == "contradicted":
        return "contradicted"
    if support == "partial":
        return "partial"
    if support == "unrelated":
        return "unrelated"
    if support == "overstated":
        return "needs_review"
    return "could_not_retrieve" if scope == "not_retrieved" else "needs_review"


def _is_garbled_claim(s: str) -> bool:
    """Figure/equation/chart-label fragment masquerading as a sentence (a PDF
    extraction artefact like 'Hosseini et al. Q(Z|X) Z Y P(X|Z,Y)') — exclude
    from the citation audit so it cannot produce a bogus alignment row."""
    s = (s or "").strip()
    toks = s.split()
    if len(toks) < 4:
        return True
    # equation/variable fragments: P(X|Z,Y), Q(Z|X), or several pipes
    if s.count("|") >= 2 or re.search(r"[A-Z]\([A-Za-z][|,)]", s):
        return True
    alpha = [t for t in toks if any(c.isalpha() for c in t)]
    if not alpha:
        return True
    # a real sentence has lowercase connective words; a chart legend has none
    if sum(1 for t in alpha if t[:1].islower()) == 0 and len(alpha) <= 12:
        return True
    return False


async def _verify_published_paper(repaired: str, ref_report: Optional[ReferenceReport]):
    """Citation-aware claim pipeline. Returns (claims, citation_matrix, warnings)."""
    # Join words split across line breaks ("Hoff-\nmann" -> "Hoffmann") so the
    # reference list and citations parse from real two-column PDF extractions.
    repaired = dehyphenate(repaired)
    structure = segment_zones(repaired)
    body = structure.body_text
    style = detect_style(repaired)

    numeric_refs = parse_reference_list(repaired)                       # {int: ReferenceEntry}
    # LLM-parse the author-year reference list (regex can't handle real ACL PDFs:
    # year-on-next-line, wrapped surnames, suffix years). Falls back to regex.
    ay_refs = await parse_references_llm(structure.references_block)     # {key: AYRef}
    valid_nums = set(numeric_refs.keys())
    # split_sentences reuses the shared extractor; then drop broken PDF fragments
    # (published-paper only — the shared _is_valid_claim is untouched).
    sentences = [s for s in split_sentences(body)
                 if not is_pdf_fragment(s) and not is_table_row(s) and not _is_garbled_claim(s)]
    # Decide superscript-marker detection ONCE at the document level (a per-
    # sentence decision would always see <2 brackets and wrongly enable it,
    # turning words like "Models1" into citations). Only for non-bracket papers.
    enable_superscript = len(re.findall(r"\[\d{1,3}\]", body)) < 2

    doi_status_map: Dict[str, str] = {}
    if ref_report:
        for d in ref_report.dois:
            doi_status_map[normalize_doi(d.doi)] = d.status.value

    sem = asyncio.Semaphore(6)
    matrix_acc: Dict[str, Dict[str, Any]] = {}
    budget = {"n": 0}
    # Published papers have many citations — verify more of them than the default
    # inline-alignment cap so the Citation Support Matrix covers a survey's refs.
    max_align = max(settings.MAX_ALIGNMENT_DOIS, 60)
    # Budget for OA full-text escalation (each costs a PDF/HTML fetch + one extra
    # LLM check, so it is bounded per document).
    ft_budget = ({"n": 0, "max": getattr(settings, "MAX_FULLTEXT_FETCHES", 12)}
                 if getattr(settings, "ENABLE_FULLTEXT_ESCALATION", True) else None)

    _scope_rank = {"full_text": 3, "abstract": 2, "metadata_only": 1, "not_retrieved": 0}

    def _acc(key: str, number: Optional[int], ref: Any, a: CitationAlignment, sentence: str):
        doi = getattr(ref, "doi", None)
        if doi:
            status = doi_status_map.get(normalize_doi(doi), "unknown")
        else:
            status = "no_doi"  # resolution ≠ DOI validity
        row = matrix_acc.setdefault(key, {
            "number": number,
            "reference": (getattr(ref, "title", None) or getattr(ref, "raw", "")[:90]),
            "doi": doi, "doi_status": status, "supports": [], "confs": [],
            "retracted": False, "note": None, "snippet": sentence[:240], "scope": "not_retrieved",
            "evidential": False,
        })
        # A reference is EVIDENTIAL if any citing sentence uses it as evidence (vs
        # tool/dataset/method/background/example). Reference-only cites are neutral.
        if classify_citation_function(sentence, key, getattr(ref, "title", None)) == "evidential":
            row["evidential"] = True
        row["supports"].append(a.support)
        row["confs"].append(int(a.confidence or 0))
        if a.is_retracted:
            row["retracted"] = True
        if a.notes and not row["note"]:
            row["note"] = a.notes
        if _scope_rank.get(a.evidence_scope, 0) > _scope_rank.get(row["scope"], 0):
            row["scope"] = a.evidence_scope or row["scope"]

    async def _process(sentence: str):
        nums: set = set()
        for m in extract_marker_citations(sentence, valid_numbers=valid_nums, enable_superscript=enable_superscript):
            nums |= set(m.numbers)
        ays = extract_author_year_citations(sentence)
        has_citation = bool(nums or ays)
        zone = classify_zone(sentence, has_citation)
        alignments: List[CitationAlignment] = []
        mapped = False
        targets: List[tuple] = []
        for n in sorted(nums):
            if numeric_refs.get(n):
                mapped = True
                targets.append((numeric_refs[n], f"[{n}]", n))
        for c in ays:
            ref = lookup_ref(ay_refs, c.key)   # suffix-aware (2023a/b) with fallback
            if ref:
                mapped = True
                targets.append((ref, c.display, None))
        for ref, marker, number in targets:
            if budget["n"] >= max_align:
                break
            budget["n"] += 1
            async with sem:
                a = await _align_cite(sentence, ref, marker, number, ft_budget=ft_budget)
            alignments.append(a)
            _acc(marker, number, ref, a, sentence)
        return sentence, zone, has_citation, mapped, alignments

    processed = await asyncio.gather(*[_process(s) for s in sentences])

    claims: List[ClaimResult] = []
    for sentence, zone, has_citation, mapped, alignments in processed:
        adicts = [alignment_to_dict(a) for a in alignments]
        if has_citation and adicts:
            verdict = _pp_claim_verdict(adicts, sentence)   # abstract-only-honest, non-poisoning
        elif has_citation:
            verdict = "unknown"           # cited but no reference entry mapped/resolved
        else:
            verdict = "author_claim"      # self-reported method/result/author claim
        reasoning = (
            "Author's own claim about this work (self-reported)."
            if verdict == "author_claim" else None
        )
        claims.append(ClaimResult(
            claim=sentence,
            verdict=verdict,
            zone=zone,
            citation_mapped=mapped,
            citation_alignment=[CitationAlignmentModel(**a) for a in adicts],
            evidence=_pp_evidence(adicts),
            reasoning=reasoning,
        ))

    citation_matrix: List[CitationMatrixRow] = []
    for key, m in matrix_acc.items():
        support = _worst_support(m["supports"])
        scope = m["scope"]
        # A reference cite (tool/dataset/method/background/example) is not expected
        # to "support" the sentence — its abstract not matching is NOT a problem.
        # Keep contradicted/retracted (a contradicting source is an issue either
        # way); neutralise unrelated/partial/overstated to a 'reference' verdict.
        is_reference = (not m.get("evidential", True)) and support not in ("contradicted",)
        cfunc = "reference" if is_reference else "evidential"
        if is_reference and not m["retracted"]:
            mverdict = "reference"
        else:
            mverdict = _pp_matrix_verdict(support, scope)
        used_correctly = (support not in ("unrelated", "contradicted")) if support else None
        citation_matrix.append(CitationMatrixRow(
            citation=key, number=m["number"], reference=m["reference"], doi=m["doi"],
            doi_status=m["doi_status"], metadata_match=None, used_correctly=used_correctly,
            supports_claim=support, is_retracted=m["retracted"],
            verdict=mverdict,
            confidence=max(m["confs"], default=0), note=m["note"],
            claim_snippet=m["snippet"], evidence_scope=scope,
            citation_function=cfunc,
        ))

    # Coverage: of the in-text-cited references that entered the audit, how many
    # we could actually retrieve a source for / content-check. Feeds the honest
    # top-line verdict so "0 issues" is never read as "clean" when we could not
    # check (reference integrity != claim integrity).
    _cov_resolved = sum(1 for r in citation_matrix if r.evidence_scope in ("full_text", "abstract", "metadata_only"))
    _cov_content = sum(1 for r in citation_matrix if r.evidence_scope in ("full_text", "abstract"))
    citation_coverage = CitationCoverage(
        cited=len(citation_matrix),
        resolved=_cov_resolved,
        content_checked=_cov_content,
        not_retrieved=len(citation_matrix) - _cov_resolved,
    )

    warnings: List[str] = []
    n_author = sum(1 for c in claims if c.verdict == "author_claim")
    n_cited = len(claims) - n_author
    excluded = []
    if structure.reference_entry_count:
        excluded.append(f"{structure.reference_entry_count} reference entries")
    if structure.excluded_block_count:
        excluded.append(f"{structure.excluded_block_count} figure/table blocks")
    if structure.header_footer_count:
        excluded.append(f"{structure.header_footer_count} header/author/footer lines")
    if structure.model_output_count:
        excluded.append(f"{structure.model_output_count} model-output blocks")
    references_parsed = len(numeric_refs) + len(ay_refs)
    warnings.append(
        f"Published-paper audit ({style} citations): {n_author} self-reported author claims, "
        f"{n_cited} cited claims checked; {references_parsed} references parsed"
        + (f"; excluded {', '.join(excluded)}." if excluded else ".")
    )
    return claims, citation_matrix, warnings, references_parsed, citation_coverage


async def _build_internal_consistency(text: str) -> Optional[InternalConsistencyResult]:
    """Run the additive internal-consistency pass and wrap it as a model. Never
    raises and never returns anything that touches `claims`."""
    if not settings.ENABLE_INTERNAL_CONSISTENCY:
        return None
    try:
        res = await check_internal_consistency(text)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Internal-consistency pass failed: {e}")
        return None
    return InternalConsistencyResult(
        status=res.get("status", "not_checked"),
        checked=res.get("checked", 0),
        findings=[InternalConsistencyFinding(**f) for f in res.get("findings", [])],
    )


def _build_forensic(text: str, citation_matrix: Optional[List[Any]] = None) -> Optional[ForensicReport]:
    """Run the additive forensic-integrity pass (deterministic text checks +
    retraction screening from the resolved citation matrix). Never raises; never
    touches `claims`."""
    if not settings.ENABLE_FORENSIC_CHECKS:
        return None
    try:
        rep = run_forensic_text_checks(text)
        findings = list(rep.get("findings", []))
        checks_run = list(rep.get("checks_run", []))
        if citation_matrix is not None:
            findings += retraction_findings([
                r.model_dump() if hasattr(r, "model_dump") else r for r in citation_matrix
            ])
            checks_run.append("retraction")
        summary: Dict[str, int] = {}
        for f in findings:
            summary[f["check"]] = summary.get(f["check"], 0) + 1
        return ForensicReport(
            findings=[ForensicFinding(**f) for f in findings],
            checks_run=checks_run,
            summary=summary,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Forensic pass failed: {e}")
        return None


@router.post("/verify", response_model=FactcheckResponse)
async def verify(payload: FactcheckRequest, _rate_key: str = Depends(rate_limit)):
    """
    Verify claims in text with reference integrity, citation-content alignment,
    fabrication detection, hallucination taxonomy, and bibliography consistency.

    Pipeline:
      1. Reference integrity (Crossref / DataCite / doi.org)
      2. Citation-content alignment (Crossref + DataCite + OpenAlex + Unpaywall + S2)
         — strict-RAG LLM check: does the cited source actually support the claim?
      3. Claim evaluation (knowledge base → Wikidata/arXiv/CrossRef → S2/Wikipedia → LLM)
      4. Fabrication detectors (numeric, venue, institution, ghost author)
      5. In-doc contradiction pass
      6. Taxonomy classification + snowball/cascade graph
      7. Bibliography ↔ in-text consistency
      8. Calibrated confidence + domain severity + risk overview

    Evidence modes:
      REGISTRY_ONLY (default), OFFLINE_ONLY, HYBRID.
    """
    warnings: List[str] = []
    ref_report: Optional[ReferenceReport] = None

    # Repair URLs split across line breaks (PDF extraction artefact) before any
    # reference/URL/DOI/alignment work — fixes false 404s on wrapped arXiv links.
    # Safe for all modes: only ever rejoins a truncated URL.
    repaired = repair_wrapped_urls(payload.text)

    # 1. Reference integrity ──────────────────────────────────────────────
    if settings.EVIDENCE_MODE != EvidenceMode.OFFLINE_ONLY:
        try:
            ref_report = await _check_references(repaired)
            warnings.extend(ref_report.get_warnings())
        except Exception as e:
            logger.warning(f"Reference check failed: {e}")
            warnings.append("Reference integrity check partially failed")

    # 1b. Internal numeric-consistency pass (ADDITIVE — separate stage, both
    #     modes). Scans figure-bearing sentences for same-quantity disagreements
    #     and produces its OWN field. It never reads or writes `claims`, the
    #     classifier, segmentation, or any verdict threshold, so it cannot change
    #     how any existing claim is bucketed.
    internal_consistency = await _build_internal_consistency(repaired)

    # 1a. Published-paper audit takes a dedicated citation-aware path (zones +
    #     author-year mapping) and returns early. General mode falls through to
    #     the standard pipeline below (unchanged).
    if payload.mode == "published_paper":
        references_parsed = 0
        citation_coverage = None
        try:
            pp_claims, citation_matrix, pp_warnings, references_parsed, citation_coverage = await _verify_published_paper(repaired, ref_report)
            warnings.extend(pp_warnings)
        except Exception as e:
            logger.warning(f"Published-paper audit failed: {e}")
            pp_claims, citation_matrix = [], []
            warnings.append("Published-paper audit failed; no claims produced.")
        final_claims = [
            ClaimResult(
                claim=c.claim, verdict=c.verdict, confidence=c.confidence, reasoning=c.reasoning,
                evidence=c.evidence if payload.include_evidence else [],
                citation_alignment=c.citation_alignment, zone=c.zone, citation_mapped=c.citation_mapped,
            )
            for c in pp_claims
        ]
        bib_report = None
        if settings.ENABLE_BIBLIOGRAPHY_REPORT and payload.include_reference_report:
            try:
                bib_report = BibliographyReportResponse(**bib_report_to_dict(build_bibliography_report(repaired)))
            except Exception as e:
                logger.debug(f"Bibliography report failed: {e}")
        pp_summary = _build_summary(final_claims)
        return FactcheckResponse(
            summary=pp_summary,
            claims=sorted(final_claims, key=lambda x: x.claim),
            warnings=warnings,
            reference_report=_ref_report_to_response(ref_report) if ref_report and payload.include_reference_report else None,
            bibliography_report=bib_report,
            risk_overview=_build_risk_overview(final_claims),
            citation_matrix=citation_matrix,
            references_parsed=references_parsed,
            citation_coverage=citation_coverage,
            verdict=_build_verdict(pp_summary, citation_coverage, citation_matrix),
            internal_consistency=internal_consistency,
            forensic_checks=_build_forensic(repaired, citation_matrix),
        )

    # 2. Citation-content alignment (one pass per document) ────────────────
    #    Inline DOI/arXiv alignment + numbered-citation alignment (IEEE/journal
    #    papers where the DOI lives only in the reference list).
    doc_alignments: Dict[str, Dict[str, Any]] = {}
    numbered_alignments: List[Dict[str, Any]] = []
    ref_entries: Dict[int, Any] = {}
    if settings.EVIDENCE_MODE != EvidenceMode.OFFLINE_ONLY:
        doc_alignments = await _alignments_for_doc(repaired)
        if settings.ENABLE_NUMBERED_CITATIONS:
            ref_entries = parse_reference_list(repaired)
            if ref_entries:
                try:
                    na = await align_numbered_citations(
                        repaired, max_alignments=settings.MAX_ALIGNMENT_DOIS
                    )
                    numbered_alignments = [alignment_to_dict(a) for a in na]
                except Exception as e:
                    logger.warning(f"Numbered-citation alignment failed: {e}")
                # Prefer sentence-context (numbered) alignments over inline
                # ref-list-DOI alignments: an inline alignment for a DOI that
                # only appears in the reference list was scored against garbage
                # ref-list context, so drop it in favour of the numbered one.
                ref_dois = {normalize_doi(e.doi) for e in ref_entries.values() if e.doi}
                ref_dois |= {a.get("doi") for a in numbered_alignments if a.get("doi")}
                if ref_dois:
                    doc_alignments = {
                        d: a for d, a in doc_alignments.items() if d not in ref_dois
                    }

    # 3. Build context for OFC engine
    context = payload.context or ""
    if ref_report:
        rc = ref_report.build_context()
        if rc:
            context = f"{context}\n\n{rc}" if context else rc

    # 4. Claim evaluation (general/student mode only — published_paper returned
    #    early at stage 1a via the dedicated citation-aware pipeline).
    try:
        claims_raw, ofc_warnings = await evaluate_text(repaired, context, settings.EVIDENCE_MODE)
        warnings.extend(ofc_warnings)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc

    # 5. Per-claim enrichment: cache lookup, fabrication detectors, alignment merge
    cache_keys = [
        claim_cache_key(item["claim"], settings.EVIDENCE_MODE.value, payload.context)
        for item in claims_raw
    ]
    cached = await get_cached_claims(cache_keys)
    cache_updates: Dict[str, Dict[str, Any]] = {}
    claims: List[ClaimResult] = []

    fab_tasks = []
    fab_indices: List[int] = []
    for i, item in enumerate(claims_raw):
        if settings.ENABLE_FABRICATION_DETECTORS:
            fab_tasks.append(detect_fabrications(item["claim"]))
            fab_indices.append(i)
    fab_results_by_index: Dict[int, List[Any]] = {}
    if fab_tasks:
        import asyncio as _aio
        fab_results = await _aio.gather(*fab_tasks, return_exceptions=True)
        for idx, res in zip(fab_indices, fab_results):
            if isinstance(res, Exception):
                fab_results_by_index[idx] = []
            else:
                fab_results_by_index[idx] = res

    for i, (item, key) in enumerate(zip(claims_raw, cache_keys)):
        # Per-claim alignment (lookup from doc-level map + numbered citations)
        claim_alignments = _alignments_for_claim(
            item["claim"], doc_alignments, numbered_alignments, item.get("_parent_claim")
        )
        # Alignment of the claim against a cited work resolved by TITLE /
        # author-year (no DOI in the text) — produced by ofc_engine.
        if item.get("_cited_work_alignment"):
            claim_alignments = claim_alignments + [item["_cited_work_alignment"]]
        # Per-claim fabrication flags (+ ghost-author / unresolvable-title flags
        # from the cited-work resolver)
        fab_flag_objs = fab_results_by_index.get(i, [])
        fab_dicts = [flag_to_dict(f) for f in fab_flag_objs] + list(item.get("_cited_work_flags") or [])

        base_verdict = item["verdict"]
        new_verdict = _verdict_from_alignment_and_flags(base_verdict, claim_alignments, fab_dicts)

        # Evidence (existing pipeline output)
        evidence_dicts = item.get("evidence") or []
        evidence_items = [EvidenceItem(**ev) for ev in evidence_dicts]

        # Add alignment + retraction as first-class evidence entries
        for a in claim_alignments:
            # Numbered citations may resolve to a source with no DOI ("ref-N");
            # only emit a doi.org link when we actually have a DOI.
            a_doi = a.get("doi") or ""
            a_url = f"https://doi.org/{a_doi}" if a_doi.startswith("10.") else None
            marker_prefix = f"{a['marker']} " if a.get("marker") else ""
            src_label = f"Cited source {marker_prefix}({a.get('source_venue') or 'unknown venue'})".replace("  ", " ")
            if a.get("support") == "supported" and a.get("supporting_span"):
                evidence_items.append(EvidenceItem(
                    source=src_label,
                    snippet=f"Supporting span: {a['supporting_span']}",
                    url=a_url,
                ))
            elif a.get("support") == "contradicted":
                evidence_items.append(EvidenceItem(
                    source=src_label,
                    snippet=a.get("notes") or "Cited source contradicts the claim.",
                    url=a_url,
                ))
            elif a.get("support") == "overstated":
                evidence_items.append(EvidenceItem(
                    source=src_label,
                    snippet=(
                        a.get("notes")
                        or "Claim overstates the cited source — it generalises or exaggerates beyond what the source shows."
                    ),
                    url=a_url,
                ))
            elif a.get("support") in ("unrelated", "partial"):
                evidence_items.append(EvidenceItem(
                    source=src_label,
                    snippet=(
                        f"Cited source is {a.get('support')} to the claim. "
                        f"Missing: {', '.join(a.get('missing_aspects', []))}"
                    ).strip(),
                    url=a_url,
                ))
            if a.get("is_retracted"):
                evidence_items.append(EvidenceItem(
                    source="Retraction status",
                    snippet=a.get("retraction_note") or "Cited work is retracted.",
                    url=a_url,
                ))

        # Recompute confidence with new signals
        source_aligned = any(a.get("support") == "supported" for a in claim_alignments)
        conf_data = compute_confidence(
            verdict=new_verdict,
            evidence=[{"source": e.source, "snippet": e.snippet, "url": e.url} for e in evidence_items],
            llm_result=item.get("_llm_result"),
            knowledge_base_match=item.get("_kb_match", False) or item.get("_source_verified", False),
            doi_verified=any("doi registry" in (ev.get("source") or "").lower() for ev in evidence_dicts),
            claim_text=item["claim"],
            citation_alignment=claim_alignments,
            fabrication_flags=fab_dicts,
            source_content_aligned=source_aligned,
        )

        # "Could not check" must not masquerade as "unsupported". If we retrieved
        # NO real external evidence (no KB/DOI/aligned source/sourced evidence)
        # and there is no hard negative (contradicting/retracted source or a
        # concrete fabrication), an "unsupported" verdict is really "unknown" —
        # otherwise true-but-niche research claims get falsely flagged. (Same
        # principle as the coverage headline: don't assert a negative you cannot
        # back. A weak "numeric_unanchored" flag alone is an uncited number, not
        # a falsehood, so it does not count as a hard negative here.)
        if new_verdict == "unsupported":
            _sig = conf_data.get("signals") or {}
            _hard_fab = {"fabricated_venue", "fabricated_institution", "ghost_author",
                         "fabricated_citation", "fabricated_doi", "fabricated_grant", "retracted"}
            _hard_negative = (
                any(a.get("support") in ("contradicted", "unrelated", "overstated") for a in claim_alignments)
                or any(a.get("is_retracted") for a in claim_alignments)
                or any((f.get("kind") in _hard_fab) for f in fab_dicts)
            )
            _no_real_evidence = (
                not _sig.get("kb_match")
                and not _sig.get("doi_resolved")
                and not _sig.get("source_content_aligned")
                and (_sig.get("tier1_sources", 0) or 0) == 0
                and (_sig.get("tier2_sources", 0) or 0) == 0
                and (_sig.get("evidence_with_url", 0) or 0) == 0
                and (_sig.get("citation_alignment_count", 0) or 0) == 0
            )
            # Likewise, a lone numeric_unanchored flag is "an uncited number",
            # not a judgement: when nothing actually JUDGED the claim (no LLM
            # verdict, no KB match, no DOI, no aligned source), topical search
            # hits from S2/Wikipedia must not turn it into "unsupported".
            _weak_flag_only = (
                base_verdict == "unknown"
                and not item.get("_llm_result")
                and bool(fab_dicts)
                and all(f.get("kind") == "numeric_unanchored" for f in fab_dicts)
                and not _sig.get("kb_match")
                and not _sig.get("doi_resolved")
                and not _sig.get("source_content_aligned")
            )
            if (_no_real_evidence or _weak_flag_only) and not _hard_negative:
                new_verdict = "unknown"
                conf_data = compute_confidence(
                    verdict=new_verdict,
                    evidence=[{"source": e.source, "snippet": e.snippet, "url": e.url} for e in evidence_items],
                    llm_result=item.get("_llm_result"),
                    knowledge_base_match=item.get("_kb_match", False) or item.get("_source_verified", False),
                    doi_verified=any("doi registry" in (ev.get("source") or "").lower() for ev in evidence_dicts),
                    claim_text=item["claim"],
                    citation_alignment=claim_alignments,
                    fabrication_flags=fab_dicts,
                    source_content_aligned=source_aligned,
                )

        confidence_score = ConfidenceScore(
            score=conf_data["score"],
            breakdown=ConfidenceBreakdown(**conf_data["breakdown"]),
            grade=conf_data["grade"],
            explanation=conf_data["explanation"],
            signals=conf_data.get("signals") or {},
            failure_mode=conf_data.get("failure_mode"),
            severity=conf_data.get("severity"),
            domain=conf_data.get("domain"),
        )

        # Taxonomy
        taxonomy_obj = classify_taxonomy(
            verdict=new_verdict,
            fabrication_flags=fab_dicts,
            citation_alignment=claim_alignments,
            in_text_contradiction=False,  # set in cascade/contradiction pass below
            has_context_user_provided=bool(payload.context),
        )
        taxonomy_model = TaxonomyModel(**taxonomy_to_dict(taxonomy_obj))

        claim_result = ClaimResult(
            claim=item["claim"],
            verdict=new_verdict,
            confidence=confidence_score,
            reasoning=item.get("_reasoning"),
            evidence=evidence_items,
            fabrication_flags=[_flag_to_pydantic(f) for f in fab_dicts],
            citation_alignment=[_alignment_to_pydantic(a) for a in claim_alignments],
            taxonomy=taxonomy_model,
            severity=confidence_score.severity,
        )
        claims.append(claim_result)
        cache_updates[key] = claim_result.model_dump()

    await set_cached_claims(cache_updates)

    # 6. DOI mismatches + existing in-text contradiction pass
    mismatch_claims: List[ClaimResult] = []
    if ref_report:
        mismatch_claims = _detect_doi_mismatches(repaired, ref_report)
        claims = _add_doi_evidence(claims, ref_report, [it.get("_parent_claim") for it in claims_raw])
    claims = _run_contradiction_pass(claims)

    # 7. Snowball / cascade graph
    raw_claims = [c.model_dump() for c in claims]
    annotated = annotate_cascades(raw_claims)
    for c, ann in zip(claims, annotated):
        root = ann.get("cascade_root")
        if root:
            c.cascade_root = CascadeRootModel(index=root["index"], claim=root["claim"])

    all_claims = claims + mismatch_claims

    # 8. Filter evidence if not requested
    final_claims = [
        ClaimResult(
            claim=c.claim,
            verdict=c.verdict,
            confidence=c.confidence,
            reasoning=c.reasoning,
            evidence=c.evidence if payload.include_evidence else [],
            fabrication_flags=c.fabrication_flags,
            citation_alignment=c.citation_alignment,
            taxonomy=c.taxonomy,
            severity=c.severity,
            cascade_root=c.cascade_root,
        )
        for c in all_claims
    ]

    # 9. Bibliography consistency
    bib_report = None
    if settings.ENABLE_BIBLIOGRAPHY_REPORT and payload.include_reference_report:
        try:
            br = build_bibliography_report(repaired)
            bib_report = BibliographyReportResponse(**bib_report_to_dict(br))
        except Exception as e:
            logger.debug(f"Bibliography report failed: {e}")

    # 10. Citation Support Matrix (published-paper audit). Built after the DOI
    #     mismatch pass so doi statuses reflect any detected mismatch.
    citation_matrix: List[CitationMatrixRow] = []
    if ref_entries and (numbered_alignments or any(e.doi for e in ref_entries.values())):
        doi_status_map: Dict[str, Dict[str, Any]] = {}
        if ref_report:
            for d in ref_report.dois:
                doi_status_map[normalize_doi(d.doi)] = {
                    "status": d.status.value,
                    "title": d.metadata.title if d.metadata else None,
                    "year": d.metadata.year if d.metadata else None,
                }
        cited_numbers = {
            a.get("cited_number") for a in numbered_alignments if a.get("cited_number") is not None
        }
        try:
            matrix_rows = build_citation_matrix(
                ref_entries, numbered_alignments, doi_status_map, cited_numbers
            )
            citation_matrix = [CitationMatrixRow(**r) for r in matrix_rows]
        except Exception as e:
            logger.warning(f"Citation matrix build failed: {e}")

    gen_summary = _build_summary(final_claims)
    return FactcheckResponse(
        summary=gen_summary,
        claims=sorted(final_claims, key=lambda x: x.claim),
        warnings=warnings,
        reference_report=_ref_report_to_response(ref_report) if ref_report and payload.include_reference_report else None,
        bibliography_report=bib_report,
        risk_overview=_build_risk_overview(final_claims),
        citation_matrix=citation_matrix,
        verdict=_build_verdict(gen_summary, None, citation_matrix),
        internal_consistency=internal_consistency,
        forensic_checks=_build_forensic(repaired, citation_matrix),
    )
