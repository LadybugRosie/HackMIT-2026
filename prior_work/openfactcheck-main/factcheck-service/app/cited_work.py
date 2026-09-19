"""
Cited-work verification for citations that carry NO identifier.

Most LLM-fabricated citations look like this:

    "Park & Williams (2022) in 'Causal Transformers for Time-Series Forecasting' ..."
    "Attention Is All You Need (Vaswani et al., 2017) was published in ICML 2017 ..."

— an author-year cite and/or a title, but no DOI or arXiv id, so the DOI
integrity check and the inline citation aligner never see them. This module
resolves such citations against OpenAlex + Crossref + Semantic Scholar (all
free, no key) and turns the answer into GROUNDED signals:

  * resolved      -> registry evidence (title / authors / year / venue / abstract)
                     so the LLM verifier judges against the real record, plus an
                     optional strict-RAG alignment of the claim vs the abstract
                     (the "real paper, wrong claim" case).
  * ghost author  -> the cited surname is not an author of the resolved work.
  * wrong venue   -> the claim names a well-known venue that differs from the
                     venue every registry records for the work.
  * not found     -> a QUOTED title that no registry knows (only asserted when
                     at least two registries answered).

Precision rules: a lookup that fails (timeout / 429) is "could not check", never
a finding; ghost-author / venue findings require a high-confidence resolution.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .fabrication_detectors import FabricationFlag, flag_to_dict, ghost_author_flags
from .settings import settings
from .source_fetcher import SourceRecord, _light_tokens, search_work, title_similarity

logger = logging.getLogger(__name__)

_SURNAME = r"[A-Z][a-zA-Z'’\-]+"
# (Vaswani et al., 2017) | Vaswani et al. (2017) | (Devlin & Chang, 2019) |
# Park & Williams (2022) | (Krizhevsky, Sutskever, Hinton, 2012) | (Chen et al., NeurIPS 2018)
_AY_RE = re.compile(
    rf"(?P<names>{_SURNAME}(?:\s*,\s*{_SURNAME})*(?:\s*,?\s*(?:&|and)\s+{_SURNAME})?)"
    r"(?P<etal>\s+et al\.?)?"
    r"\s*[,(]?\s*(?:[A-Za-z]+\s+)?(?P<year>(?:19|20)\d{2})[a-z]?\b"
)
_QUOTED_TITLE_RE = re.compile(r"[\"“‘']([A-Z][^\"”’']{12,180}?)[\"”’']")
_SPEECH_CUE_RE = re.compile(
    r"\b(said|says|stated|declared|noted|wrote|remarked|words|quoted?|speech|famously|slogan|motto)\b\W*$",
    re.I,
)
# Tokens that look like a surname but are venues / lead-ins, never authors.
_NOT_SURNAME = {
    "Nature", "Science", "Cell", "Lancet", "In", "The", "See", "As", "By", "Vol",
    "NeurIPS", "NIPS", "ICML", "ICLR", "ACL", "NAACL", "EMNLP", "CVPR", "ICCV", "ECCV",
    "AAAI", "IJCAI", "KDD", "SIGIR", "CHI", "WWW", "COLING", "PNAS", "NEJM", "JAMA",
    "Proceedings", "Journal", "Press", "University", "Institute", "Conference", "Workshop",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Since", "Between", "From", "Until",
}

# Well-known venues: canonical key -> phrases that identify it in a registry's
# venue string (checked in order; more specific entries first).
_VENUE_CANON: List[Tuple[str, List[str]]] = [
    ("naacl", ["north american chapter"]),
    ("emnlp", ["empirical methods in natural language"]),
    ("coling", ["international conference on computational linguistics"]),
    ("acl", ["annual meeting of the association for computational linguistics",
             "association for computational linguistics"]),
    ("neurips", ["neural information processing"]),
    ("icml", ["international conference on machine learning"]),
    ("iclr", ["international conference on learning representations", "learning representations"]),
    ("cvpr", ["computer vision and pattern recognition"]),
    ("iccv", ["international conference on computer vision"]),
    ("eccv", ["european conference on computer vision"]),
    ("aaai", ["aaai conference on artificial intelligence", "aaai"]),
    ("ijcai", ["international joint conference on artificial intelligence", "ijcai"]),
    ("kdd", ["knowledge discovery and data mining", "knowledge discovery & data mining"]),
    ("sigir", ["research and development in information retrieval", "sigir"]),
    ("chi", ["human factors in computing systems"]),
    ("www", ["world wide web conference", "the web conference"]),
    ("pnas", ["proceedings of the national academy of sciences"]),
    ("nejm", ["new england journal of medicine"]),
    ("jama", ["jama"]),
    ("lancet", ["lancet"]),
]
_VENUE_EXACT = {"nature": "nature", "science": "science", "cell": "cell"}
_CLAIMED_VENUE_RE = re.compile(
    r"\b(NeurIPS|NIPS|ICML|ICLR|NAACL|EMNLP|COLING|ACL|CVPR|ICCV|ECCV|AAAI|IJCAI|KDD|SIGIR|CHI|WWW|"
    r"PNAS|NEJM|JAMA|Nature|Science|Cell|Lancet)\b"
)
_VENUE_LEADIN_RE = re.compile(
    r"\b(published|appeared|presented|accepted|proceedings|in|at)\b[^.;]{0,40}$", re.I
)
_ACRONYM_ALIAS = {"nips": "neurips"}


def venue_key(venue: Optional[str]) -> Optional[str]:
    """Map a registry venue string to a canonical well-known venue key, or None."""
    v = (venue or "").lower().strip()
    if not v:
        return None
    if v in _VENUE_EXACT:
        return _VENUE_EXACT[v]
    if "arxiv" in v or "preprint" in v or "ssrn" in v or "biorxiv" in v:
        return None
    for key, phrases in _VENUE_CANON:
        if any(p in v for p in phrases):
            return key
    return None


def claimed_venues(text: str) -> List[str]:
    """Well-known venue acronyms the claim asserts the work appeared in."""
    out: List[str] = []
    for m in _CLAIMED_VENUE_RE.finditer(text):
        tok = m.group(1)
        before = text[max(0, m.start() - 45):m.start()]
        # 'Nature'/'Science'/'Cell' are ordinary words too — need a publication lead-in.
        if tok in ("Nature", "Science", "Cell", "Lancet") and not _VENUE_LEADIN_RE.search(before):
            continue
        key = _ACRONYM_ALIAS.get(tok.lower(), tok.lower())
        if key not in out:
            out.append(key)
    return out


def extract_author_year_cites(text: str) -> List[Dict[str, Any]]:
    """Author-year citations in the text: [{surnames, et_al, year, start, end, raw}]."""
    cites: List[Dict[str, Any]] = []
    for m in _AY_RE.finditer(text):
        names = re.split(r"\s*,\s*|\s+(?:&|and)\s+", m.group("names"))
        names = [re.sub(r"^(?:and|&)\s+", "", n).rstrip("'’s") if n.endswith(("'s", "’s")) else re.sub(r"^(?:and|&)\s+", "", n)
                 for n in names if n]
        names = [n for n in names if n]
        # Acronyms ("IEEE (2020)", "WHO 2023") are organisations, not authors.
        if not names or any(n in _NOT_SURNAME or (len(n) >= 3 and n.isupper()) for n in names):
            continue
        et_al = bool(m.group("etal"))
        multi = len(names) > 1
        after = text[m.end("names"):m.start("year")]
        # A bare "Smith 2020" is not a citation; require et al., a co-author, or
        # citation punctuation ("Smith (2020)", "(Smith, 2020)").
        if not (et_al or multi or "(" in after or "," in after):
            continue
        cites.append({
            "surnames": names, "et_al": et_al, "year": int(m.group("year")),
            "start": m.start(), "end": m.end(), "raw": m.group(0),
        })
    return cites


def extract_quoted_titles(text: str) -> List[Dict[str, Any]]:
    """Quoted work titles (not direct speech): [{title, start, end}]."""
    out: List[Dict[str, Any]] = []
    for m in _QUOTED_TITLE_RE.finditer(text):
        title = m.group(1).strip().rstrip(",.;:")
        if len(title.split()) < 3:
            continue
        if _SPEECH_CUE_RE.search(text[max(0, m.start() - 40):m.start()]):
            continue
        # Direct speech: a full sentence with a verb-heavy lowercase body.
        words = title.split()
        caps = sum(1 for w in words if w[:1].isupper())
        if caps / len(words) < 0.4 and len(words) > 8:
            continue
        out.append({"title": title, "start": m.start(), "end": m.end()})
    return out


def has_citation_anchor(text: str) -> bool:
    """True if the sentence carries something a source check can hang on: a DOI,
    arXiv id, URL, quoted title or author-year citation. Such sentences are
    verified as a unit against their source — never decomposed (decomposition
    strips the identifier and orphans the sub-claims)."""
    if re.search(r"10\.\d{4,9}/|https?://|arxiv[:\s]*\d{4}\.\d{4,5}", text, re.I):
        return True
    if extract_quoted_titles(text) or extract_author_year_cites(text):
        return True
    return False


_LEADIN_WORDS = {
    "as", "shown", "by", "in", "the", "seminal", "work", "of", "see", "e.g.", "cf.",
    "according", "to", "described", "reported", "demonstrated", "established", "framework",
    "building", "on", "upon", "extended", "extending", "following", "and", "with", "from",
    "also", "later", "first", "recently", "paper", "study", "their", "his", "her", "its",
}


def _preceding_title_query(text: str, cite_start: int, floor: int = 0) -> Optional[str]:
    """Text right before an author-year cite (same clause), as a title query —
    'Attention Is All You Need (Vaswani et al., 2017)' -> 'Attention Is All You Need'.
    `floor` is the end of the previous citation / quoted title, so a second cite
    in the sentence never inherits the first one's title."""
    before = text[floor:cite_start]
    before = re.split(r"[.;!?]\s|\n", before)[-1]
    before = re.sub(r"[(\[]\s*$", "", before).strip(" ,:-–—")
    words = before.split()[-14:]
    # drop leading punctuation / lead-in words ("As shown by", "the seminal
    # work of", ") was later extended by")
    _skip = _LEADIN_WORDS | {"was", "were", "is", "are", "has", "have", "had", "been", "who",
                             "which", "that", "then", "this", "these", "those", "it", "they", "we"}
    while words and (not re.search(r"[A-Za-z0-9]", words[0]) or words[0].lower().strip(",.:;") in _skip):
        words.pop(0)
    if len(words) < 2:
        return None
    content = [w for w in words if w.lower().strip(",.:") not in _skip]
    if len(content) < 2:
        return None
    return " ".join(words)


def _coverage(found_title: str, claim: str) -> float:
    """Share of the found title's distinctive tokens that appear in the claim."""
    ft = {t for t in _light_tokens(found_title) if len(t) >= 4}
    if not ft:
        return 0.0
    ct = _light_tokens(claim)
    return len(ft & ct) / len(ft)


def _first_surname_matches(surnames: List[str], rec: SourceRecord) -> bool:
    from .fabrication_detectors import _surname_matches
    return bool(surnames) and _surname_matches(surnames[0], rec)


def _year_ok(rec: SourceRecord, year: Optional[int]) -> bool:
    return bool(year and rec.year and abs(rec.year - year) <= 1)


async def _resolve(query: str, claim: str, surnames: List[str], quoted: bool,
                   year: Optional[int]) -> Dict[str, Any]:
    """Resolve a title query across the registries.

    Returns {accepted: [(rec, sim, author_ok)], best: rec|None, best_sim,
             conclusive, closest: (rec, sim)|None}.
    Acceptance is deliberately strict — a wrong resolution is worse than none:
      quoted title   : sim >= 0.9, or sim >= 0.75 with a cited surname on the record
      preceding text : a cited surname on the record and >= 60% of the found
                       title's distinctive words in the claim, or sim >= 0.9
    """
    cands, answered = await search_work(query, year=year)
    accepted: List[Tuple[SourceRecord, float, bool]] = []
    for rec, sim in cands[:10]:
        cov = _coverage(rec.title or "", claim)
        author_ok = _first_surname_matches(surnames, rec)
        if quoted:
            ok = sim >= 0.9 or (sim >= 0.75 and author_ok)
        else:
            ok = (cov >= 0.6 and author_ok) or sim >= 0.9
        if ok:
            accepted.append((rec, sim, author_ok))
    # Rank: author corroboration, then year agreement, then a real venue /
    # abstract, then similarity — so the original record beats a reprint.
    accepted.sort(key=lambda t: (t[2], _year_ok(t[0], year), bool(t[0].venue), bool(t[0].abstract or t[0].tldr), t[1]),
                  reverse=True)
    return {
        "accepted": accepted,
        "best": accepted[0][0] if accepted else None,
        "best_sim": cands[0][1] if cands else 0.0,
        "answered": answered,
        "conclusive": len(answered),
        "closest": cands[0] if cands else None,
    }


def _registry_evidence(rec: SourceRecord, label: str) -> Dict[str, Any]:
    authors = ", ".join(a.name for a in rec.authors[:4]) + (" et al." if len(rec.authors) > 4 else "")
    parts = [f"Registry record for {label}: '{rec.title}'"]
    if authors:
        parts.append(f"by {authors}")
    if rec.year:
        parts.append(f"({rec.year})")
    if rec.venue:
        parts.append(f"in {rec.venue}")
    if rec.doi:
        parts.append(f"DOI {rec.doi}")
    snippet = " ".join(parts) + "."
    body = rec.tldr or rec.abstract
    if body:
        snippet += f" Abstract: {body[:450]}"
    url = f"https://doi.org/{rec.doi}" if rec.doi else (
        f"https://arxiv.org/abs/{rec.arxiv_id}" if rec.arxiv_id else rec.openalex_id)
    src = "Registry match (" + ", ".join(sorted(set(rec.sources_consulted)) or ["openalex"]) + ")"
    return {"source": src, "snippet": snippet, "url": url}


async def verify_cited_work(claim: str) -> Optional[Dict[str, Any]]:
    """Verify the work(s) a claim cites by author-year and/or title.

    Returns None when the claim has no such citation, else a dict:
      verdict        : "contradicted" | "unsupported" | None (evidence only)
      evidence_items : registry evidence for the LLM verifier
      alignment      : strict-RAG alignment dict (claim vs abstract) or None
      flags          : fabrication flag dicts (ghost_author / fabricated_citation)
    """
    cites = extract_author_year_cites(claim)
    titles = extract_quoted_titles(claim)
    if not cites and not titles:
        return None

    # Pair each cite with the nearest quoted title (within 120 chars), else with
    # the text preceding it; a quoted title with no cite is checked alone.
    jobs: List[Dict[str, Any]] = []
    # Each quoted title belongs to ONE cite: the nearest within 120 chars.
    title_for_cite: Dict[int, Dict[str, Any]] = {}
    for t in titles:
        near = None
        for ci, c in enumerate(cites):
            dist = min(abs(t["start"] - c["end"]), abs(c["start"] - t["end"]))
            if dist <= 120 and (near is None or dist < near[0]):
                near = (dist, ci)
        if near is not None and near[1] not in title_for_cite:
            title_for_cite[near[1]] = t
    boundaries = sorted([c["end"] for c in cites] + [t["end"] for t in titles])
    for ci, c in enumerate(cites):
        t = title_for_cite.get(ci)
        if t:
            jobs.append({"query": t["title"], "quoted": True, "surnames": c["surnames"],
                         "et_al": c["et_al"], "year": c["year"]})
        else:
            floor = max([b for b in boundaries if b <= c["start"]], default=0)
            q = _preceding_title_query(claim, c["start"], floor)
            if q:
                jobs.append({"query": q, "quoted": False, "surnames": c["surnames"],
                             "et_al": c["et_al"], "year": c["year"]})
    assigned = {t["title"] for t in title_for_cite.values()}
    for t in titles:
        if t["title"] not in assigned:
            jobs.append({"query": t["title"], "quoted": True, "surnames": [], "et_al": False, "year": None})
    if not jobs:
        return None
    jobs = jobs[:3]  # bound registry traffic per claim

    evidence_items: List[Dict[str, Any]] = []
    flags: List[FabricationFlag] = []
    verdict: Optional[str] = None
    resolved: List[Tuple[SourceRecord, Dict[str, Any], bool, list]] = []

    for job in jobs:
        res = await _resolve(job["query"], claim, job["surnames"], job["quoted"], job["year"])
        rec = res["best"]
        label = (f"'{job['query']}'" if job["quoted"] else
                 f"{job['surnames'][0]}{' et al.' if job['et_al'] else ''} ({job['year']})")
        if rec is None:
            # A QUOTED title is an unambiguous pointer to one specific work. If
            # at least two registries answered and none holds it (by title, or
            # by a near-title with the cited author), that is a grounded finding.
            # Semantic Scholar is the index most likely to hold CS / preprint-only
            # works (GPT-2's report has no DOI and is absent from Crossref), so a
            # "not found" is only asserted when S2 answered plus one more registry.
            if job["quoted"] and res["conclusive"] >= 2 and "semantic_scholar" in res["answered"]:
                closest = res["closest"]
                near = ""
                if closest and closest[1] >= 0.6 and closest[0].title:
                    c_auth = ", ".join(a.name for a in closest[0].authors[:3]) or "unknown authors"
                    near = (f" Closest registry title: '{closest[0].title}' by {c_auth}"
                            f" ({closest[0].year or 'n.d.'}), similarity {closest[1]:.2f}, "
                            f"not by the cited author(s).")
                flags.append(FabricationFlag(
                    kind="fabricated_citation",
                    detail=(f"No work titled {label} was found in OpenAlex, Crossref or Semantic Scholar "
                            f"({res['conclusive']} registries answered).{near}"),
                    span=job["query"], score=0.9,
                    sources_consulted=["openalex", "crossref", "semantic_scholar"][:res["conclusive"]],
                ))
                if near:
                    evidence_items.append({
                        "source": "Registry search (openalex, crossref, semantic_scholar)",
                        "snippet": f"No exact match for {label}.{near}",
                        "url": None,
                    })
                verdict = verdict or "unsupported"
            continue
        # Any accepted candidate carrying the cited surname wins; a ghost-author
        # flag needs a confident resolution AND no candidate with that author.
        author_any = any(a_ok for _, _, a_ok in res["accepted"])
        high = author_any or any(sim >= 0.9 for _, sim, _ in res["accepted"])
        resolved.append((rec, job, high, res["accepted"]))
        evidence_items.append(_registry_evidence(rec, label))
        if high and job["surnames"]:
            # A surname is a ghost only if it is on NONE of the matching records
            # (registries hold partial / junk duplicates of famous papers — one
            # OpenAlex record lists AlexNet with a single author).
            union = SourceRecord(authors=[a for r, _, _ in res["accepted"] for a in r.authors])
            check = job["surnames"][:1] if job["et_al"] else job["surnames"]
            fullest = max((r for r, _, _ in res["accepted"]), key=lambda r: len(r.authors))
            for f in ghost_author_flags(check, union, f"'{fullest.title}'"):
                f.candidate = ", ".join(a.name.split()[-1] for a in fullest.authors[:5] if a.name)
                f.detail = (f"In-text citation names '{f.span}' but '{fullest.title}' is authored by: "
                            f"{', '.join(a.name for a in fullest.authors[:5])}.")
                flags.append(f)

    # Venue check: contradict only when the claim names a well-known venue and
    # EVERY registry record for the work that maps to a known venue disagrees
    # (arXiv / unmapped venues are ignored; one agreeing record clears it).
    claimed = claimed_venues(claim)
    if claimed and resolved:
        for rec, job, high, accepted in resolved:
            if not high:
                continue
            keys = {venue_key(r.venue) for r, _, _ in accepted} - {None}
            if not keys or keys & set(claimed):
                continue
            wrong = [c for c in claimed if c not in keys]
            if wrong:
                src_rec = next((r for r, _, _ in accepted if venue_key(r.venue)), rec)
                verdict = "contradicted"
                evidence_items.append({
                    "source": "Registry match (venue)",
                    "snippet": (f"'{src_rec.title}' is recorded in {src_rec.venue} "
                                f"({', '.join(sorted(set(src_rec.sources_consulted)))}), not {wrong[0].upper()} "
                                f"as the claim states."),
                    "url": f"https://doi.org/{src_rec.doi}" if src_rec.doi else None,
                })
                break

    # Strict-RAG alignment of the claim against the best resolved abstract
    # ("real paper, wrong claim"). Same machinery as DOI alignment.
    alignment: Optional[Dict[str, Any]] = None
    if resolved and settings.ENABLE_LLM_VERIFICATION and settings.ENABLE_CITATION_ALIGNMENT:
        rec, job, high, _acc = resolved[0]
        # Prefer a record that actually has an abstract for the alignment.
        for r, _, _ in _acc:
            if r.abstract or r.tldr:
                rec = r
                break
        blob = rec.best_text()
        if blob and (rec.abstract or rec.tldr):
            try:
                from .citation_alignment import CitationAlignment, alignment_to_dict, score_support
                scored = await score_support(claim, blob, source_label=rec.title or "cited work")
                a = CitationAlignment(
                    doi=rec.doi or (f"arXiv:{rec.arxiv_id}" if rec.arxiv_id else f"title:{(rec.title or '')[:60]}"),
                    claim_context=claim, source_title=rec.title, source_year=rec.year,
                    source_authors=[x.name for x in rec.authors[:10]], source_venue=rec.venue,
                    is_retracted=rec.is_retracted, retraction_note=rec.retraction_note,
                    sources_consulted=list(rec.sources_consulted), evidence_scope="abstract",
                )
                a.support = scored["support"]
                a.supporting_span = scored["supporting_span"]
                a.missing_aspects = scored["missing_aspects"]
                a.confidence = scored["confidence"]
                a.notes = scored.get("notes")
                alignment = alignment_to_dict(a)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Cited-work alignment failed: {e}")

    return {
        "verdict": verdict,
        "evidence_items": evidence_items,
        "alignment": alignment,
        "flags": [flag_to_dict(f) for f in flags],
        "resolved": bool(resolved),
    }
