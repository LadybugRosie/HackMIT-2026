"""
Citation-content alignment.

For every (in-text claim, cited source) pair, we ask the LLM whether
the source actually supports the claim. The LLM is restricted to a
*single* evidence blob assembled from Crossref/OpenAlex/S2 — it may
not draw on its own parametric memory.

This is the single most useful addition for academic fact-checking:
Athaluri et al. (2023) found 28/178 ChatGPT references had no DOI,
*and* a further 69 had wrong DOIs. The far more common pattern —
correct-looking DOI that points to a real paper that doesn't actually
say what the student wrote — is what this module catches.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from typing import TYPE_CHECKING

from .llm_verifier import _call_llm, _parse_json_response
from .ref_integrity import DOI_PATTERN, normalize_doi, extract_dois
from .settings import settings
from .source_fetcher import SourceRecord, fetch_source

logger = logging.getLogger(__name__)

# How many characters of context around each DOI we use as the in-text claim.
_CITATION_WINDOW = 320

# Canonical alignment outcomes. "overstated" sits between "supported" and
# "partial": the source backs a WEAKER version of the claim, but the claim
# generalises/exaggerates beyond what the source actually shows.
SUPPORT_VALUES = {"supported", "partial", "overstated", "unrelated", "contradicted", "unknown"}


# ── Citation-function classification ─────────────────────────────────────────
# ~Half of academic citations are NOT evidential: the cited source is a TOOL /
# METHOD / MODEL being used ("we use SymSpell [x]"), a named DATASET ("on the
# I-CONECT dataset [x]"), a FOUNDATIONAL/BACKGROUND reference ("the 'text as
# data' movement [x]"), or an illustrative EXAMPLE ("e.g. [x]"). Such a source
# is not expected to "support" the citing sentence, so alignment-scoring it
# yields false "unrelated" flags. Detect these from cue phrases just before the
# marker; reserve content-alignment for EVIDENTIAL cites.
_FN_EXAMPLE = re.compile(r"(e\.g\.|i\.e\.|\bsuch as\b|for example|for instance|\bcf\.)", re.I)
_FN_TOOL = re.compile(
    r"\b(use[sd]?|using|via|employ(?:s|ed|ing)?|appl(?:y|ies|ied)|adopt(?:s|ed|ing)?|"
    r"leverag\w+|implement\w*|based on|built on|build on|fine[- ]?tun\w*|pre[- ]?train\w*|"
    r"trained (?:on|with|using)|with the|run\w* (?:on|with))\b", re.I)
_FN_DATASET = re.compile(r"\b(datasets?|corpus|corpora|benchmarks?|data ?sets?|test sets?|training sets?)\b", re.I)
_FN_BACKGROUND = re.compile(
    r"\b(movement|seminal|foundational|introduced by|proposed by|building on|builds on|"
    r"inspired by|prior work|following the|framework of)\b", re.I)
_FN_TITLE_TOOL = re.compile(
    r"(toolkit|\blibrary\b|symspell|rapidfuzz|sentence-?bert|distilbert|all-mpnet|"
    r":\s*a\s+[\w\- ]+\b(system|tool|toolkit|framework|dataset|benchmark|corpus|library|model)\b)", re.I)


def classify_citation_function(sentence: str, marker: Optional[str] = None,
                               reference_title: Optional[str] = None) -> str:
    """Return 'reference' if the citation is a tool/dataset/method/background/example
    cite (not expected to support the sentence), else 'evidential'. Looks at the
    ~90 chars of text immediately before the citation marker."""
    s = sentence or ""
    before = s
    if marker and marker in s:
        before = s[:s.index(marker)]
    win = before[-90:]
    if (_FN_EXAMPLE.search(win) or _FN_TOOL.search(win)
            or _FN_DATASET.search(win) or _FN_BACKGROUND.search(win)):
        return "reference"
    if reference_title and _FN_TITLE_TOOL.search(reference_title):
        return "reference"
    return "evidential"

# arXiv ID pattern (e.g. arXiv:2605.05134, arXiv 1706.03762v3)
_ARXIV_PATTERN = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


def _arxiv_to_synthetic_doi(arxiv_id: str) -> str:
    """arXiv 2605.05134 → 10.48550/arXiv.2605.05134 (canonical form)."""
    return f"10.48550/arXiv.{arxiv_id}"


def extract_arxiv_ids(text: str) -> List[str]:
    ids: List[str] = []
    seen: set = set()
    for m in _ARXIV_PATTERN.finditer(text):
        aid = m.group(1)
        if aid not in seen:
            seen.add(aid)
            ids.append(aid)
    return ids


@dataclass
class CitationAlignment:
    doi: str
    claim_context: str
    source_title: Optional[str] = None
    source_year: Optional[int] = None
    source_authors: List[str] = field(default_factory=list)
    source_venue: Optional[str] = None
    is_retracted: bool = False
    retraction_note: Optional[str] = None
    # alignment outcome
    support: str = "unknown"   # supported | partial | overstated | unrelated | contradicted | unknown
    supporting_span: Optional[str] = None
    missing_aspects: List[str] = field(default_factory=list)
    confidence: int = 0
    notes: Optional[str] = None
    sources_consulted: List[str] = field(default_factory=list)
    # Numbered-citation provenance (set only by numbered_citations.py): the
    # in-text marker that produced this alignment, e.g. "[14]", and the parsed
    # reference number it resolved to.
    marker: Optional[str] = None
    cited_number: Optional[int] = None
    # What evidence the verdict is based on: "abstract" (title+abstract/tldr),
    # "metadata_only" (no abstract), or "not_retrieved" (source unresolved).
    # Drives the honesty rule: abstract-only must not yield a hard "unsupported".
    evidence_scope: Optional[str] = None


_ALIGNMENT_SYSTEM_PROMPT = """You are a strict source-grounded fact-checker.

You will be shown:
  1. A research-style CLAIM the author wrote in their text.
  2. The METADATA + ABSTRACT of the source they cited.

Your job is to decide whether the source actually supports the claim,
using ONLY the metadata/abstract provided. You may NOT use anything you
remember outside this evidence.

If the abstract does not mention the specifics of the claim, the correct
answer is "unrelated" or "partial" — never "supported".

Return strict JSON:
{
  "support": "supported" | "partial" | "overstated" | "unrelated" | "contradicted" | "unknown",
  "supporting_span": "<short verbatim quote from the abstract that supports the claim, or null>",
  "missing_aspects": ["aspects of the claim NOT covered by the abstract"],
  "confidence": 0-100,
  "notes": "one-sentence rationale"
}

Rules:
- "supported": every checkable specific in the claim is reflected in the abstract.
- "overstated": the abstract supports a WEAKER version of the claim, but the claim
               generalises or exaggerates beyond what the source shows. Example —
               source: "our method improves accuracy on one dataset"; claim:
               "this proves the method is universally superior." Same finding,
               inflated scope/strength.
- "partial":   topic matches but a specific number / actor / date in the claim
               is not in the abstract.
- "unrelated": the abstract is about a different topic from the claim.
- "contradicted": the abstract states the opposite of the claim.
- "unknown":   the abstract is too thin to judge (no abstract, only metadata).
- Use "unknown" sparingly — prefer "partial" or "unrelated" if there is any signal.
- Prefer "overstated" over "supported" when the claim's scope (all / always /
  universally / state-of-the-art on every benchmark) exceeds the source's evidence.
"""


def _citation_context(text: str, doi: str) -> str:
    """Return ~CITATION_WINDOW chars of text surrounding the DOI mention."""
    norm = re.escape(doi)
    m = re.search(norm, text)
    if not m:
        # Try locating by suffix only (handles `doi:` / `https://doi.org/` prefixes)
        for variant in (doi, doi.lower(), doi.upper()):
            m = re.search(re.escape(variant), text)
            if m:
                break
    if not m:
        return text[:_CITATION_WINDOW]
    start = max(0, m.start() - _CITATION_WINDOW // 2)
    end = min(len(text), m.end() + _CITATION_WINDOW // 2)
    return text[start:end].strip()


def _shorten(s: Optional[str], n: int) -> Optional[str]:
    if not s:
        return s
    return s if len(s) <= n else s[: n - 1] + "…"


def _local_backend_score(source_blob: str, ctx: str) -> Optional[Dict[str, Any]]:
    """
    Try the local HF backend (MiniCheck → HHEM, in order of accuracy) and
    return a dict shaped like the LLM response, or None if neither backend
    is available / configured.
    """
    # Pick which local backend to invoke (or all of them for "ensemble").
    from .local_models import get_backend, available_backends

    backend_name = (settings.ALIGNMENT_BACKEND or "openai").lower()
    if backend_name == "openai":
        # The OpenAI path needs a key. Without one it returns nothing, and
        # citation alignment — the ONLY check that catches a real DOI attached
        # to a claim it does not support — silently does nothing at all. That
        # is a hard failure disguised as a clean run: on the bundled eval
        # corpus it scored 0/40 on exactly that class. If local weights are
        # installed, use them instead of degrading to no checking.
        if settings.OPENAI_API_KEY:
            return None
        fallback = next((b for b in ("minicheck", "nli", "hhem")
                         if b in available_backends()), None)
        if not fallback:
            logger.warning(
                "Citation alignment is DISABLED: ALIGNMENT_BACKEND=openai with no "
                "OPENAI_API_KEY, and no local backend installed. Mismatched-citation "
                "detection will not run. Set OPENAI_API_KEY, or "
                "`pip install -r requirements-local.txt` and set ALIGNMENT_BACKEND=nli."
            )
            return None
        logger.info(
            "No OPENAI_API_KEY set; using local alignment backend %r instead of "
            "skipping citation alignment.", fallback,
        )
        backend_name = fallback

    try_order: List[str]
    if backend_name == "minicheck":
        try_order = ["minicheck"]
    elif backend_name == "hhem":
        try_order = ["hhem"]
    elif backend_name == "nli":
        try_order = ["nli"]
    elif backend_name == "ensemble":
        try_order = [b for b in ("minicheck", "nli", "hhem") if b in available_backends()]
    else:
        return None

    if backend_name != "ensemble":
        try_order = [b for b in try_order if b in available_backends()]
    if not try_order:
        logger.warning(
            "ALIGNMENT_BACKEND=%s but no local backend deps are installed; "
            "falling back to OpenAI strict-RAG path.",
            backend_name,
        )
        return None

    scores = []
    for b in try_order:
        try:
            scores.append(get_backend(b).score(source_blob, ctx))
        except Exception as e:
            logger.warning("Local backend %s failed: %s", b, e)

    if not scores:
        return None

    # Ensemble: average probabilities, take the lowest band.
    if len(scores) == 1:
        s = scores[0]
        support, prob, conf = s.support, s.probability, s.confidence
        backend_label = s.backend
    else:
        prob = sum(s.probability for s in scores) / len(scores)
        support = _band_from_prob(prob)
        conf = int(min(s.confidence for s in scores))
        backend_label = "+".join(s.backend for s in scores)

    return {
        "support": support,
        "supporting_span": None,  # neither HHEM nor MiniCheck emit a span
        "missing_aspects": [],
        "confidence": conf,
        "notes": f"Verdict from local backend {backend_label} (prob={prob:.3f}).",
    }


# Re-exported here so _local_backend_score above stays self-contained.
def _band_from_prob(p: float) -> str:
    # Mirror of local_models._band_from_prob — see the rationale there: a scalar
    # supportedness score cannot distinguish off-topic from contradicted.
    if p >= 0.80: return "supported"
    if p >= 0.55: return "partial"
    return "unrelated"


_ALIGN_POS = ("align", "confirm", "support", "consistent", "agree", "matches",
              "in line with", "corroborat")
_ALIGN_NEG = ("contradict", "opposite", "does not align", "not support",
              "doesn't support", "inconsistent", "conflict", "refut", "disagree")


def _reconcile_support(support: str, notes: Optional[str]) -> str:
    """The LLM occasionally labels 'contradicted' while its own rationale says the
    source ALIGNS/CONFIRMS (common when a cited source proposes a related or
    differently-described method, e.g. in a multi-citation taxonomy sentence).
    Trust the reasoning: if the note is clearly positive and contains no
    contradiction language, downgrade to 'partial' so we never raise a FALSE
    contradiction. A genuine contradiction note ('the source states the
    opposite') keeps the verdict."""
    if support != "contradicted" or not notes:
        return support
    nl = notes.lower()
    if any(w in nl for w in _ALIGN_POS) and not any(w in nl for w in _ALIGN_NEG):
        return "partial"
    return support


async def score_support(ctx: str, source_blob: str, source_label: str = "") -> Dict[str, Any]:
    """
    Decide whether `source_blob` supports the claim in `ctx`, using the same
    strict-RAG path the citation aligner uses (local HF backend if configured,
    else the OpenAI no-parametric-memory check). Returns a normalised dict:
        {support, supporting_span, missing_aspects, confidence, notes}

    Shared by `_align_one` (inline DOI/arXiv alignment) and `numbered_citations`
    (in-text marker → reference entry → source alignment) so both produce
    identical verdict semantics, including the "overstated" band.
    """
    # ── Local HF backend (MiniCheck / HHEM / ensemble) ──────────────────────
    local_result = await asyncio.to_thread(_local_backend_score, source_blob, ctx)
    if local_result is not None:
        return {
            "support": local_result["support"],
            "supporting_span": local_result.get("supporting_span"),
            "missing_aspects": local_result.get("missing_aspects") or [],
            "confidence": int(local_result.get("confidence", 50)),
            "notes": local_result.get("notes") or None,
        }

    if not settings.ENABLE_LLM_VERIFICATION:
        return {
            "support": "unknown", "supporting_span": None, "missing_aspects": [],
            "confidence": 0, "notes": "LLM verification disabled; cannot perform alignment.",
        }

    user_prompt = (
        f"CLAIM (with surrounding context):\n\"\"\"\n{ctx}\n\"\"\"\n\n"
        f"CITED SOURCE ({source_label}):\n\"\"\"\n{_shorten(source_blob, 3500)}\n\"\"\"\n\n"
        f"Respond with JSON only."
    )
    try:
        raw = await _call_llm(_ALIGNMENT_SYSTEM_PROMPT, user_prompt)
        parsed = _parse_json_response(raw or "")
        if not parsed:
            return {"support": "unknown", "supporting_span": None, "missing_aspects": [],
                    "confidence": 0, "notes": "LLM returned unparseable response"}
        support = (parsed.get("support") or "unknown").lower()
        if support not in SUPPORT_VALUES:
            support = "unknown"
        notes = parsed.get("notes") or None
        support = _reconcile_support(support, notes)  # trust reasoning over a mislabel
        ma = parsed.get("missing_aspects") or []
        missing = [str(x) for x in ma][:5] if isinstance(ma, list) else []
        try:
            conf = max(0, min(100, int(parsed.get("confidence", 50))))
        except Exception:
            conf = 50
        return {
            "support": support,
            "supporting_span": parsed.get("supporting_span") or None,
            "missing_aspects": missing,
            "confidence": conf,
            "notes": notes,
        }
    except Exception as e:
        logger.warning(f"Citation alignment LLM call failed: {e}")
        return {"support": "unknown", "supporting_span": None, "missing_aspects": [],
                "confidence": 0, "notes": f"Alignment failed: {e}"}


async def _align_one(text: str, identifier: str, kind: str = "doi") -> CitationAlignment:
    """
    `identifier` is either a DOI or an arXiv ID. `kind` distinguishes them.
    For arXiv IDs we still expose a synthetic DOI on the alignment so the
    rest of the pipeline can look it up uniformly.
    """
    if kind == "arxiv":
        rec: SourceRecord = await fetch_source(arxiv_id=identifier)
        canonical = _arxiv_to_synthetic_doi(identifier)
        ctx = _citation_context(text, identifier)
    else:
        rec = await fetch_source(doi=identifier)
        canonical = identifier
        ctx = _citation_context(text, identifier)

    alignment = CitationAlignment(
        doi=canonical,
        claim_context=ctx,
        source_title=rec.title,
        source_year=rec.year,
        source_authors=[a.name for a in rec.authors[:10]],
        source_venue=rec.venue,
        is_retracted=rec.is_retracted,
        retraction_note=rec.retraction_note,
        sources_consulted=rec.sources_consulted,
    )

    # If we got nothing back, mark unknown and bail.
    if not rec.sources_consulted:
        alignment.support = "unknown"
        alignment.notes = "Source could not be retrieved from any registry."
        return alignment

    # If retracted, surface even without LLM call.
    if rec.is_retracted:
        alignment.notes = f"Cited work is retracted ({rec.retraction_note or 'see registry'})"

    source_blob = rec.best_text()
    if not source_blob:
        alignment.support = "unknown"
        alignment.notes = "Source registry returned no abstract or metadata."
        return alignment

    scored = await score_support(ctx, source_blob, source_label=canonical)
    alignment.support = scored["support"]
    alignment.supporting_span = scored["supporting_span"]
    alignment.missing_aspects = scored["missing_aspects"]
    alignment.confidence = scored["confidence"]
    alignment.notes = " ".join(p for p in [alignment.notes, scored.get("notes")] if p) or None
    return alignment


async def align_citations(text: str, max_dois: Optional[int] = None) -> List[CitationAlignment]:
    """
    Run citation alignment for every DOI and arXiv ID in the text.
    Bounded concurrency to keep OpenAI rate-limit headroom.
    """
    targets: List[tuple[str, str]] = [(d, "doi") for d in extract_dois(text)]
    for aid in extract_arxiv_ids(text):
        # Skip arXiv IDs already present as a DataCite-style DOI to avoid dupes.
        synth = _arxiv_to_synthetic_doi(aid).lower()
        if not any(d.lower() == synth for d, _ in targets):
            targets.append((aid, "arxiv"))
    if max_dois is not None:
        targets = targets[:max_dois]
    if not targets:
        return []

    sem = asyncio.Semaphore(5)

    async def _wrapped(ident: str, kind: str) -> CitationAlignment:
        async with sem:
            return await _align_one(text, ident, kind)

    return await asyncio.gather(*[_wrapped(i, k) for i, k in targets])


def alignment_to_dict(a: CitationAlignment) -> Dict[str, Any]:
    return {
        "doi": a.doi,
        "support": a.support,
        "supporting_span": a.supporting_span,
        "missing_aspects": a.missing_aspects,
        "confidence": a.confidence,
        "is_retracted": a.is_retracted,
        "retraction_note": a.retraction_note,
        "source_title": a.source_title,
        "source_authors": a.source_authors,
        "source_year": a.source_year,
        "source_venue": a.source_venue,
        "claim_context": a.claim_context,
        "notes": a.notes,
        "sources_consulted": a.sources_consulted,
        "marker": a.marker,
        "cited_number": a.cited_number,
        "evidence_scope": a.evidence_scope,
    }
