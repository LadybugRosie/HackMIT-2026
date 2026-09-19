"""
OpenFactCheck engine wrapper.
Pipeline: KB → Wikidata/arXiv/CrossRef (parallel, fast) → S2/Wikipedia → LLM (fallback only).
"""
import asyncio
import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple

from .arxiv_verify import verify_arxiv_id, verify_crossref_title
from .cache import get_cached_wikipedia, set_cached_wikipedia, wikipedia_cache_key
from .cited_work import has_citation_anchor, verify_cited_work
from .confidence import compute_confidence
from .llm_verifier import decompose_claim, verify_claim_with_llm
from .semantic_scholar import get_evidence_for_claim as s2_evidence
from .settings import EvidenceMode, settings
from .wikidata import (
    check_person_has_no_nobel,
    verify_capital,
    verify_nobel_prize,
    verify_year_event,
)
from .wikipedia import get_evidence_for_claim

logger = logging.getLogger(__name__)
_engine: Optional[Any] = None

import re

# ── Claim pattern extractors (fast, no LLM) ──

_NOBEL_PATTERN = re.compile(
    r'(\b[A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?(?:[A-Z][a-z]+)?(?:\s+(?:de|van|von|al|el)\s+)?[A-Z][a-z]+)\s+'
    r'(?:won|received|was awarded|earned)\s+(?:the\s+)?(?:a\s+)?Nobel\s+Prize\s*'
    r'(?:in\s+(\w+(?:\s+or\s+\w+)?))?\s*'
    r'(?:in\s+(\d{4}))?',
    re.IGNORECASE,
)

# A Nobel claim that also asserts a RATIONALE ("…for his theory of general
# relativity", "…for the photoelectric effect"). The prize/year KB check cannot
# confirm the rationale, so such claims must NOT be stamped SUPPORTED on the
# prize/year match alone — they are deferred to Wikipedia+LLM (which can check
# the award rationale).
_NOBEL_RATIONALE_RE = re.compile(
    r'\bfor\s+(?:his|her|their|its|the|a|an|discovering|developing|inventing|'
    r'founding|pioneering|work|research|contributions?|discovery|services?|studies)\b',
    re.IGNORECASE,
)

_CAPITAL_PATTERN = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z]\.?[a-z]*)*)\s+is\s+the\s+capital\s+(?:city\s+)?of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
)

_ARXIV_PATTERN = re.compile(r'arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE)

_VENUE_PATTERN = re.compile(
    r'(?:published|appeared|presented)\s+(?:in|at)\s+(?:the\s+)?(?:proceedings\s+of\s+(?:the\s+)?)?'
    r'((?:NeurIPS|NIPS|ICML|ICLR|ACL|NAACL|EMNLP|CVPR|ICCV|ECCV|AAAI|IJCAI|KDD|WWW|SIGIR|CHI)\s*\d{4})',
    re.IGNORECASE,
)

_PAPER_TITLE_PATTERN = re.compile(r"['\u2018\u2019\u201c\u201d\"]((?:[A-Z][^'\"]{10,}?))['\u2018\u2019\u201c\u201d\"]")


def init_engine() -> Any:
    global _engine
    if _engine is not None:
        return _engine
    try:
        import openfactcheck
        for name in ("OpenFactCheck", "OpenFactCheckClient", "Client"):
            cls = getattr(openfactcheck, name, None)
            if cls:
                _engine = cls()
                logger.info("OpenFactCheck initialized", extra={"engine": name})
                return _engine
        if hasattr(openfactcheck, "load_default"):
            _engine = openfactcheck.load_default()
            logger.info("OpenFactCheck initialized", extra={"engine": "load_default"})
            return _engine
        _engine = openfactcheck
        return _engine
    except Exception as e:
        logger.warning(f"OpenFactCheck not available: {e}; using LLM decomposition fallback")
        class _Fallback:
            def evaluate_text(self, text, context=None):
                # Return raw text as a single unknown claim for LLM decomposition
                return {"claims": [{"claim": text, "verdict": "unknown", "evidence": []}], "warnings": ["Using LLM-based verification (openfactcheck unavailable)"]}
        _engine = _Fallback()
        return _engine


def _call_engine(engine, text, context, evidence_mode):
    allow_web = evidence_mode == EvidenceMode.HYBRID
    for name in ("evaluate_text", "factcheck", "run"):
        method = getattr(engine, name, None)
        if method:
            kwargs = {"text": text, "context": context, "allow_web": allow_web}
            sig = inspect.signature(method)
            filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return method(**filtered)
    raise RuntimeError("No engine entrypoint")


def _normalize_claims(raw) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings = []
    if isinstance(raw, dict):
        raw_claims = raw.get("claims") or raw.get("results") or []
        if raw.get("warnings"):
            warnings.extend([str(w) for w in raw["warnings"]])
    elif isinstance(raw, list):
        raw_claims = raw
    else:
        raw_claims = []
        warnings.append("No claims returned")
    claims = []
    for item in raw_claims:
        text = str(item.get("claim") or item.get("text") or "").strip()
        verdict = str(item.get("verdict") or "unknown").lower()
        if verdict not in {"supported", "unsupported", "contradicted", "unknown"}:
            verdict = "unknown"
        evidence = []
        for ev in item.get("evidence") or []:
            evidence.append({
                "source": str(ev.get("source") or ""),
                "snippet": str(ev.get("snippet") or ""),
                "url": ev.get("url"),
            })
        kb_match = verdict in ("supported", "contradicted") and bool(evidence)
        claims.append({
            "claim": text or "unknown",
            "verdict": verdict,
            "evidence": evidence,
            "_kb_match": kb_match,
        })
    return claims, warnings


# ═══════════════════════════════════════════════════════════
# SOURCE-BASED VERIFICATION (fast, parallel, authoritative)
# ═══════════════════════════════════════════════════════════

async def _verify_with_sources(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Verify unknown claims using authoritative sources in parallel:
    Wikidata, arXiv API, CrossRef. No LLM involved.
    """
    tasks = []
    claim_indices = []

    for i, claim in enumerate(claims):
        if claim["verdict"] != "unknown":
            continue

        text = claim["claim"]

        # Nobel Prize claims → Wikidata
        m = _NOBEL_PATTERN.search(text)
        if m:
            person, field, year = m.group(1), m.group(2), m.group(3)
            yr = int(year) if year else None
            tasks.append(_verify_nobel_claim(person, field, yr, text))
            claim_indices.append(i)
            continue

        # Capital claims → Wikidata
        m = _CAPITAL_PATTERN.search(text)
        if m:
            city, country = m.group(1), m.group(2)
            tasks.append(_verify_capital_claim(city, country))
            claim_indices.append(i)
            continue

        # arXiv ID claims → arXiv API
        m = _ARXIV_PATTERN.search(text)
        if m:
            arxiv_id = m.group(1)
            tasks.append(_verify_arxiv_claim(arxiv_id, text))
            claim_indices.append(i)
            continue

        # Cited work WITHOUT an identifier (author-year cite / quoted title) →
        # OpenAlex + Crossref + S2 resolution: registry evidence, ghost-author,
        # wrong-venue, unresolvable-title, and claim-vs-abstract alignment.
        # (Claims carrying a DOI are covered by the inline citation aligner.)
        if not re.search(r"10\.\d{4,9}/", text) and has_citation_anchor(text):
            tasks.append(_verify_cited_work_safe(text))
            claim_indices.append(i)
            continue

    # Run all source checks in parallel
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in zip(claim_indices, results):
            if isinstance(result, Exception) or not result:
                continue
            claim = dict(claims[idx])
            ev_items = list(result.get("evidence_items") or [])
            if result.get("evidence"):
                ev_items.append({
                    "source": result.get("source", "Verified Source"),
                    "snippet": result.get("evidence", ""),
                    "url": result.get("url"),
                })
            if ev_items:
                claim["evidence"] = claim.get("evidence", []) + ev_items
            if result.get("alignment"):
                claim["_cited_work_alignment"] = result["alignment"]
            if result.get("flags"):
                claim["_cited_work_flags"] = result["flags"]
            if result.get("verdict"):
                claim["verdict"] = result["verdict"]
                claim["_source_verified"] = True
            claims[idx] = claim

    return claims


async def _verify_cited_work_safe(text: str) -> Optional[Dict[str, Any]]:
    try:
        return await verify_cited_work(text)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Cited-work verification failed: {e}")
        return None


async def _verify_nobel_claim(person: str, field: Optional[str], year: Optional[int], text: str) -> Optional[Dict[str, Any]]:
    """Verify Nobel Prize claim via Wikidata."""
    # First try positive verification
    result = await verify_nobel_prize(person, field, year)
    if result:
        # A "…for X" rationale (e.g. "for his theory of general relativity") is
        # NOT confirmed by the prize/year match. Do not stamp SUPPORTED on a
        # partial match — defer to Wikipedia+LLM, which can check the award
        # rationale, so a true sub-claim (won the 1921 prize) cannot carry a
        # false one (the wrong reason). A genuine prize/year MISMATCH is still
        # returned (contradicted) — that is definitive regardless of rationale.
        if result.get("verdict") == "supported" and _NOBEL_RATIONALE_RE.search(text):
            return None
        return result

    # Check if person exists but has no Nobel
    no_nobel = await check_person_has_no_nobel(person)
    if no_nobel:
        return {
            "verdict": "contradicted",
            "evidence": no_nobel["evidence"],
            "source": "Wikidata",
        }
    return None


async def _verify_capital_claim(city: str, country: str) -> Optional[Dict[str, Any]]:
    return await verify_capital(city, country)


async def _verify_arxiv_claim(arxiv_id: str, claim_text: str) -> Optional[Dict[str, Any]]:
    """Verify arXiv paper exists and title matches."""
    result = await verify_arxiv_id(arxiv_id)
    if not result:
        return None
    if not result.get("exists"):
        return {
            "verdict": "unsupported",
            "evidence": f"arXiv ID {arxiv_id} does not exist in the arXiv database.",
            "source": "arXiv API",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
        }
    # Paper exists — check if claimed title matches
    real_title = result.get("title", "")
    title_m = _PAPER_TITLE_PATTERN.search(claim_text)
    if title_m:
        claimed_title = title_m.group(1)
        from .arxiv_verify import _title_similarity
        sim = _title_similarity(claimed_title, real_title)
        if sim < 0.3:
            return {
                "verdict": "contradicted",
                "evidence": f"arXiv:{arxiv_id} exists but is titled '{real_title}', not '{claimed_title}'.",
                "source": "arXiv API",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
            }
    return {
        "verdict": "supported",
        "evidence": f"arXiv:{arxiv_id} verified: '{real_title}' by {', '.join(result.get('authors', [])[:3])}.",
        "source": "arXiv API",
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


async def _verify_paper_venue(title: str, claimed_venue: str) -> Optional[Dict[str, Any]]:
    """Verify a paper was published at the claimed venue via CrossRef."""
    result = await verify_crossref_title(title, claimed_venue)
    if not result:
        return None
    if not result.get("found"):
        return None  # Can't verify, leave as unknown
    if "venue_match" in result and not result["venue_match"]:
        return {
            "verdict": "contradicted",
            "evidence": f"'{title}' was published in {result['actual_venue']}, not {claimed_venue}.",
            "source": "CrossRef",
            "url": f"https://doi.org/{result.get('doi', '')}",
        }
    return {
        "verdict": "supported",
        "evidence": f"'{title}' verified in {result.get('venue', claimed_venue)}.",
        "source": "CrossRef",
    }


# ═══════════════════════════════════════════════════════════
# EVIDENCE ENRICHMENT (Wikipedia, Semantic Scholar)
# ═══════════════════════════════════════════════════════════

async def _enrich_with_wikipedia(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not settings.ENABLE_WIKIPEDIA_EVIDENCE:
        return claims
    enriched = []
    for claim in claims:
        if claim["verdict"] == "unknown" and not claim["evidence"]:
            try:
                cache_key = wikipedia_cache_key(claim["claim"])
                cached = await get_cached_wikipedia(cache_key)
                if cached is not None:
                    if cached:
                        claim = dict(claim)
                        claim["evidence"] = cached
                else:
                    wiki_ev = await get_evidence_for_claim(claim["claim"])
                    await set_cached_wikipedia(cache_key, wiki_ev)
                    if wiki_ev:
                        claim = dict(claim)
                        claim["evidence"] = wiki_ev
            except Exception as e:
                logger.debug(f"Wikipedia enrichment failed: {e}")
        enriched.append(claim)
    return enriched


async def _enrich_with_semantic_scholar(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not settings.ENABLE_SEMANTIC_SCHOLAR:
        return claims
    enriched = []
    for claim in claims:
        if claim["verdict"] in ("unknown",) and len(claim.get("evidence", [])) < 2:
            try:
                s2_ev = await s2_evidence(claim["claim"])
                if s2_ev:
                    claim = dict(claim)
                    claim["evidence"] = claim.get("evidence", []) + s2_ev
            except Exception as e:
                logger.debug(f"S2 enrichment failed: {e}")
        enriched.append(claim)
    return enriched


# ═══════════════════════════════════════════════════════════
# LLM VERIFICATION (fallback only — for remaining unknowns)
# ═══════════════════════════════════════════════════════════

async def _verify_with_llm(claims: List[Dict[str, Any]], context: Optional[str]) -> List[Dict[str, Any]]:
    """LLM fallback — ONLY for claims still unknown after all source checks."""
    if not settings.ENABLE_LLM_VERIFICATION:
        return claims

    # Batch: collect all unknown claims, send to LLM concurrently
    unknown_indices = [i for i, c in enumerate(claims) if c["verdict"] == "unknown"]
    if not unknown_indices:
        return claims

    async def _verify_one(idx: int) -> Tuple[int, Optional[Dict]]:
        claim = claims[idx]
        try:
            result = await verify_claim_with_llm(
                claim["claim"],
                evidence_context=context,
                scholarly_evidence=claim.get("evidence") or None,
            )
            return idx, result
        except Exception as e:
            logger.debug(f"LLM failed: {e}")
            return idx, None

    # Run LLM calls concurrently (max 10 at a time to avoid rate limits)
    sem = asyncio.Semaphore(10)

    async def _limited(idx):
        async with sem:
            return await _verify_one(idx)

    results = await asyncio.gather(*[_limited(i) for i in unknown_indices])

    for idx, llm_result in results:
        if not llm_result:
            continue
        claim = dict(claims[idx])
        if llm_result["verdict"] != "unknown":
            claim["verdict"] = llm_result["verdict"]
            snippet = llm_result.get("reasoning", "")
            if snippet:
                claim["evidence"] = claim.get("evidence", []) + [{
                    "source": "AI Analysis",
                    "snippet": snippet,
                    "url": None,
                }]
        claim["_llm_result"] = llm_result
        claim["_reasoning"] = llm_result.get("reasoning", "")
        claims[idx] = claim

    return claims


# ═══════════════════════════════════════════════════════════
# CLAIM DECOMPOSITION & CONFIDENCE
# ═══════════════════════════════════════════════════════════

async def _decompose_claims(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not settings.ENABLE_CLAIM_DECOMPOSITION:
        return claims
    decomposed = []
    for claim in claims:
        # A sentence that cites a source (DOI / arXiv / URL / quoted title /
        # author-year) is verified AS A UNIT against that source. Splitting it
        # strips the identifier from the sub-claims, so the fabricated DOI or
        # unrelated source is never attached to the facts it is supposed to
        # back (the sub-claims came back "unknown" instead of "unsupported").
        if claim["verdict"] != "unknown" or has_citation_anchor(claim["claim"]):
            decomposed.append(claim)
            continue
        try:
            subs = await decompose_claim(claim["claim"])
            if len(subs) > 1:
                for s in subs:
                    decomposed.append({
                        "claim": s, "verdict": "unknown", "evidence": [],
                        "_kb_match": False, "_parent_claim": claim["claim"],
                    })
            else:
                decomposed.append(claim)
        except Exception:
            decomposed.append(claim)
    return decomposed


async def _add_confidence_scores(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not settings.ENABLE_CONFIDENCE_SCORING:
        return claims
    scored = []
    for claim in claims:
        try:
            kb_match = claim.get("_kb_match", False)
            llm_result = claim.get("_llm_result")
            doi_verified = any(
                "doi registry" in (ev.get("source") or "").lower()
                for ev in claim.get("evidence", [])
            )
            source_verified = claim.get("_source_verified", False)
            confidence = compute_confidence(
                verdict=claim["verdict"],
                evidence=claim.get("evidence", []),
                llm_result=llm_result,
                knowledge_base_match=kb_match or source_verified,
                doi_verified=doi_verified,
            )
            claim = dict(claim)
            claim["confidence"] = confidence
        except Exception as e:
            logger.warning(f"Confidence scoring failed for claim: {e}")
            claim = dict(claim)
        scored.append(claim)
    return scored


# ═══════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════

async def evaluate_text(
    text: str,
    context: Optional[str],
    evidence_mode: EvidenceMode,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Enhanced pipeline:
    1. Knowledge base (instant)
    2. Claim decomposition (LLM, only for compound claims)
    3. Re-check decomposed claims against KB
    4. Wikidata + arXiv + CrossRef (parallel, authoritative, fast)
    5. Wikipedia + Semantic Scholar (evidence gathering)
    6. LLM verification (fallback only — remaining unknowns)
    7. Confidence scoring
    """
    if len(text) > settings.MAX_TEXT_CHARS:
        raise ValueError("Text too long")

    engine = init_engine()

    def _run():
        raw = _call_engine(engine, text, context, evidence_mode)
        if asyncio.iscoroutine(raw):
            raw = asyncio.run(raw)
        return _normalize_claims(raw)

    try:
        claims, warnings = await asyncio.wait_for(
            asyncio.to_thread(_run),
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )

        if evidence_mode != EvidenceMode.OFFLINE_ONLY:
            # Step 2: Decompose compound claims
            claims = await _decompose_claims(claims)

            # Step 3: Re-check decomposed claims against KB
            try:
                from openfactcheck import _analyze_claim
                for i, claim in enumerate(claims):
                    if claim.get("_parent_claim") and claim["verdict"] == "unknown":
                        kb = _analyze_claim(claim["claim"])
                        if kb["verdict"] != "unknown":
                            claims[i] = {**claim, **kb, "_kb_match": True}
            except Exception:
                pass

            # Step 4: Source-based verification (Wikidata, arXiv, CrossRef) — FAST
            claims = await _verify_with_sources(claims)

            # Step 5: Evidence enrichment (Wikipedia, S2)
            claims = await _enrich_with_wikipedia(claims)
            claims = await _enrich_with_semantic_scholar(claims)

            # Step 6: LLM fallback (only remaining unknowns, concurrent)
            claims = await _verify_with_llm(claims, context)

        # Step 7: Confidence scores
        claims = await _add_confidence_scores(claims)

        return claims, warnings

    except asyncio.TimeoutError:
        raise TimeoutError("Evaluation timed out")
