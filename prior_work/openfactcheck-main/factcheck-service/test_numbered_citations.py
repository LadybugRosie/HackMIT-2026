"""
Unit tests for numbered-citation parsing + Citation Support Matrix rollup.

These are pure (no network / no LLM): they exercise the reference-list parser,
the in-text marker extractor, and build_citation_matrix's verdict rollup.

Run directly (repo convention — no pytest dependency):
    .venv/bin/python test_numbered_citations.py
"""
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("OPENAI_API_KEY", "")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.numbered_citations import (  # noqa: E402
    ReferenceEntry,
    build_citation_matrix,
    extract_marker_citations,
    parse_reference_list,
)


def _supers(text, valid):
    """All numbers detected as superscript citation markers."""
    nums = set()
    for m in extract_marker_citations(text, valid_numbers=set(valid)):
        nums |= set(m.numbers)
    return nums

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


IEEE_DOC = """Transformer models outperform all CNN-based methods in medical imaging [14].
Recent work has explored attention mechanisms broadly [2]-[5]. Several studies
also report gains [1, 3, 7] across benchmarks. Earlier surveys [8]–[9] disagree.

References
[1] A. Vaswani et al., "Attention Is All You Need," in Proc. NeurIPS, 2017. doi:10.5555/3295222.3295349
[2] K. He et al., "Deep Residual Learning for Image Recognition," in Proc. CVPR, 2016.
[3] J. Devlin et al., "BERT: Pre-training of Deep Bidirectional Transformers," 2019, arXiv:1810.04805.
[7] Y. LeCun et al., "Gradient-Based Learning Applied to Document Recognition," 1998.
[14] X. Author, "A Convolutional Approach to Chest X-ray Classification," in Proc. MICCAI, 2020. https://doi.org/10.1000/cnn.2020.001
"""


def test_parse_reference_list():
    refs = parse_reference_list(IEEE_DOC)
    check("parses 5 bracket entries", set(refs.keys()) == {1, 2, 3, 7, 14})
    check("entry 1 title parsed", refs[1].title == "Attention Is All You Need")
    check("entry 1 doi parsed", refs[1].doi == "10.5555/3295222.3295349")
    check("entry 1 year parsed", refs[1].year == 2017)
    check("entry 1 authors parsed", "Vaswani" in refs[1].authors)
    check("entry 3 arxiv parsed", refs[3].arxiv_id == "1810.04805")
    check("entry 14 doi parsed", refs[14].doi == "10.1000/cnn.2020.001")


def test_marker_extraction():
    body = IEEE_DOC.split("References")[0]
    mentions = extract_marker_citations(body)
    all_numbers = sorted({n for m in mentions for n in m.numbers})
    check("single marker [14] found", 14 in all_numbers)
    check("range [2]-[5] expanded", {2, 3, 4, 5}.issubset(set(all_numbers)))
    check("list [1, 3, 7] expanded", {1, 3, 7}.issubset(set(all_numbers)))
    check("cross-bracket [8]–[9] expanded", {8, 9}.issubset(set(all_numbers)))
    # The sentence containing [14] should carry the claim text.
    s14 = next(m.sentence for m in mentions if 14 in m.numbers)
    check("[14] sentence carries claim", "outperform all CNN" in s14)


def test_matrix_rollup():
    refs = {
        1: ReferenceEntry(number=1, raw="...", doi="10.1/a", title="Attention Is All You Need"),
        14: ReferenceEntry(number=14, raw="...", doi="10.2/cnn", title="A CNN Approach"),
        19: ReferenceEntry(number=19, raw="...", doi="10.3/missing", title="Ghost Paper"),
    }
    alignments = [
        {"cited_number": 1, "support": "supported", "confidence": 90,
         "source_title": "Attention Is All You Need", "is_retracted": False, "notes": None},
        {"cited_number": 14, "support": "overstated", "confidence": 70,
         "source_title": "A CNN Approach", "is_retracted": False,
         "notes": "Claim generalises beyond the source."},
    ]
    doi_status = {
        "10.1/a": {"status": "valid", "title": "Attention Is All You Need", "year": 2017},
        "10.2/cnn": {"status": "valid", "title": "A CNN Approach", "year": 2020},
        "10.3/missing": {"status": "not_found", "title": None, "year": None},
    }
    rows = build_citation_matrix(refs, alignments, doi_status, cited_numbers={1, 14})
    by_num = {r["number"]: r for r in rows}
    check("matrix has rows for 1, 14, 19", set(by_num.keys()) == {1, 14, 19})
    check("ref 1 verdict supported", by_num[1]["verdict"] == "supported")
    check("ref 1 metadata_match true", by_num[1]["metadata_match"] is True)
    check("ref 14 verdict overstated", by_num[14]["verdict"] == "overstated")
    check("ref 14 supports_claim overstated", by_num[14]["supports_claim"] == "overstated")
    check("ref 19 verdict not_found", by_num[19]["verdict"] == "not_found")
    check("ref 19 used_correctly None (uncited)", by_num[19]["used_correctly"] is None)


def test_matrix_contradiction_beats_doi():
    refs = {5: ReferenceEntry(number=5, raw="...", doi="10.9/x", title="Some Paper")}
    alignments = [{"cited_number": 5, "support": "contradicted", "confidence": 80,
                   "source_title": "Some Paper", "is_retracted": False, "notes": "Opposite."}]
    doi_status = {"10.9/x": {"status": "valid", "title": "Some Paper", "year": 2020}}
    rows = build_citation_matrix(refs, alignments, doi_status, cited_numbers={5})
    check("contradicted wins over valid DOI", rows[0]["verdict"] == "contradicted")


def test_no_references_returns_empty():
    refs = parse_reference_list("Just a plain paragraph with no reference list at all.")
    check("no refs -> empty dict", refs == {})


def test_superscript_true_positives():
    valid = range(1, 30)
    check("glued single 'entropy3.'", 3 in _supers("Semantic entropy3.", valid))
    check("glued comma-list 'models1,2'", {1, 2} <= _supers("transformer models1,2 excel.", valid))
    check("glued range 'datasets9-11'", {9, 10, 11} <= _supers("across datasets9-11 broadly.", valid))


def test_superscript_false_positives_rejected():
    valid = range(1, 60)  # wide range so rejection is by denylist/format, not number range
    check("GPT4 not a marker", 4 not in _supers("We used GPT4 for inference.", valid))
    check("CO2 not a marker", 2 not in _supers("emissions of CO2 rose.", valid))
    check("ResNet50 not a marker", 50 not in _supers("a ResNet50 backbone.", valid))
    check("Table3 not a marker", 3 not in _supers("as shown in Table3 below.", valid))
    check("H2O not a marker (digit mid-word)", 2 not in _supers("a drop of H2O here.", valid))
    check("year with space not a marker", 2023 not in _supers("published in 2023 widely.", valid))
    check("number out of ref range rejected", 99 not in _supers("the value reached99 today.", range(1, 10)))


def test_superscript_off_without_reference_list():
    # No valid_numbers -> superscript detection disabled entirely.
    check("no valid_numbers -> no superscript", _supers("models1,2 are strong.", []) == set())


def test_superscript_gated_by_enable_flag():
    # Regression: a bracket-style paper (enable_superscript=False) must NOT read
    # glued digits as citations, even per-sentence.
    off = set()
    for m in extract_marker_citations("Models1 perform well across tasks.", valid_numbers={1, 2, 3}, enable_superscript=False):
        off |= set(m.numbers)
    check("enable_superscript=False -> no marker", off == set())
    on = set()
    for m in extract_marker_citations("transformer models1,2 excel.", valid_numbers={1, 2}, enable_superscript=True):
        on |= set(m.numbers)
    check("enable_superscript=True -> Nature superscript detected", {1, 2} <= on)


if __name__ == "__main__":
    for fn in (
        test_parse_reference_list,
        test_marker_extraction,
        test_matrix_rollup,
        test_matrix_contradiction_beats_doi,
        test_no_references_returns_empty,
        test_superscript_true_positives,
        test_superscript_false_positives_rejected,
        test_superscript_off_without_reference_list,
        test_superscript_gated_by_enable_flag,
    ):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
