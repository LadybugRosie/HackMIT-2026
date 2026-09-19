"""
Unit tests for citation-style detection, author-year citation/reference parsing,
mapping, equation detection, and zone classification (M3). Pure — no network/LLM.

Run: cd factcheck-service && .venv/bin/python test_citation_styles.py
"""
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.citation_styles import (  # noqa: E402
    detect_style,
    extract_author_year_citations,
    parse_author_year_references,
    map_author_year,
    lookup_ref,
    ay_key,
    AYRef,
    _entry_surname,
)
from app.doc_structure import classify_zone, is_equation_block, segment_zones  # noqa: E402

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


IEEE = "Transformers excel [1]. CNNs lag [2]. See [3]–[5] for surveys. Also [7]."
ACL = ("We build on prior work (Yuan et al., 2021; Fu et al., 2023). "
       "Brown et al. (2020) introduced few-shot learning. "
       "Hallucination is common (Ji et al., 2023).")


def test_detect_style():
    check("IEEE numeric detected", detect_style(IEEE) == "numeric")
    check("ACL author-year detected", detect_style(ACL) == "author_year")
    check("plain text -> none", detect_style("The sky is blue. Water boils.") == "none")


def test_author_year_citations():
    cites = extract_author_year_citations(ACL)
    keys = {c.key for c in cites}
    check("multi-cite split: Yuan 2021", ay_key("Yuan", "2021") in keys)
    check("multi-cite split: Fu 2023", ay_key("Fu", "2023") in keys)
    check("narrative: Brown 2020", ay_key("Brown", "2020") in keys)
    check("single: Ji 2023", ay_key("Ji", "2023") in keys)


ACL_REFS = """References
Tom B. Brown, Benjamin Mann, and Nick Ryder. 2020. Language models are few-shot learners. In Advances in Neural Information Processing Systems.
Yao Fu, Hao Peng, and Tushar Khot. 2023. Complexity-based prompting for multi-step reasoning. Preprint at https://arxiv.org/abs/2210.00720.
Ziwei Ji, Nayeon Lee, and Rita Frieske. 2023. Survey of hallucination in natural language generation. ACM Computing Surveys.
Weizhe Yuan, Graham Neubig, and Pengfei Liu. 2021. Bartscore: Evaluating generated text as text generation. In NeurIPS.
"""


def test_parse_author_year_references():
    block = segment_zones(ACL_REFS).references_block
    refs = parse_author_year_references(block)
    check("parsed 4 author-year refs", len(refs) == 4)
    check("key Brown:2020 present", ay_key("Brown", "2020") in refs)
    r = refs.get(ay_key("Brown", "2020"))
    check("Brown title parsed", bool(r and r.title and "few-shot" in r.title.lower()))
    fu = refs.get(ay_key("Fu", "2023"))
    check("Fu arXiv id from URL", bool(fu and fu.arxiv_id == "2210.00720"))


def test_entry_surname_first_author():
    # Regression: must key by FIRST author, not last (the bug that broke mapping).
    check("two-author natural -> Devlin", _entry_surname("Jacob Devlin and Ming-Wei Chang. 2019. BERT.") == "Devlin")
    check("'et al.' -> Devlin", _entry_surname("Devlin et al. 2019. BERT pretraining.") == "Devlin")
    check("APA surname-first -> Brown", _entry_surname("Brown, T. B., Mann, B. 2020. Language models.") == "Brown")
    check("comma natural -> Brown", _entry_surname("Tom B. Brown, Benjamin Mann. 2020. Language models.") == "Brown")
    check("'and' two-author -> Yuan", _entry_surname("Zhijing Yuan and Wei Liu. 2021. Metric.") == "Yuan")


def test_split_entries_wrapped_continuation():
    # Regression: a wrapped venue line must NOT start a phantom entry.
    block = ("Tom Brown and Nick Ryder. 2020. Language models. In Advances in Neural Information\n"
             "Processing Systems, volume 33.\n"
             "Jacob Devlin and Ming-Wei Chang. 2019. BERT pretraining of transformers.")
    refs = parse_author_year_references(block)
    keys = set(refs.keys())
    check("Brown 2020 parsed", ay_key("Brown", "2020") in keys)
    check("Devlin 2019 parsed (not merged into wrapped line)", ay_key("Devlin", "2019") in keys)
    check("no phantom 'systems' entry", ay_key("Systems", "2019") not in keys)


def test_venue_authors_populated():
    refs = parse_author_year_references(
        "Tom Brown and Nick Ryder. 2020. Language models are few-shot learners. In Advances in Neural Information Processing Systems.")
    r = refs.get(ay_key("Brown", "2020"))
    check("venue populated", bool(r and r.venue))
    check("authors populated", bool(r and r.authors))


def test_suffix_year_keys_and_lookup():
    check("ay_key keeps suffix", ay_key("Huang", "2023a") == "huang:2023a")
    check("ay_key 4-digit", ay_key("Brown", "2020") == "brown:2020")
    refs = {
        ay_key("Huang", "2023a"): AYRef(key="huang:2023a", surname="Huang", year="2023a", raw=""),
        ay_key("Huang", "2023b"): AYRef(key="huang:2023b", surname="Huang", year="2023b", raw=""),
        ay_key("Brown", "2020"): AYRef(key="brown:2020", surname="Brown", year="2020", raw=""),
    }
    check("exact suffix lookup", lookup_ref(refs, "huang:2023a").year == "2023a")
    check("suffixless cite -> suffixless ref", lookup_ref(refs, "brown:2020").year == "2020")
    check("ambiguous suffixless cite -> None", lookup_ref(refs, "huang:2023") is None)
    # cite with suffix not in refs falls back to suffixless prefix if unique
    refs2 = {ay_key("Wang", "2023"): AYRef(key="wang:2023", surname="Wang", year="2023", raw="")}
    check("suffix cite -> suffixless ref fallback", lookup_ref(refs2, "wang:2023b").year == "2023")


def test_mapping():
    refs = parse_author_year_references(segment_zones(ACL_REFS).references_block)
    cites = extract_author_year_citations(ACL)
    mapping = map_author_year(cites, refs)
    check("Yuan 2021 maps to a ref", mapping.get(ay_key("Yuan", "2021")) is not None)
    check("Brown 2020 maps to a ref", mapping.get(ay_key("Brown", "2020")) is not None)


def test_equation_detection():
    check("symbolic eq is equation", is_equation_block("p(j) = (1/N) ∑ s_i ≤ θ"))
    check("ascii eq is equation", is_equation_block("s(i) = (1/N) sum_j p(i,j) <= theta."))
    check("bare eq number is equation", is_equation_block("(3)"))
    check("method sentence not equation", not is_equation_block("In this work, we propose SelfCheckGPT."))
    check("stat sentence not equation", not is_equation_block("We set the threshold to 0.5 in experiments."))
    check("result sentence not equation", not is_equation_block("Our method achieves an AUC-PR of 92.50 on the dataset."))
    check("prose with f(x) not equation", not is_equation_block("The function f(x) = x squared is shown in the plot."))


def test_zone_classification():
    check("cited -> related work", classify_zone("Prior work shows X (Ji et al., 2023).", True) == "RELATED_WORK_CLAIM")
    check("we propose -> method", classify_zone("In this work, we propose SelfCheckGPT, a sampling approach.", False) == "METHOD_CLAIM")
    check("AUC result -> result", classify_zone("Our method achieves an AUC-PR of 92.50 on wikibio.", False) == "RESULT_CLAIM")
    check("plain -> author claim", classify_zone("Language models are widely deployed today.", False) == "AUTHOR_CLAIM")


def test_thirty_plus_refs_fixture():
    # 30 synthetic ACL entries -> parser should find >= 30 (item-9 target).
    surnames = ["Brown", "Devlin", "Vaswani", "Radford", "Lewis", "Raffel", "Liu", "Wang",
                "Chen", "Zhang", "Kumar", "Smith", "Jones", "Patel", "Garcia", "Khan",
                "Singh", "Cohen", "Nguyen", "Park", "Kim", "Lee", "Gupta", "Ahmed",
                "Rossi", "Muller", "Tanaka", "Silva", "Ivanov", "Yang"]
    lines = ["References"]
    for i, s in enumerate(surnames):
        yr = 2015 + (i % 9)
        # Natural ACL order: "Given Surname, Second Author, ... YEAR. Title. Venue."
        lines.append(f"Given {s}, Second Author, and Third One. {yr}. A study of method for tasks number {i}. In Proceedings of ACL.")
    block = segment_zones("\n".join(lines)).references_block
    refs = parse_author_year_references(block)
    check(f"parsed >=30 refs (got {len(refs)})", len(refs) >= 30)


if __name__ == "__main__":
    for fn in (
        test_detect_style,
        test_author_year_citations,
        test_parse_author_year_references,
        test_entry_surname_first_author,
        test_split_entries_wrapped_continuation,
        test_venue_authors_populated,
        test_suffix_year_keys_and_lookup,
        test_mapping,
        test_equation_detection,
        test_zone_classification,
        test_thirty_plus_refs_fixture,
    ):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
