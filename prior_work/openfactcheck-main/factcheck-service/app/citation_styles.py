"""
Author-year (ACL / APA) citation support for Published Paper Audit.

M1/M2 handle numeric citations (IEEE [n], Nature superscript). ACL/EMNLP papers
cite by author-year — "(Yuan et al., 2021; Fu et al., 2023)", "Brown et al.
(2020)" — and list references without numbers ("Tom B. Brown … 2020. Title. In
NeurIPS."). This module detects citation style, extracts author-year citations,
parses author-year reference entries, and maps citations to entries by
(surname, year).

All consumed only in published_paper mode (see api.verify); the shared
preprocessor and general mode are unaffected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ref_integrity import extract_dois, extract_urls
from .citation_alignment import extract_arxiv_ids

# arXiv id embedded in an arxiv.org URL (refs cite the URL, not "arXiv:").
_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.IGNORECASE)

_BRACKET_NUM_RE = re.compile(r"\[\d{1,3}(?:[–—,\-]\d{1,3})*\]")
# A single author-year token: "Brown et al., 2020", "Yuan and Liu, 2021",
# "Devlin et al. 2019", "Smith, 2020".
_AY_TOKEN_RE = re.compile(
    r"([A-Z][a-zA-Z'’\-]+)"                                  # first-author surname
    r"(?:\s+et al\.?|\s+and\s+[A-Z][a-zA-Z'’\-]+|\s*&\s*[A-Z][a-zA-Z'’\-]+)?"
    r",?\s+\(?((?:19|20)\d{2}[a-z]?)\)?"                     # year (+ optional suffix 2023a)
)
# Narrative form: "Brown et al. (2020)".
_AY_NARRATIVE_RE = re.compile(
    r"([A-Z][a-zA-Z'’\-]+)"
    r"(?:\s+et al\.?|\s+and\s+[A-Z][a-zA-Z'’\-]+|\s*&\s*[A-Z][a-zA-Z'’\-]+)?"
    r"\s*\(((?:19|20)\d{2}[a-z]?)\)"
)
# Parenthetical citation group that contains at least one year.
_PAREN_GROUP_RE = re.compile(r"\(([^()]*\b(?:19|20)\d{2}[a-z]?\b[^()]*)\)")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})[a-z]?\b")
_SENT_END_RE = re.compile(r"[.!?]\s")


@dataclass
class AYCite:
    surname: str
    year: str
    raw: str
    sentence: str = ""

    @property
    def key(self) -> str:
        return ay_key(self.surname, self.year)

    @property
    def display(self) -> str:
        return f"({self.surname} et al., {self.year})"


@dataclass
class AYRef:
    key: str
    surname: str
    year: str
    raw: str
    title: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    authors: List[str] = field(default_factory=list)


def ay_key(surname: str, year: str) -> str:
    """Key by surname:year, KEEPING a disambiguating suffix (2023a/b) when
    present (distinct papers); lookups fall back to the suffix-less prefix."""
    m = re.match(r"((?:19|20)\d{2}[a-z]?)", str(year).strip())
    y = m.group(1) if m else str(year)[:4]
    return f"{surname.strip().lower()}:{y}"


def lookup_ref(refs: Dict[str, "AYRef"], cite_key: str) -> Optional["AYRef"]:
    """Map a citation key to a reference: exact (with suffix) first, then the
    suffix-less prefix (handles a body '2023a' vs a ref parsed as '2023')."""
    if cite_key in refs:
        return refs[cite_key]
    base = re.sub(r"[a-z]$", "", cite_key)  # drop trailing suffix letter
    if base != cite_key and base in refs:
        return refs[base]
    # body has no suffix but the ref does (unique same-surname-year) -> match
    cands = [r for k, r in refs.items() if k == base or k.startswith(base) or re.sub(r"[a-z]$", "", k) == base]
    return cands[0] if len(cands) == 1 else None


def _enclosing_sentence(text: str, idx: int) -> str:
    left = 0
    for m in _SENT_END_RE.finditer(text, 0, idx):
        left = m.end()
    rm = _SENT_END_RE.search(text, idx)
    right = rm.end() if rm else len(text)
    return text[left:right].strip()


# ── Style detection ────────────────────────────────────────────────────────────
def detect_style(text: str) -> str:
    """Return 'numeric' | 'author_year' | 'mixed' | 'none'."""
    numeric = len(_BRACKET_NUM_RE.findall(text)) + len(re.findall(r"\brefs?\.\s*\d", text, re.I))
    ay = len(extract_author_year_citations(text))
    if numeric >= 3 and ay >= 3:
        return "mixed"
    if numeric >= 3 and numeric >= ay:
        return "numeric"
    if ay >= 3:
        return "author_year"
    return "none"


# ── In-text author-year citations ───────────────────────────────────────────────
def extract_author_year_citations(text: str) -> List[AYCite]:
    """All author-year citations in `text` (parenthetical groups + narrative)."""
    cites: List[AYCite] = []
    seen: set = set()

    def _add(surname: str, year: str, raw: str, pos: int):
        c = AYCite(surname=surname, year=year, raw=raw, sentence=_enclosing_sentence(text, pos))
        k = (c.key, c.sentence)
        if k not in seen:
            seen.add(k)
            cites.append(c)

    # Parenthetical groups, possibly multi-cite separated by ';'
    for g in _PAREN_GROUP_RE.finditer(text):
        inner = g.group(1)
        for part in inner.split(";"):
            m = _AY_TOKEN_RE.search(part)
            if m:
                _add(m.group(1), m.group(2), part.strip(), g.start())
    # Narrative "Author et al. (2020)"
    for m in _AY_NARRATIVE_RE.finditer(text):
        _add(m.group(1), m.group(2), m.group(0), m.start())
    return cites


# ── Author-year reference list ───────────────────────────────────────────────────
# Boundary that ends the FIRST author within a reference's author list.
_FIRST_AUTHOR_BOUNDARY_RE = re.compile(r",| and | & |;|\bet al\.?", re.IGNORECASE)


def _entry_surname(entry: str) -> Optional[str]:
    """FIRST-author surname (must match the in-text key). Handles natural order
    "Jacob Devlin and Ming-Wei Chang" -> Devlin, "Tom B. Brown, ..." -> Brown,
    APA "Brown, T. B., ..." -> Brown, and "Devlin et al. 2019" -> Devlin."""
    year_m = _YEAR_RE.search(entry)
    head = entry[: year_m.start()] if year_m else entry[:120]
    first_author = _FIRST_AUTHOR_BOUNDARY_RE.split(head, maxsplit=1)[0].strip()
    tokens = re.findall(r"[A-Za-zÀ-ÿ'’\-]{2,}", first_author)
    return tokens[-1] if tokens else None


def _entry_authors(entry: str) -> List[str]:
    """Author strings before the year (split on comma / 'and' / '&' / ';')."""
    year_m = _YEAR_RE.search(entry)
    head = entry[: year_m.start()] if year_m else entry[:200]
    parts = re.split(r",| and | & |;", head)
    return [p.strip() for p in parts if p.strip() and re.search(r"[A-Za-z]", p)][:12]


# A line that plausibly STARTS a new reference entry: APA "Surname, F." or a
# natural-order name run, and (for the natural case) a year somewhere up front.
_ENTRY_APA_RE = re.compile(r"^[A-Z][a-zA-Z'’\-]+,\s+[A-Z]\.")
_ENTRY_NATURAL_RE = re.compile(r"^[A-Z][a-zA-Z'’\-]+\s+(?:[A-Z]\.?\s+)*[A-Z][a-zA-Z'’\-]+")


def _looks_like_entry_start(line: str) -> bool:
    if _ENTRY_APA_RE.match(line):
        return True
    has_year_upfront = bool(_YEAR_RE.search(line[:100]))
    return has_year_upfront and (bool(_ENTRY_NATURAL_RE.match(line)) or bool(re.match(r"^[A-Z][a-zA-Z'’\-]+,", line)))


def _split_entries(refs_block: str) -> List[str]:
    """Split an unnumbered (ACL/APA) reference block into entries. A new entry
    starts only on a line that LOOKS like an author-list start once the buffer
    already contains a year — so a wrapped venue/title continuation line
    ("Processing Systems, volume 33.") is not mistaken for a new entry."""
    entries: List[str] = []
    buf: List[str] = []
    for raw_line in refs_block.split("\n"):
        line = raw_line.strip()
        if not line:
            if buf:
                entries.append(" ".join(buf))
                buf = []
            continue
        starts_entry = _looks_like_entry_start(line) and any(_YEAR_RE.search(b) for b in buf)
        if starts_entry and buf:
            entries.append(" ".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        entries.append(" ".join(buf))
    # Keep only entries that actually look like references (contain a year).
    return [e for e in entries if _YEAR_RE.search(e)]


def parse_author_year_references(refs_block: str) -> Dict[str, AYRef]:
    """Parse an author-year reference block into {surname:year -> AYRef}."""
    refs: Dict[str, AYRef] = {}
    if not refs_block or not refs_block.strip():
        return refs
    for entry in _split_entries(refs_block):
        surname = _entry_surname(entry)
        year_m = _YEAR_RE.search(entry)
        if not surname or not year_m:
            continue
        year = year_m.group(1)
        # Title: text between "year." and the next sentence period; venue: the
        # clause after the title (often "In <venue>").
        title = None
        venue = None
        after = entry[year_m.end():].lstrip(" .)")
        tm = re.match(r"(.+?)\.\s", after)
        if tm and len(tm.group(1).split()) >= 2:
            title = tm.group(1).strip()
            rest = after[tm.end():].strip()
            vm = re.match(r"(?:In\s+)?(.+?)[.,]", rest)
            if vm and len(vm.group(1)) >= 4:
                venue = vm.group(1).strip()[:120]
        dois = extract_dois(entry)
        arxiv = extract_arxiv_ids(entry)
        arxiv_id = arxiv[0] if arxiv else None
        if not arxiv_id:
            um = _ARXIV_URL_RE.search(entry)
            if um:
                arxiv_id = um.group(1)
        key = ay_key(surname, year)
        if key not in refs:
            refs[key] = AYRef(
                key=key, surname=surname, year=year, raw=entry[:400],
                title=title, venue=venue, doi=dois[0] if dois else None,
                arxiv_id=arxiv_id, authors=_entry_authors(entry),
            )
    return refs


def map_author_year(cites: List[AYCite], refs: Dict[str, AYRef]) -> Dict[str, Optional[AYRef]]:
    """Map each citation key to its reference entry (or None if unmapped)."""
    return {c.key: refs.get(c.key) for c in cites}


# ── LLM-assisted reference parsing (robust on real PDF extractions) ──────────────
# Regex entry-splitting fails on real ACL/EMNLP PDFs: the year is on a different
# line than the author start ("…Mann, Nick Ryder, and\nMelanie Subbiah et al.
# 2020."), surnames wrap with hyphens ("Hoff-\nmann"), and suffix years (2023a/b)
# abound. An LLM parses all of this reliably (validated: 71 refs, 98% citation
# mapping on a real EMNLP survey). Regex parse_author_year_references stays as an
# offline fallback.
import json as _json  # noqa: E402

_REF_PARSE_SYS = (
    "You parse an academic paper's reference list into STRICT JSON: "
    '{"references":[{"surname":<first-author family name>,"year":"<4-digit year, keep suffix like 2023a if present as the year e.g. 2023>","title":<paper title>}]}. '
    "Emit ONE object per reference entry, for EVERY entry. surname is the FIRST "
    "author's family name only. No prose, no markdown fences."
)


def dehyphenate(text: str) -> str:
    """Join words split across a line break by a hyphen ('Hoff-\\nmann' -> 'Hoffmann')."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text or "")


def _chunk_refs(block: str, size: int = 11000) -> List[str]:
    """Split a long references block into <=size chunks at line boundaries."""
    if len(block) <= size:
        return [block]
    chunks, cur = [], []
    n = 0
    for line in block.split("\n"):
        if n + len(line) > size and cur:
            chunks.append("\n".join(cur))
            cur, n = [], 0
        cur.append(line)
        n += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks


async def parse_references_llm(refs_block: str) -> Dict[str, AYRef]:
    """Parse an author-year reference block via the LLM. Falls back to the regex
    parser if the LLM is unavailable or returns nothing."""
    from .llm_verifier import call_llm_json

    if not refs_block or len(refs_block.strip()) < 40:
        return {}
    block = dehyphenate(refs_block)
    refs: Dict[str, AYRef] = {}
    for chunk in _chunk_refs(block):
        raw = await call_llm_json(
            _REF_PARSE_SYS, "Reference list:\n\"\"\"\n" + chunk + "\n\"\"\"\n\nReturn the JSON object only.",
            max_tokens=8000,
        )
        if not raw:
            continue
        s = raw.strip()
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        try:
            data = _json.loads(s)
        except Exception:  # noqa: BLE001
            continue
        items = data.get("references") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for it in items or []:
            if not isinstance(it, dict):
                continue
            sn, yr = it.get("surname"), it.get("year")
            if not sn or not yr:
                continue
            key = ay_key(str(sn), str(yr))
            if key not in refs:
                title = (it.get("title") or "").strip() or None
                refs[key] = AYRef(key=key, surname=str(sn), year=str(yr)[:4],
                                  raw=(title or "")[:200], title=title)
    # Fallback to regex if the LLM produced nothing.
    if not refs:
        return parse_author_year_references(refs_block)
    return refs
