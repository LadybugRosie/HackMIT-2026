"""
Published-paper-format citation-integrity eval cases -> eval/pp_cases.jsonl.

The general-mode eval appends "(doi:X)" inline, which the claim extractor drops
(no real paper cites that way). THIS harness builds a real mini-paper per case:
an in-text [1] marker citing a reference list, and runs it through
mode="published_paper" so the Citation Support Matrix (resolve source -> check
support) is actually exercised.

Per corpus paper P we emit, with perfect ground truth:
  - pp_genuine     : claim from P, [1] cites P itself (real DOI). Source supports
                     the claim -> must NOT be flagged (false-positive control).
  - pp_fabricated  : claim from P, [1] cites P's title with a FAKE, non-resolving
                     DOI -> the DOI check must flag not_found/invalid.
  - pp_frankenstein: claim from P, [1] cites a real but UNRELATED paper Q -> the
                     source does not support the claim -> must flag the mismatch
                     (support = unrelated/contradicted/overstated).

Usage:
    PP_N=20 .venv/bin/python eval/build_pp_cases.py
"""
from __future__ import annotations
import importlib.util
import json
import os
import random
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "corpus.db"
OUT = HERE / "pp_cases.jsonl"
N = int(os.environ.get("PP_N", "20"))
random.seed(7)

# Reuse the (improved) claim selector + fake-DOI generator.
_spec = importlib.util.spec_from_file_location("bcc", HERE / "build_corpus_cases.py")
bcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bcc)


def _ref(n: int, title: str, year, doi: str) -> str:
    yr = f" ({year})" if year else ""
    return f"[{n}] {title}.{yr} https://doi.org/{doi}"


def _paper(claim: str, ref_line: str) -> str:
    return (
        "Introduction\n\n"
        "Prior work has established relevant background for this area of study. "
        f"{claim} [1].\n\n"
        "References\n"
        f"{ref_line}\n"
    )


def main() -> None:
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT doi, title, year, field, abstract FROM papers "
        "WHERE abstract != '' AND doi != '' ORDER BY cited_by DESC"
    ).fetchall()
    con.close()

    cases = []
    used = 0
    for i, (doi, title, year, field, abstract) in enumerate(rows):
        if used >= N:
            break
        claim = bcc.first_claim(abstract)
        if not claim or not title or not doi:
            continue
        used += 1
        # 1) genuine — cite the paper itself (matching, real DOI)
        cases.append({
            "id": f"pp{i}-genuine", "class": "pp_genuine", "is_hallucination": False,
            "expected": "supported", "field": field,
            "text": _paper(claim, _ref(1, title, year, doi)),
        })
        # 2) fabricated — real title, FAKE non-resolving DOI
        cases.append({
            "id": f"pp{i}-fabdoi", "class": "pp_fabricated", "is_hallucination": True,
            "expected": "not_found", "field": field,
            "text": _paper(claim, _ref(1, title, year, bcc.fake_doi())),
        })
        # 3) frankenstein — cite a real but UNRELATED paper (different field)
        others = [r for r in rows if r[3] != field and r[0] and r[1]] or rows
        oj = random.choice(others)  # (doi, title, year, field, abstract)
        cases.append({
            "id": f"pp{i}-franken", "class": "pp_frankenstein", "is_hallucination": True,
            "expected": "unrelated", "field": field,
            "text": _paper(claim, _ref(1, oj[1], oj[2], oj[0])),
        })

    OUT.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    by = {}
    for c in cases:
        by[c["class"]] = by.get(c["class"], 0) + 1
    print(f"wrote {len(cases)} published-paper cases from {used} papers -> {OUT}")
    for k, v in by.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
