"""
Document-structure parsing for Published Paper Audit.

PDF-extracted journal/IEEE papers are messy: reference lists leak into body
prose, table/figure example text reads like author claims, and URLs wrap across
line breaks. This module adds a zone layer used by api.verify so that in
published_paper mode only genuine body prose reaches claim verification.

IMPORTANT: the shared claim extractor (preprocessor.py) is NOT touched — these
helpers are applied in api.verify and gated on mode, so student/essay mode is
unaffected. `repair_wrapped_urls` is the one always-on helper, and it only ever
rejoins truncated URLs.

  - repair_wrapped_urls : re-join a URL split across a newline
                          (https://arxiv.org/abs/\n2302.09664 -> …/abs/2302.09664)
  - segment_zones       : split into verifiable body_text vs excluded zones
                          (references section, figure/table caption+example blocks)
  - verifiable_body     : repair_wrapped_urls -> segment_zones -> body_text
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ── URL repair ────────────────────────────────────────────────────────────────
# Join a URL fragment that looks INCOMPLETE at a line end (ends with a path
# separator / query sign / hyphen — chars that cannot legitimately end a
# sentence-final URL) with the next line's leading token, but ONLY when that
# token starts lowercase or with a digit. Path/ID continuations
# ("abs/2303.08774", "2302.09664") match; a prose word like "The" (capital T)
# does not, so a complete URL followed by prose is never merged.
_WRAPPED_URL_RE = re.compile(
    r'(https?://[^\s)>\]]*?[/=&\-])\n[ \t]*([a-z0-9][^\s)>\]]*)'
)


def repair_wrapped_urls(text: str) -> str:
    """Rejoin URLs split across line breaks. Idempotent; safe for all modes."""
    if not text:
        return text
    prev = None
    out = text
    # Iterate so a URL wrapped more than once (rare) is fully rejoined.
    for _ in range(3):
        out = _WRAPPED_URL_RE.sub(r'\1\2', out)
        if out == prev:
            break
        prev = out
    return out


# ── Zone segmentation ──────────────────────────────────────────────────────────
_REF_HEADER_RE = re.compile(
    r'^\s*(?:references|bibliography|works cited|literature cited)\s*:?\s*$',
    re.IGNORECASE,
)
# A numbered/bracketed reference entry: "[12] ..." or "12. ..." with a leading token.
_REF_ENTRY_RE = re.compile(r'^\s*(?:\[\d{1,3}\]|\d{1,3}\.)\s+\S')
# Stricter (for the header-less fallback): also requires a 4-digit year, so a
# numbered list in Methods ("1. Do X") doesn't get mistaken for references.
_REF_ENTRY_YEAR_RE = re.compile(r'^\s*(?:\[\d{1,3}\]|\d{1,3}\.)\s+.*\b(?:19|20)\d{2}\b')
# Figure/table caption (start of an excluded block).
_CAPTION_RE = re.compile(
    r'^\s*(?:fig(?:ure)?\.?|table|tab\.|extended\s+data\s+(?:fig(?:ure)?|table)|'
    r'supplementary\s+(?:fig(?:ure)?|table))\s*\.?\s*\d',
    re.IGNORECASE,
)
_MAX_CAPTION_BLOCK_LINES = 8  # bound over-exclusion if no blank line follows

# Math/operator characters used to spot display-equation lines.
_MATH_CHARS = set("=+−*/^_<>≤≥≈≠±∑∏∫∂∇√∞·×÷⟨⟩∈∉⊂⊆∩∪θλμσαβγδεζηπρτφχψω")
# ASCII math signals PDF extraction often leaves: inequalities, a function-style
# definition "s(i) =", or a "1/N"-type fraction.
_ASCII_MATH_RE = re.compile(
    r"<=|>=|:=|/=|[a-zA-Z]\([a-z0-9, ]+\)\s*=|\b\d+\s*/\s*[A-Za-z]\b"
    r"|\b[a-z]_[a-z0-9]\b|\b(?:sum|prod|exp|log|argmax|argmin)_"
)


def is_equation_block(line: str) -> bool:
    """True for a display-equation line (symbol-dense or a bare equation number).
    Conservative: prose with one stray symbol ("we set α = 0.05") stays prose."""
    s = line.strip()
    if not s or len(s) > 200:
        return False
    if re.match(r"^\(?\d{1,3}\)?$", s):          # bare equation number "(3)" / "3"
        return True
    letters = sum(1 for c in s if c.isascii() and c.isalpha())
    math = sum(1 for c in s if c in _MATH_CHARS)
    digits = sum(1 for c in s if c.isdigit())
    if math >= 2 and (math + digits) >= letters:
        return True
    # ASCII math: short, symbol-bearing, low letter density (so prose like
    # "The function f(x) = x squared is shown." — 75% letters — stays prose).
    if len(s) <= 120 and _ASCII_MATH_RE.search(s) and letters / max(len(s), 1) < 0.7:
        return True
    return False


# ── Claim zone classifier (published-paper audit) ──────────────────────────────
_METHOD_RE = re.compile(
    r"\b(?:we|our|this (?:paper|work|study|article|method|approach))\b[^.]{0,70}?"
    r"\b(propos|present|introduc|develop|design|describ|defin|use|train|appl|adopt|"
    r"build|implement|extend|formulat)",
    re.IGNORECASE,
)
_RESULT_VERB_RE = re.compile(
    r"\b(?:we|our|this (?:method|approach|model|system))\b[^.]{0,50}?"
    r"\b(achiev|obtain|report|find|observ|show|demonstrat|improv|outperform|reach|yield|score)",
    re.IGNORECASE,
)
_RESULT_SIGNAL_RE = re.compile(
    r"%|\bF1\b|\bAUC(?:-?PR)?\b|\bBLEU\b|\bROUGE\b|\baccuracy\b|\bprecision\b|\brecall\b|"
    r"outperform|state[- ]of[- ]the[- ]art|\bTable\s*\d|\bFigure\s*\d",
    re.IGNORECASE,
)


def classify_zone(sentence: str, has_citation: bool, in_related_work: bool = False) -> str:
    """One of RELATED_WORK_CLAIM | RESULT_CLAIM | METHOD_CLAIM | AUTHOR_CLAIM."""
    if has_citation or in_related_work:
        return "RELATED_WORK_CLAIM"
    if _RESULT_VERB_RE.search(sentence) or _RESULT_SIGNAL_RE.search(sentence):
        return "RESULT_CLAIM"
    if _METHOD_RE.search(sentence):
        return "METHOD_CLAIM"
    return "AUTHOR_CLAIM"


# ── Header / footer / front-matter / model-output exclusion ────────────────────
# Whole-line banners (PDF front matter / running headers). Matched against a
# stripped line with a length cap so a banner string occurring mid-prose is
# never affected.
# Anchored at line start (a body sentence never starts "arXiv:NNNN.NNNNN"); the
# trailing primary-class + date ("[cs.CL] 11 Oct 2023") is allowed to follow.
_ARXIV_BANNER_RE = re.compile(r"^arxiv:\s*\d{4}\.\d{4,5}(?:v\d+)?\b", re.IGNORECASE)
_VENUE_BANNER_RE = re.compile(r"^(?:in\s+)?proceedings of\b|^to appear in\b|^under review\b|^preprint\.?$", re.IGNORECASE)
_COPYRIGHT_RE = re.compile(r"^(?:©|\(c\)|copyright)\b.*(?:19|20)\d{2}|all rights reserved\.?$", re.IGNORECASE)
_EMAIL_LINE_RE = re.compile(r"^[\w.+\-]+@[\w.\-]+\.\w+(?:\s*[,;]\s*[\w.+\-]+@[\w.\-]+\.\w+)*$")
_AFFIL_RE = re.compile(r"^\d*\s*(?:department|dept\.?|school|faculty|institute|laboratory|lab|centre|center|college|university|division)\b", re.IGNORECASE)
_AFFIL_ORG_RE = re.compile(r"\b(?:university|institute|laborator|college|inc\.?|corp\.?|gmbh|ltd|llc)\b", re.IGNORECASE)
# Running header/footer: starts with a page number, capitalised title, ends in a
# bare page number, no terminal sentence punctuation.
_PAGE_HF_RE = re.compile(r"^\d{1,4}\s+[A-Z][^.!?]{0,60}\s+\d{1,4}$")
# Author line (a comma-separated list of >=2 capitalised names, optional
# superscript affiliation markers) — only consulted in the pre-abstract window.
_AUTHORLINE_RE = re.compile(
    r"^[A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+){0,3}[*\d†‡§¶]*"
    r"(?:\s*,\s*[A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+){0,3}[*\d†‡§¶]*)+$"
)
_ABSTRACT_RE = re.compile(r"^\s*abstract\b", re.IGNORECASE)
# Model-output / transcript example block header.
_MODEL_OUTPUT_HDR_RE = re.compile(
    r"^\s*(?:prompt|response|output|input|completion|generated(?:\s+(?:text|output|response))?|"
    r"model output|system|user|assistant|example\s*\d*)\s*[:\-–—]",
    re.IGNORECASE,
)
_MAX_MODEL_BLOCK_LINES = 12


def _is_banner_anywhere(line: str) -> bool:
    """Banners safe to drop ANYWHERE — these (almost) never collide with prose:
    arXiv id banners, pure email lines, running page headers."""
    s = line.strip()
    if not s or len(s) > 160:
        return False
    return bool(_ARXIV_BANNER_RE.match(s) or _EMAIL_LINE_RE.match(s) or _PAGE_HF_RE.match(s))


def _is_front_matter_line(line: str) -> bool:
    """Venue / copyright / affiliation lines — excluded ONLY in the front-matter
    window, since these phrasings can legitimately begin a body sentence
    ("Proceedings of the 2017 workshop showed that …")."""
    s = line.strip()
    if not s or len(s) > 160:
        return False
    if _VENUE_BANNER_RE.match(s) or _COPYRIGHT_RE.search(s):
        return True
    if _AFFIL_RE.match(s) and ("," in s or _AFFIL_ORG_RE.search(s)):
        return True
    return False


def _find_front_matter_end(lines: list[str]) -> int:
    """Index of the Abstract header (author/affiliation block lives before it),
    or a hard 12-line cap so the window can never reach into the body."""
    for i, ln in enumerate(lines):
        if _ABSTRACT_RE.match(ln):
            return i
    return min(12, len(lines))


_TABLE_FUNCTION_WORDS = {
    "the", "of", "and", "in", "is", "are", "to", "a", "an", "that", "this", "we",
    "our", "for", "on", "with", "as", "by", "from", "it", "its", "which", "was",
    "were", "be", "can", "has", "have", "their", "these", "such", "than", "but",
}


def is_table_row(s: str) -> bool:
    """A survey/comparison table row or column-header line (e.g. 'Survey Date
    Pages Eval Improve Multimodal Contributions') — Title-Case tokens / numeric
    columns, almost no function words, no sentence structure. Excluded from
    claim verification in published-paper mode."""
    s = s.strip()
    # Comparison-table check/cross glyphs anywhere -> table noise, even merged
    # with prose ("However, … 03-Sept-2023 32✓ ✓ ✗"). No real prose has ≥2.
    if len(re.findall(r"[✓✗✔✘☑☒]", s)) >= 2:
        return True
    toks = s.split()
    if len(toks) < 4 or len(s) > 200:
        return False
    func = sum(1 for t in toks if t.lower() in _TABLE_FUNCTION_WORDS)
    if func > 1:
        return False  # real connective structure -> prose, not a table row
    ends_sentence = s.rstrip().endswith((".", "!", "?"))
    cap = sum(1 for t in toks if t[:1].isupper())
    if cap / len(toks) >= 0.6 and not ends_sentence:
        return True  # mostly Title-Case header/comparison row
    nums = sum(1 for t in toks if re.fullmatch(r"[\d.,%/x±+\-]+", t))
    if nums >= 3:
        return True  # numeric column row
    return False


def is_pdf_fragment(s: str) -> bool:
    """Conservative published-paper sentence filter for broken PDF fragments.
    Requires >=2 weak signals (or decisive mostly-non-alphabetic) so a real
    sentence survives a single borderline signal."""
    s = s.strip()
    if len(s) < 25:
        return False  # already vetted by _is_valid_claim; stay conservative
    alpha = sum(1 for c in s if c.isalpha())
    mostly_nonalpha = (1 - alpha / len(s)) > 0.5
    truncated = bool(re.search(r"\w-\s\w", s)) or re.sub(r"[.!?]+$", "", s).endswith("-")
    no_lower = not any(c.islower() for c in s)
    tokens = s.split()
    dangling = s[:1].islower() and len(tokens) < 8
    ends_sentence = s.rstrip().endswith((".", "!", "?"))
    # mostly-non-alphabetic is decisive only for non-sentence lines (symbol soup);
    # a stat-dense but properly-terminated sentence ("GDP grew by 3.2% in 2020.")
    # needs a second signal before being dropped.
    if mostly_nonalpha and not ends_sentence:
        return True
    return (truncated + no_lower + dangling + mostly_nonalpha) >= 2


@dataclass
class DocStructure:
    body_text: str          # verifiable prose only
    references_block: str    # the references section (for the Citation Matrix)
    reference_entry_count: int = 0
    excluded_block_count: int = 0     # figure/table caption blocks removed
    header_footer_count: int = 0      # banners / author / affiliation / page headers
    model_output_count: int = 0       # prompt/response transcript blocks


def _find_references_start(lines: list[str]) -> int | None:
    """Index of the first references-section line, or None."""
    # 1) Last explicit "References"/"Bibliography" header wins.
    header_idx = None
    for i, ln in enumerate(lines):
        if _REF_HEADER_RE.match(ln):
            header_idx = i
    if header_idx is not None:
        return header_idx + 1  # references start AFTER the header line

    # 2) Header-less fallback: a trailing cluster of >=5 year-bearing numbered
    #    entries in the LAST half of the document, excluding first-person lines
    #    (a numbered "1. We improved … 2020" contributions list is NOT references).
    entry_idxs = [
        i for i, ln in enumerate(lines)
        if _REF_ENTRY_YEAR_RE.match(ln) and not re.search(r"\b(?:we|our|us)\b", ln, re.IGNORECASE)
    ]
    if len(entry_idxs) >= 5 and entry_idxs[0] >= len(lines) * 0.5:
        return entry_idxs[0]
    return None


def segment_zones(text: str) -> DocStructure:
    """Split text into verifiable body vs excluded zones (references, captions)."""
    lines = text.split('\n')
    n = len(lines)
    ref_start = _find_references_start(lines)
    fm_end = _find_front_matter_end(lines)
    has_abstract = any(_ABSTRACT_RE.match(ln) for ln in lines)

    body_lines: list[str] = []
    ref_lines: list[str] = []
    excluded_blocks = 0
    header_footer = 0
    model_output = 0
    i = 0
    while i < n:
        if ref_start is not None and i >= ref_start:
            ref_lines.append(lines[i])
            i += 1
            continue
        # Banners anywhere (arXiv/email/page header); venue/copyright/affiliation
        # and author lines ONLY in the bounded front-matter window, so a body
        # sentence ("Proceedings of the workshop showed …" / starting with
        # surnames) is never dropped. Author lines additionally require a real
        # Abstract header to have been found (avoids the 12-line-fallback FP).
        in_fm = i < fm_end
        if (_is_banner_anywhere(lines[i])
                or (in_fm and _is_front_matter_line(lines[i]))
                or (in_fm and has_abstract and _AUTHORLINE_RE.match(lines[i].strip()))):
            header_footer += 1
            i += 1
            continue
        # Model-output / transcript example block (mirror the caption block).
        if _MODEL_OUTPUT_HDR_RE.match(lines[i]):
            model_output += 1
            i += 1
            taken = 1
            while (
                i < n
                and taken < _MAX_MODEL_BLOCK_LINES
                and lines[i].strip() != ''
                and not _CAPTION_RE.match(lines[i])
                and not _MODEL_OUTPUT_HDR_RE.match(lines[i])
                and not (ref_start is not None and i >= ref_start)
            ):
                i += 1
                taken += 1
            continue
        if _CAPTION_RE.match(lines[i]):
            # Exclude the caption line + tightly-coupled following lines (the
            # table/figure example) until a blank line, a new caption, the
            # references section, or the line cap.
            excluded_blocks += 1
            i += 1
            taken = 1
            while (
                i < n
                and taken < _MAX_CAPTION_BLOCK_LINES
                and lines[i].strip() != ''
                and not _CAPTION_RE.match(lines[i])
                and not (ref_start is not None and i >= ref_start)
            ):
                i += 1
                taken += 1
            continue
        # Drop standalone display-equation lines from the verifiable body.
        if is_equation_block(lines[i]):
            i += 1
            continue
        # Drop survey/comparison table rows & column headers at the LINE level,
        # before lines are joined into sentences (else a table row merges into a
        # prose sentence and slips through the sentence-level filter).
        if is_table_row(lines[i]):
            excluded_blocks += 1
            i += 1
            continue
        body_lines.append(lines[i])
        i += 1

    ref_entry_count = sum(1 for ln in ref_lines if _REF_ENTRY_RE.match(ln))
    return DocStructure(
        body_text='\n'.join(body_lines),
        references_block='\n'.join(ref_lines),
        reference_entry_count=ref_entry_count,
        excluded_block_count=excluded_blocks,
        header_footer_count=header_footer,
        model_output_count=model_output,
    )


def verifiable_body(text: str) -> str:
    """Repaired body prose only — the text that should reach claim verification."""
    return segment_zones(repair_wrapped_urls(text)).body_text
