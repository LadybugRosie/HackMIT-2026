"""
Unit tests for the ADDITIVE internal numeric-consistency pass.

Pure — no network/LLM. Covers the two deterministic halves:
  - _candidate_sentences: precision of the figure-bearing prefilter (it must NOT
    grab prose, bare years, or numberless metric words).
  - _coerce: robust parsing of the LLM JSON (drops malformed / out-of-range /
    self-paired items; resolves indices back to snippets).

Run: cd factcheck-service && .venv/bin/python test_internal_consistency.py
"""
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.internal_consistency import _candidate_sentences, _coerce, _is_delta  # noqa: E402

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


def test_candidate_prefilter():
    text = (
        "We propose a sampling-based hallucination detector. "
        "Our method achieves 98.7% accuracy on the benchmark. "
        "The study ran from 2019 to 2021 across many labs. "
        "On the same test set the model reaches 94.2% accuracy. "
        "We report an F1 of 0.83 for the detector. "
        "This approach needs no external database."
    )
    cands = _candidate_sentences(text)
    joined = " || ".join(cands)
    check("keeps '98.7% accuracy' sentence", any("98.7%" in c for c in cands))
    check("keeps '94.2% accuracy' sentence", any("94.2%" in c for c in cands))
    check("keeps 'F1 of 0.83' sentence", any("F1 of 0.83" in c for c in cands))
    check("drops numberless prose (we propose)", "we propose" not in joined.lower())
    check("drops numberless prose (no external database)", "external database" not in joined.lower())
    check("drops bare-year sentence (no metric cue)", "2019 to 2021" not in joined)


def test_candidate_dedup_and_bounds():
    dup = "Accuracy was 90.0% on the dev set. Accuracy was 90.0% on the dev set."
    check("dedups identical figure sentences", len(_candidate_sentences(dup)) == 1)
    check("empty text -> no candidates", _candidate_sentences("") == [])
    check("too-few-figures text -> <2 candidates", len(_candidate_sentences("We achieve 50% recall.")) < 2)


def test_coerce_resolves_indices():
    cands = ["Abstract reports 98.7% accuracy.", "Table 2 lists 94.2% accuracy."]
    raw = (
        '{"mismatches":[{"metric":"accuracy","value_a":"98.7%","value_b":"94.2%",'
        '"sentence_a":0,"sentence_b":1,"note":"same metric, different value"}]}'
    )
    out = _coerce(raw, cands)
    check("one finding coerced", len(out) == 1)
    check("snippet_a resolved from index", out[0]["snippet_a"] == cands[0])
    check("snippet_b resolved from index", out[0]["snippet_b"] == cands[1])
    check("verdict is internal_mismatch", out[0]["verdict"] == "internal_mismatch")
    check("metric carried", out[0]["metric"] == "accuracy")


def test_coerce_drops_bad_items():
    cands = ["Abstract reports 98.7% accuracy.", "Table 2 lists 94.2% accuracy."]
    check("malformed JSON -> []", _coerce("not json at all", cands) == [])
    check("empty mismatches -> []", _coerce('{"mismatches":[]}', cands) == [])
    # out-of-range index dropped
    check(
        "out-of-range index dropped",
        _coerce('{"mismatches":[{"sentence_a":0,"sentence_b":9}]}', cands) == [],
    )
    # self-paired (same index) dropped
    check(
        "self-paired indices dropped",
        _coerce('{"mismatches":[{"sentence_a":1,"sentence_b":1}]}', cands) == [],
    )
    # fenced JSON still parses
    fenced = '```json\n{"mismatches":[{"sentence_a":0,"sentence_b":1}]}\n```'
    check("fenced JSON parses", len(_coerce(fenced, cands)) == 1)


def test_delta_backstop():
    # The real CoVe false positive: 0.17 (baseline) and 0.36 (CoVe) co-occur in
    # one "from X to Y" sentence -> a delta, NOT a contradiction -> dropped.
    cands = [
        "CoVe doubles the precision from the Llama 65B few-shot baseline on Wikidata (from 0.17 to 0.36).",
        "We also report results on MultiSpanQA.",
    ]
    finding = {"value_a": "0.17", "value_b": "0.36"}
    check("baseline->method delta dropped (CoVe FP)", _is_delta(finding, cands) is True)
    # A genuine cross-location pair (values in DIFFERENT sentences) is NOT a delta.
    cands2 = ["The abstract reports 98.7% accuracy.", "Table 2 reports 94.2% accuracy."]
    check("cross-location pair kept (not a delta)", _is_delta({"value_a": "98.7%", "value_b": "94.2%"}, cands2) is False)
    check("missing value -> not a delta", _is_delta({"value_a": "", "value_b": "0.36"}, cands) is False)


if __name__ == "__main__":
    for fn in (
        test_candidate_prefilter,
        test_candidate_dedup_and_bounds,
        test_coerce_resolves_indices,
        test_coerce_drops_bad_items,
        test_delta_backstop,
    ):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
