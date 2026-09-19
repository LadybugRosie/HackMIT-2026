"""
Calibrated confidence + domain severity.

The old version mixed source quality, agreement, and a default of 50 in a
heuristic that gave "unknown" the same shape as "no evidence found" — bad
for researchers triaging hallucinations.

This version is a *signal vector*: each binary/scalar signal contributes a
fixed weight. Same shape as before (score+breakdown+grade+explanation) so
nothing downstream breaks, plus four new fields:

  - signals          : the raw 0/1 inputs
  - failure_mode     : "no_evidence_found" | "conflicting_evidence" |
                       "partial_support" | None
  - severity         : "critical" | "high" | "medium" | "low"
  - domain           : "medical" | "legal" | "scientific" | "historical" |
                       "creative" | "code" | "general"

The article makes the explicit point that the consequence of a hallucination
is field-dependent (medical = critical, creative = low). We surface that here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ────────────────────────────────────────────────────────────────────────────
# Source tiers (same idea as before, broader list)
# ────────────────────────────────────────────────────────────────────────────
_TIER_1_SOURCES = {
    "nasa", "nih", "cdc", "nist", "nature", "science", "lancet", "nejm",
    "nobel prize official", "un official", "who", "ieee", "acm",
    "crossref", "datacite", "openalex", "unpaywall", "pubmed",
    "semantic scholar", "ror", "doi registry",
}
_TIER_2_SOURCES = {
    "wikipedia", "wikidata", "arxiv", "google ai blog", "openai", "cern",
    "smithsonian", "scientific american", "mdn web docs",
}


def _source_tier(source_name: str) -> int:
    n = (source_name or "").lower()
    if any(t in n for t in _TIER_1_SOURCES):
        return 1
    if any(t in n for t in _TIER_2_SOURCES):
        return 2
    return 3


# ────────────────────────────────────────────────────────────────────────────
# Domain detection — keyword sets
# ────────────────────────────────────────────────────────────────────────────
_DOMAIN_KEYWORDS: List[tuple[str, List[str]]] = [
    ("medical",     ["clinical","trial","rct","patient","mortality","placebo","fda","cdc","who","vaccine","diagnosis","therapy","hospital","drug"]),
    ("legal",       ["court","statute","treaty","precedent","ruling","plaintiff","defendant","supreme court","circuit","jurisdiction","legislation"]),
    ("code",        ["api","library","function","module","package","import","compile","github","stack overflow","sdk"]),
    ("scientific",  ["doi","arxiv","journal","conference","p-value","p value","peer-reviewed","meta-analysis","cohort","randomised","randomized"]),
    ("historical",  ["century","ad","bc","empire","war","revolution","king","queen","emperor","dynasty"]),
    ("creative",    ["novel","poem","fiction","prose","metaphor","plot","character","narrative"]),
]


def detect_domain(claim: str) -> str:
    c = claim.lower()
    for domain, kws in _DOMAIN_KEYWORDS:
        if any(kw in c for kw in kws):
            return domain
    return "general"


_DOMAIN_SEVERITY = {
    "medical":    {"contradicted": "critical", "unsupported": "high",   "unknown": "high"},
    "legal":      {"contradicted": "critical", "unsupported": "high",   "unknown": "high"},
    "scientific": {"contradicted": "high",     "unsupported": "high",   "unknown": "medium"},
    "code":       {"contradicted": "high",     "unsupported": "medium", "unknown": "medium"},
    "historical": {"contradicted": "medium",   "unsupported": "medium", "unknown": "low"},
    "creative":   {"contradicted": "low",      "unsupported": "low",    "unknown": "low"},
    "general":    {"contradicted": "medium",   "unsupported": "medium", "unknown": "low"},
}


def compute_severity(verdict: str, domain: str) -> str:
    if verdict == "supported":
        return "low"
    return _DOMAIN_SEVERITY.get(domain, _DOMAIN_SEVERITY["general"]).get(verdict, "medium")


# ────────────────────────────────────────────────────────────────────────────
# Failure-mode classifier
# ────────────────────────────────────────────────────────────────────────────
def _failure_mode(
    verdict: str,
    evidence: List[Dict[str, Any]],
    citation_alignment: List[Dict[str, Any]],
    fabrication_flags: List[Dict[str, Any]],
) -> Optional[str]:
    if verdict == "supported":
        return None
    if any(a.get("support") == "contradicted" for a in citation_alignment):
        return "conflicting_evidence"
    if any(a.get("support") in ("partial",) for a in citation_alignment):
        return "partial_support"
    if any(a.get("support") in ("unrelated",) for a in citation_alignment):
        return "conflicting_evidence"
    if not evidence and not fabrication_flags:
        return "no_evidence_found"
    if fabrication_flags:
        return "no_evidence_found"
    return None


# ────────────────────────────────────────────────────────────────────────────
# Public API (signature backward-compatible with the old one — new kwargs
# are optional)
# ────────────────────────────────────────────────────────────────────────────
def compute_confidence(
    verdict: str,
    evidence: List[Dict[str, Any]],
    llm_result: Optional[Dict[str, Any]] = None,
    knowledge_base_match: bool = False,
    doi_verified: bool = False,
    # new optional inputs
    claim_text: str = "",
    citation_alignment: Optional[List[Dict[str, Any]]] = None,
    fabrication_flags: Optional[List[Dict[str, Any]]] = None,
    source_content_aligned: bool = False,
) -> Dict[str, Any]:
    citation_alignment = citation_alignment or []
    fabrication_flags = fabrication_flags or []

    n_evidence = len(evidence)
    tier1 = sum(1 for ev in evidence if _source_tier(ev.get("source", "")) == 1)
    tier2 = sum(1 for ev in evidence if _source_tier(ev.get("source", "")) == 2)
    has_url = sum(1 for ev in evidence if ev.get("url"))
    n_aligned = sum(1 for a in citation_alignment if a.get("support") == "supported")
    n_retracted = sum(1 for a in citation_alignment if a.get("is_retracted"))
    llm_conf = int(llm_result.get("confidence", 0)) if llm_result else 0
    llm_agrees = (llm_result.get("verdict") == verdict) if (llm_result and verdict != "unknown") else False

    signals = {
        "kb_match": bool(knowledge_base_match),
        "doi_resolved": bool(doi_verified),
        "source_content_aligned": bool(source_content_aligned or n_aligned > 0),
        "tier1_sources": tier1,
        "tier2_sources": tier2,
        "evidence_count": n_evidence,
        "evidence_with_url": has_url,
        "llm_confidence": llm_conf,
        "llm_agrees": llm_agrees,
        "citation_alignment_count": n_aligned,
        "retracted_citation_count": n_retracted,
        "fabrication_flag_count": len(fabrication_flags),
    }

    # ── Source quality (0-100)
    source_quality = 0
    if knowledge_base_match:
        source_quality += 35
    if doi_verified:
        source_quality += 20
    if source_content_aligned or n_aligned > 0:
        source_quality += 25
    source_quality += min(20, tier1 * 7)
    source_quality += min(10, tier2 * 3)
    source_quality = min(100, source_quality)

    # ── Evidence strength (0-100)
    evidence_strength = 0
    if knowledge_base_match:
        evidence_strength += 40
    evidence_strength += min(25, n_evidence * 8)
    evidence_strength += min(10, has_url * 4)
    evidence_strength += int(llm_conf * 0.25)
    if n_aligned > 0:
        evidence_strength += 20
    if fabrication_flags:
        evidence_strength -= min(15, len(fabrication_flags) * 5)
    evidence_strength = max(0, min(100, evidence_strength))

    # ── Source agreement (0-100)
    source_agreement = 50
    if n_evidence >= 2: source_agreement += 15
    if n_evidence >= 3: source_agreement += 10
    if llm_agrees:      source_agreement += 15
    if any(a.get("support") == "contradicted" for a in citation_alignment):
        source_agreement -= 25
    source_agreement = max(0, min(100, source_agreement))

    score = int(source_quality * 0.30 + evidence_strength * 0.45 + source_agreement * 0.25)
    score = max(0, min(100, score))

    # Hard caps reflecting failure modes
    if verdict == "unknown":
        score = min(score, 30)
    if n_retracted:
        # Retracted source → score not low, but verdict should already be contradicted
        score = max(score, 70)

    grade = _score_to_grade(score)
    domain = detect_domain(claim_text) if claim_text else "general"
    severity = compute_severity(verdict, domain)
    failure_mode = _failure_mode(verdict, evidence, citation_alignment, fabrication_flags)
    explanation = _build_explanation(score, grade, verdict, evidence, llm_result, knowledge_base_match, citation_alignment, fabrication_flags)

    return {
        "score": score,
        "breakdown": {
            "source_quality": source_quality,
            "evidence_strength": evidence_strength,
            "source_agreement": source_agreement,
        },
        "grade": grade,
        "explanation": explanation,
        "signals": signals,
        "failure_mode": failure_mode,
        "severity": severity,
        "domain": domain,
    }


def _score_to_grade(score: int) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 50: return "C"
    if score >= 30: return "D"
    return "F"


def _build_explanation(
    score: int,
    grade: str,
    verdict: str,
    evidence: List[Dict[str, Any]],
    llm_result: Optional[Dict[str, Any]],
    kb_match: bool,
    citation_alignment: List[Dict[str, Any]],
    fabrication_flags: List[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if verdict == "unknown":
        parts.append("Insufficient evidence to verify this claim.")
    elif verdict == "supported":
        parts.append("Claim is supported by available evidence.")
    elif verdict == "contradicted":
        parts.append("Claim is contradicted by available evidence.")
    elif verdict == "unsupported":
        parts.append("Claim lacks verifiable supporting evidence.")

    if evidence:
        sources = sorted({(ev.get("source") or "").split("(")[0].strip() for ev in evidence if ev.get("source")})
        sources = [s for s in sources if s]
        if sources:
            parts.append(f"Based on {len(evidence)} evidence item{'s' if len(evidence) > 1 else ''}: {', '.join(sources)}.")
    if kb_match:
        parts.append("Matched against curated knowledge base.")
    contradicted_cites = [a for a in citation_alignment if a.get("support") == "contradicted"]
    if contradicted_cites:
        parts.append(f"{len(contradicted_cites)} cited source(s) contradict the claim.")
    retracted = [a for a in citation_alignment if a.get("is_retracted")]
    if retracted:
        parts.append(f"{len(retracted)} cited source(s) are retracted.")
    if fabrication_flags:
        kinds = sorted({f["kind"] for f in fabrication_flags})
        parts.append(f"Fabrication flags: {', '.join(kinds)}.")
    if llm_result and llm_result.get("reasoning"):
        parts.append(f"AI analysis: {llm_result['reasoning']}")
    return " ".join(parts)
