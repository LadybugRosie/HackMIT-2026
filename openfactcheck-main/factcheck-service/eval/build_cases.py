"""
Build eval/cases.jsonl from the existing test files.

Reads test_academic_hallucinations.py and test_hallucination_taxonomy.py via
Python AST (no execution), extracts the TC(...) / TestCase(...) literals,
maps the free-text category to a taxonomy label, and emits one JSON object
per case.

Output schema:
{
  "id": int,
  "claim": str,
  "is_hallucination": bool,
  "category": str,                # original free-text category
  "class": str,                   # canonical fabrication class
  "taxonomy": {
      "intrinsic_extrinsic": "intrinsic" | "extrinsic" | "n/a",
      "conflict_type": "input" | "context" | "reality" | "n/a"
  },
  "domain": "medical" | "legal" | "scientific" | "historical" | "creative" | "code" | "general",
  "expected_verdict": "supported" | "contradicted" | "unsupported",
  "why": str
}
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "cases.jsonl"

# ────────────────────────────────────────────────────────────────────────────
# Taxonomy mapping (Ji et al. 2023 + Zhang et al. 2023 + Athaluri et al. 2023)
# ────────────────────────────────────────────────────────────────────────────
# Each row maps the original free-text "category" to:
#   (canonical_class, intrinsic_or_extrinsic, conflict_type, domain)
CATEGORY_MAP: Dict[str, Tuple[str, str, str, str]] = {
    # academic hallucinations file
    "Fake DOI":                    ("fabricated_citation",  "extrinsic", "reality",  "scientific"),
    "Phantom arXiv":               ("fabricated_citation",  "extrinsic", "reality",  "scientific"),
    "Retraction Fabrication":      ("fabricated_event",     "extrinsic", "reality",  "scientific"),
    "Journal Doppelgänger":        ("fabricated_venue",     "extrinsic", "reality",  "scientific"),
    "Fabricated Metrics":          ("fabricated_metric",    "extrinsic", "reality",  "scientific"),
    "Ghost Author":                ("ghost_author",         "extrinsic", "reality",  "scientific"),
    "Frankenstein Citation":       ("frankenstein_citation","extrinsic", "reality",  "scientific"),
    "Fake Benchmark":              ("fabricated_benchmark", "extrinsic", "reality",  "scientific"),
    # taxonomy file
    "Factual Fabrication":         ("factual_fabrication",  "extrinsic", "reality",  "general"),
    "Entity Confusion":            ("entity_confusion",     "extrinsic", "reality",  "general"),
    "Numerical Hallucination":     ("numeric_hallucination","extrinsic", "reality",  "scientific"),
    "Citation Fabrication":        ("fabricated_citation",  "extrinsic", "reality",  "scientific"),
    "Temporal Distortion":         ("temporal_distortion",  "extrinsic", "reality",  "historical"),
    "Logical Contradiction":       ("logical_contradiction","intrinsic", "context",  "general"),
    "Misattribution":              ("misattribution",       "extrinsic", "reality",  "general"),
    "Confabulation":               ("confabulation",        "extrinsic", "reality",  "general"),
    "Overconfident Assertion":     ("overconfident",        "extrinsic", "reality",  "general"),
    "Subtle Errors":               ("subtle_error",         "extrinsic", "reality",  "general"),
    "Fabricated Institutions":     ("fabricated_institution","extrinsic","reality",  "general"),
    "Fabricated Laws":             ("fabricated_law",       "extrinsic", "reality",  "legal"),
    "Code Hallucination":          ("code_hallucination",   "extrinsic", "reality",  "code"),
    "Aggregation Errors":          ("aggregation_error",    "extrinsic", "reality",  "general"),
    "Snowball":                    ("snowball",             "intrinsic", "context",  "general"),
    "Source Amnesia":              ("source_amnesia",       "extrinsic", "reality",  "general"),
    # Additional categories observed in test_academic_hallucinations.py
    "Aggregation Hallucination":   ("aggregation_error",    "extrinsic", "reality",  "general"),
    "Citation Chain":              ("citation_chain",       "extrinsic", "reality",  "scientific"),
    "Contextual Misattribution":   ("misattribution",       "extrinsic", "reality",  "general"),
    "Dead Link":                   ("dead_link",            "extrinsic", "reality",  "general"),
    "Fake Funding":                ("fabricated_funding",   "extrinsic", "reality",  "scientific"),
    "Fake Legal":                  ("fabricated_law",       "extrinsic", "reality",  "legal"),
    "Fake Proceedings":            ("fabricated_venue",     "extrinsic", "reality",  "scientific"),
    "Fake Review History":         ("fabricated_event",     "extrinsic", "reality",  "scientific"),
    "Fake Statistics":             ("numeric_hallucination","extrinsic", "reality",  "scientific"),
    "Geographic/Institutional":    ("fabricated_institution","extrinsic","reality",  "general"),
    "Legal Fabrication":           ("fabricated_law",       "extrinsic", "reality",  "legal"),
    "Medical Hallucination":       ("medical_hallucination","extrinsic", "reality",  "medical"),
    "Source Fabrication":          ("fabricated_citation",  "extrinsic", "reality",  "scientific"),
    "Subtle Plausibility":         ("subtle_error",         "extrinsic", "reality",  "general"),
}


def _string_value(node: ast.AST) -> Optional[str]:
    """Extract a string literal from an AST node, joining concatenated strings."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        l = _string_value(node.left) or ""
        r = _string_value(node.right) or ""
        return l + r
    if isinstance(node, ast.JoinedStr):  # f-string
        return None
    return None


def _bool_value(node: ast.AST) -> Optional[bool]:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _int_value(node: ast.AST) -> Optional[int]:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _expected_verdict(is_hallucination: bool, klass: str) -> str:
    """
    Map (is_hallucination, class) → expected verdict.
    Conservative: every hallucination should land at contradicted OR unsupported.
    Cases that ARE true facts → supported.
    """
    if not is_hallucination:
        return "supported"
    # Hallucinations involving real-world contradiction (Berlin Wall in 1991,
    # Bezos founded Apple) → contradicted. Fabricated entities / unverifiable
    # specifics → unsupported.
    contradiction_classes = {
        "entity_confusion", "temporal_distortion", "logical_contradiction",
        "subtle_error", "factual_fabrication", "misattribution",
        "overconfident",
    }
    if klass in contradiction_classes:
        return "contradicted"
    return "unsupported"


def parse_test_file(path: Path) -> List[Dict]:
    """Parse a test file and pull out TC(...) / TestCase(...) calls."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    cases: List[Dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in ("TC", "TestCase"):
            continue
        if len(node.args) < 4:
            continue

        # TC(id, cat, claim, is_hall, why=...)
        # TestCase(id, category, claim, is_hallucination, description=...)
        tid = _int_value(node.args[0])
        cat = _string_value(node.args[1])
        claim = _string_value(node.args[2])
        is_hall = _bool_value(node.args[3])
        why = _string_value(node.args[4]) if len(node.args) > 4 else ""

        if tid is None or cat is None or claim is None or is_hall is None:
            continue

        # Default mapping if category not known
        klass, ie, ct, domain = CATEGORY_MAP.get(
            cat, ("uncategorised", "extrinsic", "reality", "general")
        )

        # Re-domain a few obvious cases by content keywords
        text_lower = claim.lower()
        if any(k in text_lower for k in ("doctor", "patient", "trial", "rct", "drug", "medical", "vaccine", "clinical")):
            if domain == "general":
                domain = "medical"
        if any(k in text_lower for k in ("law", "court", "treaty", "statute", "supreme court")):
            if domain in ("general", "historical"):
                domain = "legal"

        cases.append({
            "id": f"{path.stem}-{tid}",
            "claim": claim.strip(),
            "is_hallucination": is_hall,
            "category": cat,
            "class": klass,
            "taxonomy": {
                "intrinsic_extrinsic": ie if is_hall else "n/a",
                "conflict_type": ct if is_hall else "n/a",
            },
            "domain": domain,
            "expected_verdict": _expected_verdict(is_hall, klass),
            "why": (why or "").strip(),
            "source_file": path.name,
        })
    return cases


# Net-new cases that explicitly target the article's gap list
# (Athaluri / Berberette / Sui / Ji / Zhang).
EXTRA_CASES: List[Dict] = [
    {
        "id": "extra-1",
        "claim": (
            "The 2017 paper 'Attention Is All You Need' (DOI: 10.48550/arXiv.1706.03762) "
            "proved that recurrent networks outperform Transformers on long-range dependencies."
        ),
        "is_hallucination": True,
        "category": "Citation-Content Mismatch",
        "class": "real_doi_wrong_claim",
        "taxonomy": {"intrinsic_extrinsic": "extrinsic", "conflict_type": "reality"},
        "domain": "scientific",
        "expected_verdict": "contradicted",
        "why": "Real DOI but the cited paper says the OPPOSITE — Transformers outperform RNNs.",
        "source_file": "extra",
    },
    {
        "id": "extra-2",
        "claim": (
            "A 2024 study at the MIT Department of Quantum Linguistics found that "
            "68.3% of LLM hallucinations are caused by token-level entropy collapse."
        ),
        "is_hallucination": True,
        "category": "Fabricated Institutions",
        "class": "fabricated_institution",
        "taxonomy": {"intrinsic_extrinsic": "extrinsic", "conflict_type": "reality"},
        "domain": "scientific",
        "expected_verdict": "unsupported",
        "why": "No such department exists at MIT (ROR check), fabricated stat.",
        "source_file": "extra",
    },
    {
        "id": "extra-3",
        "claim": (
            "According to the World Health Organization, 47.2% of global antibiotic "
            "prescriptions were unnecessary in 2023."
        ),
        "is_hallucination": True,
        "category": "Numerical Hallucination",
        "class": "numeric_hallucination",
        "taxonomy": {"intrinsic_extrinsic": "extrinsic", "conflict_type": "reality"},
        "domain": "medical",
        "expected_verdict": "unsupported",
        "why": "Precise statistic attributed to authority with no verifiable source.",
        "source_file": "extra",
    },
    {
        "id": "extra-4",
        "claim": "The Berlin Wall fell in 1989, marking the end of the Cold War division of Germany.",
        "is_hallucination": False,
        "category": "Factual Fabrication",
        "class": "factual_fabrication",
        "taxonomy": {"intrinsic_extrinsic": "n/a", "conflict_type": "n/a"},
        "domain": "historical",
        "expected_verdict": "supported",
        "why": "True historical fact (control case).",
        "source_file": "extra",
    },
    {
        "id": "extra-5",
        "claim": (
            "The Berlin Wall fell in 1989. Therefore, the Cold War officially ended in 1989, "
            "and as a direct consequence, the Soviet Union dissolved that same year, "
            "leading to Boris Yeltsin's election to the Russian presidency in 1989."
        ),
        "is_hallucination": True,
        "category": "Snowball",
        "class": "snowball",
        "taxonomy": {"intrinsic_extrinsic": "intrinsic", "conflict_type": "context"},
        "domain": "historical",
        "expected_verdict": "contradicted",
        "why": "Snowball: builds plausible-sounding but false cascade. USSR dissolved 1991, Yeltsin elected 1991.",
        "source_file": "extra",
    },
    {
        "id": "extra-6",
        "claim": (
            "Dr. Elena Vasquez at the Max Planck Institute for Quantum Bioinformatics (ROR: "
            "https://ror.org/01abcd234) has an h-index of 87 with 14,200 citations across 250 papers."
        ),
        "is_hallucination": True,
        "category": "Fabricated Metrics",
        "class": "fabricated_metric",
        "taxonomy": {"intrinsic_extrinsic": "extrinsic", "conflict_type": "reality"},
        "domain": "scientific",
        "expected_verdict": "unsupported",
        "why": "Fabricated institute, fabricated ROR, fabricated metrics.",
        "source_file": "extra",
    },
    {
        "id": "extra-7",
        "claim": "Tokyo is the capital of Japan.",
        "is_hallucination": False,
        "category": "Factual Fabrication",
        "class": "factual_fabrication",
        "taxonomy": {"intrinsic_extrinsic": "n/a", "conflict_type": "n/a"},
        "domain": "general",
        "expected_verdict": "supported",
        "why": "Control: well-known fact.",
        "source_file": "extra",
    },
    {
        "id": "extra-8",
        "claim": (
            "Hallucinations in generative AI models are produced through a process of stochastic "
            "decoding from a probabilistic language model."
        ),
        "is_hallucination": False,
        "category": "Confabulation",
        "class": "confabulation",
        "taxonomy": {"intrinsic_extrinsic": "n/a", "conflict_type": "n/a"},
        "domain": "scientific",
        "expected_verdict": "supported",
        "why": "True characterization of how hallucinations arise (Berberette 2024).",
        "source_file": "extra",
    },
]


def main() -> None:
    files = [
        ROOT / "test_academic_hallucinations.py",
        ROOT / "test_hallucination_taxonomy.py",
    ]
    all_cases: List[Dict] = []
    for f in files:
        if not f.exists():
            continue
        all_cases.extend(parse_test_file(f))
    all_cases.extend(EXTRA_CASES)

    # de-dupe by claim text
    seen = set()
    dedup: List[Dict] = []
    for c in all_cases:
        k = c["claim"].strip().lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(c)

    OUTPUT.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in dedup) + "\n", encoding="utf-8")
    print(f"Wrote {len(dedup)} cases to {OUTPUT}")
    # Print a brief class summary
    summary: Dict[str, int] = {}
    for c in dedup:
        summary[c["class"]] = summary.get(c["class"], 0) + 1
    for k in sorted(summary):
        print(f"  {k:30s} {summary[k]}")


if __name__ == "__main__":
    main()
