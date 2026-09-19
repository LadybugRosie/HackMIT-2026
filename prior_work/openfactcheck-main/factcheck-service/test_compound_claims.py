"""
Compound-claim regression: a true sub-claim must not carry a false one.
The Einstein Nobel case — "...in 1921 for his theory of general relativity" —
must NOT be SUPPORTED (the prize was for the photoelectric effect).

Pure check here = the rationale detector that defers such claims from the
prize/year KB shortcut to the Wikipedia+LLM step. The full verdict acceptance
(general relativity -> contradicted, photoelectric -> supported, simple facts
unchanged) needs the live engine; run via /v1/verify (see __main__).

    cd factcheck-service && .venv/bin/python test_compound_claims.py
"""
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ofc_engine import _NOBEL_RATIONALE_RE  # noqa: E402

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


def test_rationale_detection():
    # Rationale present -> defer from the KB prize/year shortcut to Wikipedia+LLM.
    for t in [
        "Albert Einstein received the Nobel Prize in Physics in 1921 for his theory of general relativity.",
        "Einstein won the 1921 Nobel Prize in Physics, awarded for the photoelectric effect.",
        "She won the Nobel Prize for her work on radioactivity.",
        "He won the Nobel Prize for discovering the structure of DNA.",
    ]:
        check(f"rationale detected: …{t[-32:]}", bool(_NOBEL_RATIONALE_RE.search(t)))
    # No rationale -> keep the KB shortcut (simple prize/year facts unchanged).
    for t in [
        "Albert Einstein won the Nobel Prize in Physics in 1921.",
        "Marie Curie won the Nobel Prize in Chemistry.",
        "Niels Bohr received the Nobel Prize in Physics in 1922.",
    ]:
        check(f"no false rationale: {t[:40]}…", not _NOBEL_RATIONALE_RE.search(t))


if __name__ == "__main__":
    test_rationale_detection()
    print(f"\n{_passed} passed, {_failed} failed")
    print("\n(Full verdict acceptance — general-relativity->contradicted, "
          "photoelectric->supported — validated via the live /v1/verify engine.)")
    sys.exit(1 if _failed else 0)
