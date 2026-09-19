"""
Turn eval/corpus.db (real 2021-2025 papers) into labeled eval cases in the
existing cases.jsonl schema -> eval/cases_corpus.jsonl.

Per paper we emit, with PERFECT ground truth:
  - real_claim         : a true sentence from the abstract, no DOI.
                         is_hallucination=False -> engine must NOT flag it
                         (measures FALSE-POSITIVE / over-flagging rate).
  - fabricated_citation: that claim + a fake (valid-format, non-resolving) DOI.
                         is_hallucination=True  -> engine must flag it.
  - frankenstein_citation: that claim + a REAL DOI from an unrelated paper.
                         is_hallucination=True  -> engine must flag the mismatch.

Usage:
    CASES_N=40 .venv/bin/python eval/build_corpus_cases.py
"""
from __future__ import annotations
import json, os, random, re, sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "corpus.db"
OUT = HERE / "cases_corpus.jsonl"
N = int(os.environ.get("CASES_N", "40"))
random.seed(42)  # reproducible cases

FAKE_PREFIXES = ["10.1038", "10.1016", "10.1126", "10.1103", "10.1093",
                 "10.1021", "10.1007", "10.1111", "10.1073", "10.1145"]


# Sentences that announce the paper rather than assert a verifiable fact.
_ANNOUNCE_RE = re.compile(
    r"^\s*(this (article|paper|study|review|work|report|chapter)|here(,| we)|"
    r"in this (paper|article|study|work|review)|we (present|propose|develop|introduce|"
    r"describe|report|study|investigate|examine|explore|review|consider|aim)|"
    r"the (present|current|aim of|purpose of|objective of|goal of)|our (aim|goal|approach|work|study))",
    re.I,
)
# Markers of a concrete, externally-checkable finding.
_FACTUAL_RE = re.compile(
    r"(\bpercent\b|%|increas|decreas|reduc|higher|lower|associat|correlat|"
    r"signific|caus|\beffect|result(s|ed|ing)?\b|\brisk\b|\brate\b|ratio|compared|"
    r"than|greater|fewer|more likely|less likely|\bp\s*[<=]|95%|odds|hazard|fold|"
    r"improv|outperform|accuracy|prevalence|incidence|mortality|surviv)",
    re.I,
)


def first_claim(abstract: str) -> str | None:
    """Pick the most externally-verifiable factual sentence from an abstract.

    Skips meta/announcement sentences ("This article provides...", "We propose...")
    that the engine correctly refuses to fact-check, and prefers sentences that
    assert a concrete, checkable finding (numbers, comparisons, effects). Returns
    None when no such sentence exists (that paper is then skipped).
    """
    abstract = re.sub(r"\s+", " ", abstract).strip()
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", abstract)
    scored: list[tuple[int, int, str]] = []
    for pos, s in enumerate(sents):
        s = s.strip()
        wc = len(s.split())
        if not (10 <= wc <= 45) or not any(ch.isalpha() for ch in s):
            continue
        if _ANNOUNCE_RE.search(s):
            continue
        has_factual = bool(_FACTUAL_RE.search(s))
        has_digit = bool(re.search(r"\d", s))
        if not (has_factual or has_digit):
            continue
        score = (2 if has_factual else 0) + (1 if has_digit else 0)
        # results usually live past the lead sentence, not in the opener
        if pos >= len(sents) // 3:
            score += 1
        scored.append((score, pos, s))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], t[1]))
    return scored[0][2]


def fake_doi() -> str:
    pre = random.choice(FAKE_PREFIXES)
    suf = "".join(random.choice("0123456789abcdef") for _ in range(8))
    return f"{pre}/{pre.split('.')[1]}-2023-{suf}"


def case(cid, claim, is_hall, category, klass, expected, why, field):
    return {
        "id": cid, "claim": claim, "is_hallucination": is_hall,
        "category": category, "class": klass,
        "taxonomy": {"intrinsic_extrinsic": "extrinsic", "conflict_type": "reality"},
        "domain": "scientific", "expected_verdict": expected, "why": why,
        "field": field, "source_file": "corpus(openalex 2021-2025)",
    }


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT doi, title, field, abstract FROM papers ORDER BY cited_by DESC").fetchall()
    con.close()

    # build pool of real DOIs (for mismatch injection)
    real_dois = [(r[0], r[2]) for r in rows]

    cases = []
    used = 0
    for i, (doi, title, field, abstract) in enumerate(rows):
        if used >= N:
            break
        claim = first_claim(abstract)
        if not claim:
            continue
        used += 1
        base = f"corpus-{i}"
        # 1) real claim (control)
        cases.append(case(f"{base}-real", claim, False, "Real Claim", "genuine_claim",
                          "supported", "True statement from a real 2021-2025 paper abstract", field))
        # 2) fabricated DOI
        cases.append(case(f"{base}-fakedoi", f"{claim} (doi:{fake_doi()})", True,
                          "Fake DOI", "fabricated_citation", "unsupported",
                          "Real claim attached to a fabricated, non-resolving DOI", field))
        # 3) mismatched (frankenstein) citation — a real DOI from a different field
        other = random.choice([d for d, f in real_dois if f != field] or [d for d, _ in real_dois])
        cases.append(case(f"{base}-mismatch", f"{claim} (doi:{other})", True,
                          "Frankenstein Citation", "frankenstein_citation", "unsupported",
                          "Real claim attached to a real but unrelated DOI (citation mismatch)", field))

    OUT.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    by_class = {}
    for c in cases:
        by_class[c["class"]] = by_class.get(c["class"], 0) + 1
    print(f"wrote {len(cases)} cases from {used} papers -> {OUT}")
    for k, v in by_class.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
