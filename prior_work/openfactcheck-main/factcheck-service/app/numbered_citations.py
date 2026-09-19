"""
Numbered-citation alignment for published / IEEE-style papers.

A published paper cites with numbered markers in the body —

    "Transformer models outperform all CNN methods in medical imaging [14]."

— while the DOI / title for reference 14 lives only in the reference list at
the end:

    [14] A. Vaswani et al., "Attention Is All You Need," in Proc. NeurIPS, 2017.

The inline citation aligner (`citation_alignment.py`) only sees DOIs/arXiv IDs
that sit *next to* the claim, so it is blind to numbered citations. This module
bridges the gap:

  1. parse the reference list into {number → ReferenceEntry}
  2. extract in-text markers ([14], [2]-[5], [1, 3, 7], and the [2]–[5] form)
     and the sentence each one sits in
  3. resolve every cited reference to its real source (DOI → arXiv → title)
  4. run the SAME strict-RAG alignment (citation_alignment.score_support) of the
     citing sentence against that source — yielding supported / overstated /
     partial / unrelated / contradicted / unknown.

`build_citation_matrix` then rolls these up, together with the DOI-validity
report, into the journal-grade "Citation Support Matrix".

Core thesis: reference integrity ≠ claim integrity. A real DOI does not mean
the cited source actually supports the sentence that points at it.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .citation_alignment import (
    CitationAlignment,
    _arxiv_to_synthetic_doi,
    score_support,
)
from .ref_integrity import extract_dois, normalize_doi
from .citation_alignment import extract_arxiv_ids
from .doc_structure import repair_wrapped_urls, segment_zones
from .settings import settings
from .source_fetcher import SourceRecord, fetch_by_reference, fetch_by_title, fetch_source
from .taxonomy import _split_body_and_bib

logger = logging.getLogger(__name__)

# Severity order used to pick the most concerning support verdict when one
# reference is cited by several sentences.
_SUPPORT_SEVERITY = {
    "contradicted": 5,
    "overstated": 4,
    "unrelated": 3,
    "partial": 2,
    "unknown": 1,
    "supported": 0,
}

# A reference entry header: "[14] A. Vaswani et al., ..." up to the next "[n]"
# at line start (or end of bib). MULTILINE so ^ matches each line; DOTALL so an
# entry can wrap across lines.
_ENTRY_BRACKET_RE = re.compile(
    r"^\s*\[(\d{1,3})\]\s*(.+?)(?=\n\s*\[\d{1,3}\]\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
# Fallback for "1. Author, ..." style reference lists (used only when the
# bracket style finds nothing, to avoid matching body section numbers).
_ENTRY_DOT_RE = re.compile(
    r"^\s*(\d{1,3})\.\s+(.+?)(?=\n\s*\d{1,3}\.\s|\Z)",
    re.MULTILINE | re.DOTALL,
)

# In-text marker: [14], [2-5], [2–5], [1, 3, 7] (after [a]–[b] normalisation).
_MARKER_RE = re.compile(
    r"\[(\d{1,3}(?:\s*[-–—]\s*\d{1,3})?(?:\s*,\s*\d{1,3}(?:\s*[-–—]\s*\d{1,3})?)*)\]"
)
# Range written across two brackets: "[2]–[5]" / "[2]-[5]".
_CROSS_RANGE_RE = re.compile(r"\[(\d{1,3})\]\s*[-–—]\s*\[(\d{1,3})\]")
# Superscript citation markers (Nature/Science): a digit-run GLUED to the end of
# a word with no space — "models1,2", "datasets9–11". Distinguished from years /
# quantities (which have a space before the number) by the no-space attachment.
# `(?<![\d.\-])` avoids decimals/hyphenated versions; `(?=[^\w]|$)` requires the
# run to end at the word (so "H2O" — 2 followed by O — is not matched).
_SUPERSCRIPT_RE = re.compile(
    r"(?<![\d.\-])(?<=[A-Za-z])(\d{1,3}(?:[–—-]\d{1,3})?(?:,\s?\d{1,3}(?:[–—-]\d{1,3})?)*)(?=[^\w]|$)"
)
# Tokens that legitimately end in digits and must NOT be read as a superscript
# citation: model/version names, chemicals, units, cross-refs.
# Tokens that legitimately end in digits and must NOT be read as a superscript
# citation. NOTE: kept tight on purpose — common nouns like "models"/"layer" are
# NOT denylisted because real Nature superscripts attach to them ("models1,2").
# The document-level enable_superscript gate (no superscript pass in bracket-style
# papers) + the "every number must be a real reference" check are the primary
# guards; this list only catches model/version/chemical/unit/cross-ref tokens.
_SUPERSCRIPT_DENY_RE = re.compile(
    r"(?:gpt|llama|llm|gemma|mistral|qwen|resnet|vgg|bert|roberta|electra|bloom|"
    r"bleu|rouge|covid|sars|cov|"
    r"co|h|o|n|p|t|v|k|fig|figure|table|tab|section|sect|eq|equation|ref|"
    r"chapter|ch|vol|no|version|gb|mb|kb|tb|ghz|mhz|nm|mm|cm|km|kg|mg|ml|top)$",
    re.IGNORECASE,
)
# Sentence terminator followed by whitespace.
_SENT_END_RE = re.compile(r"[.!?]\s")
# Quoted title inside a reference entry (straight or curly quotes).
_QUOTED_TITLE_RE = re.compile(r"[“\"]([^”\"]{6,})[”\"]")
# IEEE author tokens: "A. Vaswani", "N. Shazeer".
_AUTHOR_TOKEN_RE = re.compile(r"\b[A-Z]\.\s*([A-Z][a-z]+)")
# arXiv ID embedded in an arxiv.org URL (Nature-style refs cite the URL, not
# the "arXiv:" prefix): https://arxiv.org/abs/2302.09664
_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.IGNORECASE)


@dataclass
class ReferenceEntry:
    number: int
    raw: str
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None


@dataclass
class MarkerMention:
    numbers: List[int]
    sentence: str


# ────────────────────────────────────────────────────────────────────────────
# Parsing
# ────────────────────────────────────────────────────────────────────────────
def _parse_entry(number: int, raw: str) -> ReferenceEntry:
    raw = raw.strip()
    dois = extract_dois(raw)
    arxiv = extract_arxiv_ids(raw)
    arxiv_id = arxiv[0] if arxiv else None
    if not arxiv_id:
        m = _ARXIV_URL_RE.search(raw)
        if m:
            arxiv_id = m.group(1)
    title_m = _QUOTED_TITLE_RE.search(raw)
    title = title_m.group(1).strip().rstrip(",.") if title_m else None
    year_m = re.search(r"\b(19|20)\d{2}\b", raw)
    year = int(year_m.group(0)) if year_m else None
    author_segment = raw[: title_m.start()] if title_m else raw[:80]
    authors = []
    for a in _AUTHOR_TOKEN_RE.findall(author_segment):
        if a not in authors:
            authors.append(a)
    return ReferenceEntry(
        number=number,
        raw=raw[:400],
        doi=dois[0] if dois else None,
        arxiv_id=arxiv_id,
        title=title,
        authors=authors[:6],
        year=year,
    )


def parse_reference_list(text: str) -> Dict[int, ReferenceEntry]:
    """Parse the reference list into {number → ReferenceEntry}. Empty if none."""
    text = repair_wrapped_urls(text)
    # Robust references-section detection (header OR trailing numbered-entry run),
    # which catches Nature/IEEE PDFs where taxonomy._split_body_and_bib misses.
    bib = segment_zones(text).references_block
    if not bib.strip():
        _body, bib = _split_body_and_bib(text)  # legacy fallback (inline header)
    if not bib.strip():
        return {}
    entries: Dict[int, ReferenceEntry] = {}
    matches = list(_ENTRY_BRACKET_RE.finditer(bib))
    if not matches:
        matches = list(_ENTRY_DOT_RE.finditer(bib))
    for m in matches:
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        # Keep the first occurrence of a given number (handles stray digits).
        if n not in entries:
            entries[n] = _parse_entry(n, m.group(2))
    return entries


def _enclosing_sentence(text: str, idx: int) -> str:
    """Return the sentence containing position `idx`."""
    left = 0
    for m in _SENT_END_RE.finditer(text, 0, idx):
        left = m.end()
    rm = _SENT_END_RE.search(text, idx)
    right = rm.end() if rm else len(text)
    return text[left:right].strip()


def _expand_marker(spec: str) -> List[int]:
    """'2-5' → [2,3,4,5]; '1, 3, 7' → [1,3,7]; '14' → [14]."""
    out: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        rng = re.split(r"\s*[-–—]\s*", part)
        if len(rng) == 2 and rng[0].isdigit() and rng[1].isdigit():
            a, b = int(rng[0]), int(rng[1])
            if a <= b and b - a <= 60:
                out.extend(range(a, b + 1))
            else:
                out.append(a)
        elif part.isdigit():
            out.append(int(part))
    return out


def extract_marker_citations(
    body: str, valid_numbers: Optional[Set[int]] = None, enable_superscript: bool = True
) -> List[MarkerMention]:
    """
    Find numbered in-text markers in the body and the sentence each sits in.

    Bracketed markers ([14], [2]-[5], [1,3]) are always detected. Superscript
    markers (Nature/Science: "models1,2", "datasets9–11") are detected only when
    `valid_numbers` (the parsed reference numbers) is supplied AND the paper is
    not bracket-style — and only when every number in the run is a real reference
    number and the glued word is not denylisted. These guards keep "GPT4",
    "CO2", "ResNet50", "Table3" etc. from being read as citations.
    """
    # Normalise the cross-bracket range form "[2]–[5]" → "[2-5]" first.
    body = _CROSS_RANGE_RE.sub(lambda m: f"[{m.group(1)}-{m.group(2)}]", body)
    mentions: List[MarkerMention] = []
    for m in _MARKER_RE.finditer(body):
        numbers = _expand_marker(m.group(1))
        if not numbers:
            continue
        sentence = _enclosing_sentence(body, m.start())
        if sentence:
            mentions.append(MarkerMention(numbers=numbers, sentence=sentence))

    # Superscript pass — only for superscript-style papers (few/no brackets) and
    # only with a reference list to validate against. `enable_superscript` lets a
    # per-sentence caller carry the document-level bracket-style decision so the
    # "<2 markers" guard isn't defeated by single-sentence calls.
    if valid_numbers and enable_superscript and len(mentions) < 2:
        for m in _SUPERSCRIPT_RE.finditer(body):
            prefix_word = re.search(r"[A-Za-z]+$", body[: m.start()])
            if prefix_word and _SUPERSCRIPT_DENY_RE.search(prefix_word.group(0)):
                continue
            numbers = _expand_marker(m.group(1))
            if not numbers or not all(n in valid_numbers for n in numbers):
                continue
            sentence = _enclosing_sentence(body, m.start())
            if sentence:
                mentions.append(MarkerMention(numbers=numbers, sentence=sentence))
    return mentions


# ────────────────────────────────────────────────────────────────────────────
# Resolution + alignment
# ────────────────────────────────────────────────────────────────────────────
async def _resolve_entry(entry: ReferenceEntry) -> SourceRecord:
    if entry.doi:
        return await fetch_source(doi=entry.doi)
    if entry.arxiv_id:
        rec = await fetch_source(arxiv_id=entry.arxiv_id)
        if rec and rec.sources_consulted:
            return rec
        # OpenAlex's arxiv.org lookup is flaky and S2 is often rate-limited;
        # arXiv papers also carry a DataCite/Crossref DOI (10.48550/arXiv.*),
        # which resolves reliably with an abstract.
        return await fetch_source(doi=_arxiv_to_synthetic_doi(entry.arxiv_id))
    # No DOI/arXiv: resolve the raw reference string via Crossref bibliographic
    # (style-agnostic — handles Vancouver/APA/MLA/IEEE/Chicago/etc. whose titles
    # the per-style parser can't extract). Fall back to OpenAlex title search.
    rec = await fetch_by_reference(entry.raw)
    if rec and rec.sources_consulted:
        return rec
    if entry.title:
        rec2 = await fetch_by_title(entry.title)
        if rec2:
            return rec2
    return rec or SourceRecord()


async def _align_pair(entry: ReferenceEntry, sentence: str, rec: SourceRecord) -> CitationAlignment:
    n = entry.number
    canonical = (
        (rec.doi if rec and rec.doi else None)
        or entry.doi
        or (_arxiv_to_synthetic_doi(entry.arxiv_id) if entry.arxiv_id else None)
        or f"ref-{n}"
    )
    a = CitationAlignment(
        doi=canonical,
        claim_context=sentence,
        marker=f"[{n}]",
        cited_number=n,
        source_title=(rec.title if rec else None) or entry.title,
        source_year=(rec.year if rec else None) or entry.year,
        source_authors=[au.name for au in rec.authors[:10]] if rec and rec.authors else entry.authors,
        source_venue=rec.venue if rec else None,
        is_retracted=rec.is_retracted if rec else False,
        retraction_note=rec.retraction_note if rec else None,
        sources_consulted=rec.sources_consulted if rec else [],
    )
    if not rec or not rec.sources_consulted:
        a.support = "unknown"
        a.notes = f"Reference [{n}] could not be resolved to a source in any registry."
        return a
    if rec.is_retracted:
        a.notes = f"Cited reference [{n}] is retracted ({rec.retraction_note or 'see registry'})."
    blob = rec.best_text()
    if not blob:
        a.support = "unknown"
        a.notes = " ".join(p for p in [a.notes, "Source registry returned no abstract."] if p)
        return a
    scored = await score_support(sentence, blob, source_label=f"[{n}] {canonical}")
    a.support = scored["support"]
    a.supporting_span = scored["supporting_span"]
    a.missing_aspects = scored["missing_aspects"]
    a.confidence = scored["confidence"]
    a.notes = " ".join(p for p in [a.notes, scored.get("notes")] if p) or None
    return a


async def align_numbered_citations(
    text: str, max_alignments: Optional[int] = None
) -> List[CitationAlignment]:
    """
    Align every (numbered in-text marker, reference entry) pair in `text`.
    Sources are resolved once per reference number (and cached by source_fetcher);
    each distinct citing sentence is aligned separately. Bounded concurrency.
    """
    text = repair_wrapped_urls(text)
    refs = parse_reference_list(text)
    if not refs:
        return []
    # Extract markers from the BODY only (segment_zones drops the references
    # section) so a reference entry "[1] Author…" is not read as an in-text
    # citation of reference 1.
    body = segment_zones(text).body_text
    mentions = extract_marker_citations(body, valid_numbers=set(refs.keys()))
    if not mentions:
        return []

    # Build unique (number, sentence) work items for references we actually have.
    pairs: List[tuple[int, str]] = []
    seen: Set[tuple[int, str]] = set()
    for mention in mentions:
        for n in mention.numbers:
            if n not in refs:
                continue
            key = (n, mention.sentence)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(key)

    if max_alignments is not None:
        pairs = pairs[:max_alignments]
    if not pairs:
        return []

    sem = asyncio.Semaphore(5)

    # Resolve each distinct reference number once.
    numbers = sorted({n for n, _ in pairs})

    async def _resolve(n: int):
        async with sem:
            try:
                return n, await _resolve_entry(refs[n])
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Reference [{n}] resolution failed: {e}")
                return n, SourceRecord()

    recs = dict(await asyncio.gather(*[_resolve(n) for n in numbers]))

    async def _do(n: int, sentence: str):
        async with sem:
            try:
                return await _align_pair(refs[n], sentence, recs.get(n))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Numbered alignment failed for [{n}]: {e}")
                return None

    results = await asyncio.gather(*[_do(n, s) for n, s in pairs])
    return [r for r in results if r is not None]


# ────────────────────────────────────────────────────────────────────────────
# Citation Support Matrix
# ────────────────────────────────────────────────────────────────────────────
def _worst_support(supports: List[str]) -> Optional[str]:
    real = [s for s in supports if s]
    if not real:
        return None
    return max(real, key=lambda s: _SUPPORT_SEVERITY.get(s, 0))


def _rollup_verdict(support: Optional[str], doi_status: str, metadata_match: Optional[bool]) -> str:
    if support == "contradicted":
        return "contradicted"
    if support == "overstated":
        return "overstated"
    if doi_status in ("not_found", "invalid"):
        return "not_found"
    if doi_status == "mismatch" or metadata_match is False:
        return "mismatch"
    if support in ("unrelated", "partial"):
        return "needs_review"
    if support == "supported":
        return "supported"
    if doi_status == "valid":
        return "needs_review"
    return "unknown"


def build_citation_matrix(
    refs: Dict[int, ReferenceEntry],
    alignments: List[Dict[str, Any]],
    doi_status: Dict[str, Dict[str, Any]],
    cited_numbers: Set[int],
) -> List[Dict[str, Any]]:
    """
    Roll numbered alignments + DOI validity into the Citation Support Matrix.
    One row per reference that is either cited in-text or carries a DOI we
    checked. `doi_status` maps normalised DOI → {status, title, year}.
    """
    from .arxiv_verify import _title_similarity

    rows: List[Dict[str, Any]] = []
    by_number: Dict[int, List[Dict[str, Any]]] = {}
    for a in alignments:
        n = a.get("cited_number")
        if n is not None:
            by_number.setdefault(n, []).append(a)

    for n in sorted(refs):
        entry = refs[n]
        aligns_n = by_number.get(n, [])
        if n not in cited_numbers and not entry.doi:
            continue  # uncited and unverifiable — skip to keep the matrix signal-dense

        support = _worst_support([a.get("support") for a in aligns_n])
        confidence = max([int(a.get("confidence") or 0) for a in aligns_n], default=0)

        dstat = doi_status.get(normalize_doi(entry.doi)) if entry.doi else None
        doi_status_str = (dstat or {}).get("status") if dstat else ("no_doi" if not entry.doi else "unknown")

        # metadata_match: does the title parsed from the reference string match
        # the registry's title for that DOI?
        registry_title = (dstat or {}).get("title") or (aligns_n[0].get("source_title") if aligns_n else None)
        metadata_match: Optional[bool] = None
        if entry.title and registry_title:
            metadata_match = _title_similarity(entry.title, registry_title) >= 0.5

        used_correctly: Optional[bool] = None
        if support:
            used_correctly = support not in ("unrelated", "contradicted")

        note = next((a.get("notes") for a in aligns_n if a.get("notes")), None)
        retracted = any(a.get("is_retracted") for a in aligns_n)

        rows.append({
            "citation": f"[{n}]",
            "number": n,
            "reference": entry.title or entry.raw[:90],
            "doi": entry.doi,
            "doi_status": doi_status_str,
            "metadata_match": metadata_match,
            "used_correctly": used_correctly,
            "supports_claim": support,
            "is_retracted": retracted,
            "verdict": _rollup_verdict(support, doi_status_str or "unknown", metadata_match),
            "confidence": confidence,
            "note": note,
        })
    return rows
