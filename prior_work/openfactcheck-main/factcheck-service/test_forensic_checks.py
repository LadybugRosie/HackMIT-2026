"""
Forensic-integrity checks — detection AND zero-false-positive tests.

Pure (no network/LLM). Covers:
  - p-value functions accurate vs known values
  - statcheck: catches decision errors / inconsistencies; leaves CORRECT stats alone
  - GRIM: catches impossible %/means; leaves attainable ones (and continuous data) alone
  - dangling cross-refs: flags above-ceiling Table/Figure; leaves valid ones alone
  - retraction screening from a citation-matrix row

Run: cd factcheck-service && .venv/bin/python test_forensic_checks.py
"""
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.stats_pvalue import chi2_p, f_p, norm_p_two, r_p_two, t_p_two  # noqa: E402
from app.forensic_checks import (  # noqa: E402
    run_statcheck, run_grim, run_dangling_refs, retraction_findings,
)

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


def test_pvalues_accurate():
    for name, got, exp in [
        ("t(28)=2.10", t_p_two(2.10, 28), 0.04486),
        ("F(2,45)=3.5", f_p(3.5, 2, 45), 0.03866),
        ("chi2(1)=5.2", chi2_p(5.2, 1), 0.02259),
        ("r(38)=.42", r_p_two(0.42, 38), 0.00697),
        ("z=1.96", norm_p_two(1.96), 0.04999),
    ]:
        check(f"p-value {name}", abs(got - exp) < 5e-4)


def test_statcheck_catches_errors():
    # Decision error: reported significant but statistic implies ns.
    f = run_statcheck("The effect held, t(28) = 1.20, p = .04.")
    check("t decision error caught", any(x["severity"] == "error" for x in f))
    # ns but actually significant.
    f = run_statcheck("No effect was found, t(30) = 2.50, p = ns.")
    check("ns-but-significant caught", any(x["severity"] == "error" for x in f))
    # F decision error.
    f = run_statcheck("The interaction was reliable, F(2, 45) = 1.50, p = .03.")
    check("F decision error caught", any(x["check"] == "statcheck" for x in f))
    # p < .05 contradicted by a tiny statistic.
    f = run_statcheck("This was significant, t(28) = 0.50, p < .05.")
    check("p<.05 contradiction caught", any(x["check"] == "statcheck" for x in f))


def test_statcheck_zero_false_positive():
    # A block of CORRECT statistics must produce NO findings.
    correct = ("Results. t(28) = 2.10, p = .04. F(2, 45) = 3.50, p = .04. "
               "chi2(1) = 5.20, p = .02. r(38) = .42, p = .007. z = 1.96, p = .05.")
    f = run_statcheck(correct)
    check("zero findings on correct stats", len(f) == 0)
    # One-tailed report must be accepted (not flagged): t(28)=2.10 one-sided ≈ .022.
    f = run_statcheck("One-tailed, t(28) = 2.10, p = .02.")
    check("one-tailed p accepted", len(f) == 0)
    # No df → cannot recompute → no finding (conservative).
    check("t without df ignored", len(run_statcheck("t = 2.10, p = .03.")) == 0)


def test_grim_percent():
    check("impossible 63.4% of 30 flagged", len(run_grim("19/30 (63.4%) responded.")) == 1)
    check("attainable 63.3% of 30 not flagged", len(run_grim("19/30 (63.3%) responded.")) == 0)
    check("impossible 63.4% (n=30) flagged", len(run_grim("63.4% (n = 30) agreed.")) == 1)
    check("attainable 45.0% of 200 not flagged", len(run_grim("90 of 200 (45.0%) agreed.")) == 0)
    # Large N has no granularity power → never a false positive.
    check("large-N % not flagged", len(run_grim("63.4% (n = 5000) agreed.")) == 0)


def test_grim_mean_gated():
    # Integer-scale cue present + impossible mean → flagged.
    bad = "On a 1-7 Likert scale, the mean was M = 3.46 (N = 20)."
    check("impossible Likert mean flagged", len(run_grim(bad)) == 1)
    # Same numbers but NO scale cue → continuous data is possible → NOT flagged.
    cont = "Reaction time averaged M = 3.46 (N = 20) seconds."
    check("continuous mean not flagged (no scale cue)", len(run_grim(cont)) == 0)
    # Attainable Likert mean → not flagged.
    good = "On a 1-7 Likert scale, the mean was M = 3.45 (N = 20)."
    check("attainable Likert mean not flagged", len(run_grim(good)) == 0)


def test_dangling_refs():
    doc = ("We summarize the data.\n"
           "Table 1: baseline characteristics.\n"
           "Table 2: model accuracy.\n"
           "As shown in Table 1 and Table 2, results are strong. "
           "Full details appear in Table 5.\n")
    f = run_dangling_refs(doc)
    check("Table 5 above ceiling flagged", any(x["data"]["number"] == 5 for x in f))
    check("Table 1/2 (defined) not flagged", not any(x["data"]["number"] in (1, 2) for x in f))
    # Only one defined table → no trusted ceiling → no flag (avoids under-parse FP).
    doc2 = "Table 1: the only table. But see Table 9 for more."
    check("no ceiling with <2 defined → no flag", len(run_dangling_refs(doc2)) == 0)


def test_retraction_findings():
    rows = [
        {"citation": "[5]", "is_retracted": True, "note": "retracted 2021", "doi": "10.x/y", "claim_snippet": "as [5] showed"},
        {"citation": "[6]", "is_retracted": False},
    ]
    f = retraction_findings(rows)
    check("retracted citation flagged", len(f) == 1 and f[0]["severity"] == "error")
    check("non-retracted not flagged", all("[6]" not in (x["data"].get("citation") or "") for x in f))
    check("empty matrix → no findings", retraction_findings(None) == [])


if __name__ == "__main__":
    for fn in (
        test_pvalues_accurate,
        test_statcheck_catches_errors,
        test_statcheck_zero_false_positive,
        test_grim_percent,
        test_grim_mean_gated,
        test_dangling_refs,
        test_retraction_findings,
    ):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
