"""
Hallucination taxonomy + snowball/cascade graph + bibliography consistency.

Taxonomy (Ji et al. 2023 × Zhang et al. 2023):
    intrinsic_extrinsic : "intrinsic"  | "extrinsic"
    conflict_type       : "input" | "context" | "reality"

Each non-supported claim is classified here so downstream UIs (and the
researcher) can triage by failure mode.

Snowball graph: a lightweight entity-mention map. If claim B mentions an
entity from a previously-contradicted/unsupported claim A, B inherits a
`cascade_root = A` reference. This surfaces *root* hallucinations rather
than a forest of dependent symptoms (Zhang et al. snowball effect).

Bibliography report: every in-text citation should appear in the
references section, and vice versa. Orphan in-text citations are a
strong source-amnesia signal; uncited bibliography entries are a
common decoration-of-rigour pattern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .ref_integrity import extract_dois


# ────────────────────────────────────────────────────────────────────────────
# Taxonomy
# ────────────────────────────────────────────────────────────────────────────
@dataclass
class Taxonomy:
    intrinsic_extrinsic: str  # "intrinsic" | "extrinsic" | "n/a"
    conflict_type: str        # "input" | "context" | "reality" | "n/a"
    primary_class: str        # e.g. "fabricated_citation"
    notes: Optional[str] = None


# Map fabrication-flag kinds → canonical primary class
_FLAG_TO_CLASS = {
    "numeric_unanchored":      "numeric_hallucination",
    "fabricated_venue":        "fabricated_venue",
    "fabricated_institution":  "fabricated_institution",
    "ghost_author":            "ghost_author",
}


def classify(
    verdict: str,
    fabrication_flags: List[Dict[str, Any]],
    citation_alignment: List[Dict[str, Any]],
    in_text_contradiction: bool,
    has_context_user_provided: bool,
) -> Taxonomy:
    """
    Decide intrinsic/extrinsic and conflict-type for a single claim.
    """
    if verdict == "supported":
        return Taxonomy(intrinsic_extrinsic="n/a", conflict_type="n/a", primary_class="supported")

    # If the claim explicitly contradicts another claim in the same input or
    # a user-provided context, it's intrinsic.
    if in_text_contradiction:
        return Taxonomy(
            intrinsic_extrinsic="intrinsic",
            conflict_type="input" if has_context_user_provided else "context",
            primary_class="logical_contradiction",
            notes="In-document or in-context contradiction detected.",
        )

    # If any citation alignment came back "contradicted", that's reality conflict.
    for a in citation_alignment:
        if a.get("support") == "contradicted":
            return Taxonomy(
                intrinsic_extrinsic="extrinsic",
                conflict_type="reality",
                primary_class="real_doi_wrong_claim",
                notes="Cited source contradicts the claim.",
            )
        if a.get("is_retracted"):
            return Taxonomy(
                intrinsic_extrinsic="extrinsic",
                conflict_type="reality",
                primary_class="retracted_citation",
                notes="Citation points to a retracted work.",
            )
    for a in citation_alignment:
        if a.get("support") == "overstated":
            return Taxonomy(
                intrinsic_extrinsic="extrinsic",
                conflict_type="reality",
                primary_class="overstated_claim",
                notes="Claim generalises/exaggerates beyond what the cited source shows.",
            )
        if a.get("support") in ("unrelated", "partial"):
            return Taxonomy(
                intrinsic_extrinsic="extrinsic",
                conflict_type="reality",
                primary_class="real_doi_wrong_claim",
                notes=f"Cited source is {a.get('support')} to the claim.",
            )

    # Otherwise pick the strongest fabrication flag.
    if fabrication_flags:
        top = max(fabrication_flags, key=lambda f: float(f.get("score") or 0))
        primary = _FLAG_TO_CLASS.get(top["kind"], top["kind"])
        return Taxonomy(
            intrinsic_extrinsic="extrinsic",
            conflict_type="reality",
            primary_class=primary,
            notes=top.get("detail"),
        )

    # Verdict-specific fallback.
    if verdict == "contradicted":
        return Taxonomy(intrinsic_extrinsic="extrinsic", conflict_type="reality", primary_class="factual_fabrication")
    if verdict == "unsupported":
        return Taxonomy(intrinsic_extrinsic="extrinsic", conflict_type="reality", primary_class="source_amnesia",
                        notes="Claim has no resolvable supporting source.")
    return Taxonomy(intrinsic_extrinsic="extrinsic", conflict_type="reality", primary_class="unknown")


def taxonomy_to_dict(t: Taxonomy) -> Dict[str, Any]:
    return {
        "intrinsic_extrinsic": t.intrinsic_extrinsic,
        "conflict_type": t.conflict_type,
        "primary_class": t.primary_class,
        "notes": t.notes,
    }


# ────────────────────────────────────────────────────────────────────────────
# Snowball / cascade graph
# ────────────────────────────────────────────────────────────────────────────
_STOPWORDS = {
    "the","a","an","of","in","on","at","to","for","and","or","but","with","by",
    "is","are","was","were","be","been","being","that","this","it","as","from",
    "into","over","under","than","then","also","such","which","who","whom","what",
    "when","where","why","how","not","no","only","most","more","less","one","two",
    "three","four","five","very","its","their","there","these","those","other",
}
_TOKEN_RE = re.compile(
    r"\b("
    r"[A-Z][a-z]+(?:[-’ʼ'][A-Z][a-z]+)?"   # capitalised word ("Berlin")
    r"|[A-Z]{2,}"                            # acronym ("CRISPR", "NASA")
    r")\b"
)
_NUM_RE = re.compile(r"\b\d{2,}\b")          # numeric tokens (years, counts)


def _entity_tokens(claim: str) -> Set[str]:
    """Cheap entity-mention extractor: capitalised words + 2+ digit numbers."""
    out: Set[str] = set()
    for m in _TOKEN_RE.finditer(claim):
        tok = m.group(1)
        if tok.lower() not in _STOPWORDS:
            out.add(tok)
    out.update(_NUM_RE.findall(claim))
    return out


def annotate_cascades(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Annotate each non-supported claim with cascade_root pointing to the
    earliest non-supported claim that shares ≥2 entity tokens with it.

    Returns the same list, mutated in place.
    """
    entities: List[Set[str]] = [_entity_tokens(c["claim"]) for c in claims]
    for i, c in enumerate(claims):
        if c.get("verdict") == "supported":
            c["cascade_root"] = None
            continue
        own = entities[i]
        if len(own) < 2:
            c["cascade_root"] = None
            continue
        root: Optional[int] = None
        for j in range(i):
            if claims[j].get("verdict") == "supported":
                continue
            shared = own & entities[j]
            if len(shared) >= 2:
                root = j
                break
        if root is not None:
            c["cascade_root"] = {"index": root, "claim": claims[root]["claim"]}
        else:
            c["cascade_root"] = None
    return claims


# ────────────────────────────────────────────────────────────────────────────
# Bibliography ↔ in-text consistency
# ────────────────────────────────────────────────────────────────────────────
_BIB_HEADER_RE = re.compile(r"\n\s*(references|bibliography|works cited)\s*[:\n]", re.IGNORECASE)
_INTEXT_CITE_RE = re.compile(r"\(([^()]*\d{4}[a-z]?[^()]*)\)")
_AUTHOR_YEAR_RE = re.compile(r"([A-Z][A-Za-z\-’ʼ']+(?:\s+(?:et al\.?|and\s+[A-Z][A-Za-z\-]+))?)[,\s]+(?:\d{4})")


@dataclass
class BibliographyReport:
    in_text_citations: List[str] = field(default_factory=list)
    bibliography_entries: List[str] = field(default_factory=list)
    orphan_in_text: List[str] = field(default_factory=list)  # cited inline but not in refs
    uncited_entries: List[str] = field(default_factory=list)  # in refs but never cited inline
    in_text_dois: List[str] = field(default_factory=list)
    bibliography_dois: List[str] = field(default_factory=list)


def _split_body_and_bib(text: str) -> Tuple[str, str]:
    m = _BIB_HEADER_RE.search(text)
    if not m:
        return text, ""
    return text[: m.start()], text[m.end() :]


def _author_year_keys(s: str) -> Set[str]:
    """
    Build a set of (author, year) keys for matching in-text ↔ bibliography.
    Surname is normalised lowercase, year is 4-digit.
    """
    keys: Set[str] = set()
    for m in re.finditer(r"([A-Z][A-Za-z\-’ʼ']+).{0,40}?\b(19|20)(\d{2})\b", s):
        keys.add(f"{m.group(1).lower()}-{m.group(2)}{m.group(3)}")
    return keys


def build_bibliography_report(text: str) -> BibliographyReport:
    body, bib = _split_body_and_bib(text)
    in_text_dois = extract_dois(body)
    bib_dois = extract_dois(bib)

    in_text_cites = [m.group(1).strip() for m in _INTEXT_CITE_RE.finditer(body)][:200]
    bib_entries: List[str] = []
    if bib:
        # Each bibliography entry on its own line / numbered.
        for line in re.split(r"\n+", bib):
            line = line.strip()
            if not line:
                continue
            # Lines without a year are unlikely to be entries.
            if not re.search(r"\b(19|20)\d{2}\b", line):
                continue
            bib_entries.append(line)

    in_text_keys = _author_year_keys(body)
    bib_keys = _author_year_keys(bib) if bib else set()

    orphan_in_text = sorted(in_text_keys - bib_keys) if bib else []
    uncited_entries = sorted(bib_keys - in_text_keys) if bib else []

    return BibliographyReport(
        in_text_citations=in_text_cites,
        bibliography_entries=bib_entries[:200],
        orphan_in_text=orphan_in_text,
        uncited_entries=uncited_entries,
        in_text_dois=in_text_dois,
        bibliography_dois=bib_dois,
    )


def bib_report_to_dict(r: BibliographyReport) -> Dict[str, Any]:
    return {
        "in_text_citations_count": len(r.in_text_citations),
        "bibliography_entries_count": len(r.bibliography_entries),
        "in_text_dois_count": len(r.in_text_dois),
        "bibliography_dois_count": len(r.bibliography_dois),
        "orphan_in_text": r.orphan_in_text[:50],
        "uncited_entries": r.uncited_entries[:50],
    }
