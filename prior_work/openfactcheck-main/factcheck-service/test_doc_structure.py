"""
Unit tests for document-structure parsing (Published Paper Audit Milestone 2):
URL repair, zone segmentation (references + table/figure exclusion), and
reference parsing on a Nature-style snippet. Pure — no network/LLM.

Run: cd factcheck-service && .venv/bin/python test_doc_structure.py
"""
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.doc_structure import repair_wrapped_urls, segment_zones, verifiable_body, is_pdf_fragment, is_table_row  # noqa: E402
from app.numbered_citations import parse_reference_list  # noqa: E402
from app.ref_integrity import extract_urls  # noqa: E402

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


NATURE_DOC = """We introduce semantic entropy to detect confabulations in large language models. Our method computes uncertainty over meanings rather than exact word sequences, and we evaluate it on TriviaQA, SQuAD, BioASQ and NQ-Open.

Table 1 | Examples of generated answers from LLaMA 2 Chat.
Refineries, process chemical, power generation, mills and manufacturing plants are under the industrial sector of construction.

Semantic entropy outperforms baselines across datasets.

References
1. Kuhn, L., Gal, Y. & Farquhar, S. Semantic uncertainty: linguistic invariances for uncertainty estimation. Preprint at https://arxiv.org/abs/
2302.09664 (2023).
2. Burns, K., Darrell, T. & Saenko, K. Discovering latent knowledge in language models. In Proc. 16th Conference on Empirical Methods (2022).
3. OpenAI. GPT-4 technical report. Preprint at https://arxiv.org/
abs/2303.08774 (2023).
4. The New York Times (8 Jun 2023).
"""


def test_url_repair():
    fixed = repair_wrapped_urls(NATURE_DOC)
    check("joins …/abs/<newline>id", "https://arxiv.org/abs/2302.09664" in fixed)
    check("joins …arxiv.org/<newline>abs/id", "https://arxiv.org/abs/2303.08774" in fixed)
    urls = extract_urls(fixed)
    check("extract_urls has no truncated …/abs/", "https://arxiv.org/abs/" not in urls)
    check("extract_urls returns full arXiv URL", "https://arxiv.org/abs/2302.09664" in urls)


def test_url_repair_does_not_merge_prose():
    # Complete URL ending a sentence, then a capitalized prose word — must NOT merge.
    t = "See the site https://example.com/page.\nThe results were strong."
    check("does not merge complete-URL + prose (period)", repair_wrapped_urls(t) == t)
    # Trailing slash but next token is capitalized prose — must NOT merge.
    t2 = "Visit https://example.com/\nThe homepage explains it."
    check("does not merge trailing-slash + Capitalized word", repair_wrapped_urls(t2) == t2)


def test_segmentation():
    s = segment_zones(repair_wrapped_urls(NATURE_DOC))
    body = s.body_text
    check("body keeps the intro author claim", "We introduce semantic entropy" in body)
    check("body keeps the results author claim", "outperforms baselines" in body)
    check("body EXCLUDES the Table 1 example", "Refineries, process chemical" not in body)
    check("body EXCLUDES reference fragments", "Burns" not in body and "New York Times" not in body)
    check("references_block captured", "Kuhn" in s.references_block)
    check("counted >=4 reference entries", s.reference_entry_count >= 4)
    check("counted the table block", s.excluded_block_count >= 1)


def test_reference_parsing_and_arxiv_urls():
    refs = parse_reference_list(NATURE_DOC)
    check("parsed all 4 numbered entries", set(refs.keys()) == {1, 2, 3, 4})
    check("entry 1 arXiv id from URL", refs[1].arxiv_id == "2302.09664")
    check("entry 3 arXiv id from wrapped URL", refs[3].arxiv_id == "2303.08774")


def test_plain_essay_unchanged():
    # No references / captions → body_text equals input (student-mode guard).
    essay = "The mitochondria is the powerhouse of the cell. Photosynthesis occurs in chloroplasts."
    check("plain essay body unchanged", verifiable_body(essay).strip() == essay.strip())


def test_header_footer_exclusion():
    doc = """arXiv:2303.08896v3 [cs.CL] 11 Oct 2023
Potsawee Manakul, Adian Liusie, Mark Gales
Department of Engineering, University of Cambridge
pm574@cam.ac.uk, al826@cam.ac.uk
Abstract
We propose SelfCheckGPT, a sampling-based hallucination detector.
The method works without external databases.
"""
    body = segment_zones(doc).body_text
    check("arXiv banner excluded", "2303.08896" not in body)
    check("author line excluded", "Potsawee Manakul" not in body)
    check("affiliation excluded", "Department of Engineering" not in body)
    check("email line excluded", "pm574@cam.ac.uk" not in body)
    check("abstract body kept", "we propose selfcheckgpt" in body.lower())
    check("method body kept", "without external databases" in body.lower())


def test_authorline_only_in_front_matter():
    # A body sentence that starts with surnames must NOT be dropped (it's past the
    # 12-line front-matter window / after Abstract).
    doc = "Abstract\n" + ("Filler sentence number {0} about the topic.\n".format(0)) \
        + "\n".join("Body filler line %d here." % i for i in range(14)) \
        + "\nSmith, Jones, and Lee, working independently, showed the effect in 2019."
    body = segment_zones(doc).body_text
    check("body sentence starting with surnames kept", "Smith, Jones, and Lee" in body)


def test_model_output_block_exclusion():
    doc = """We evaluate the prompts below.
Prompt: List the side effects of the drug.
Response: The drug causes drowsiness and nausea in most patients.

Our analysis covers three datasets.
"""
    body = segment_zones(doc).body_text
    check("model-output header excluded", "List the side effects" not in body)
    check("model-output response excluded", "drowsiness and nausea" not in body)
    check("real body after block kept", "three datasets" in body)


def test_pdf_fragment_filter():
    check("mostly-nonalpha fragment dropped", is_pdf_fragment("(3) ∑ p(i,j) ≤ θ , = 0.05 ± 0.1 // 12 34"))
    check("hyphen+dangling fragment dropped", is_pdf_fragment("ploy- ment of large models in clin"))
    check("real sentence kept", not is_pdf_fragment("SelfCheckGPT detects hallucinations without external resources."))
    check("state-of-the-art compound kept", not is_pdf_fragment("Our method reaches state-of-the-art accuracy on the benchmark."))
    # Regression: a stat-dense but properly-terminated sentence is NOT a fragment.
    check("stat sentence with % kept", not is_pdf_fragment("GDP grew by 3.2% in Q4 2020 versus 2019 levels."))


def test_header_less_refs_not_body_list():
    # Regression: a numbered first-person contributions list must NOT be taken as
    # the references section (it has no 'References' header).
    intro = "Introduction paragraph motivating the work and its broad context here.\n"
    filler = "\n".join("Body sentence number %d describing the approach in detail." % i for i in range(6))
    contrib = ("\n1. We improved accuracy on the 2020 benchmark significantly.\n"
               "2. We reduced latency on the 2021 dataset.\n"
               "3. We scaled to the 2022 corpus.\n"
               "4. We released code in 2023.\n"
               "5. We extended results in 2024.")
    s = segment_zones(intro + filler + contrib)
    check("first-person numbered list stays in body", "We improved accuracy" in s.body_text)
    check("not misclassified as references", s.reference_entry_count == 0)


def test_table_row_exclusion():
    check("survey table header is table row", is_table_row("Survey Date Pages Eval Improve Multimodal Contributions"))
    check("numeric column row is table row", is_table_row("BERT 92.5 88.1 90.3 0.91 76.2"))
    check("checkmark comparison row (even merged w/ prose)", is_table_row("However, inadequate coverage of approaches 03-Sept-2023 32✓ ✓ ✗"))
    check("real prose sentence not table row", not is_table_row("The survey covers many datasets and downstream tasks."))
    check("method sentence not table row", not is_table_row("We propose a sampling-based method for detection."))
    # line-level exclusion: a table header line is dropped from the body
    doc = "We study factuality methods in this paper.\nSurvey Date Pages Eval Improve Multimodal Contributions Year\nOur approach improves on prior work substantially."
    body = segment_zones(doc).body_text
    check("table header dropped from body", "Survey Date Pages" not in body)
    check("surrounding prose kept", "We study factuality" in body and "improves on prior work" in body)


def test_venue_banner_body_sentence_kept():
    # Regression: a body sentence starting "Proceedings of ..." (outside the
    # front-matter window) must be kept, with its citation marker intact.
    doc = ("Abstract\nWe study attention mechanisms.\n"
           "Proceedings of the 2017 workshop showed that attention beats recurrence in translation.\n"
           "We extend that result to longer sequences.")
    body = segment_zones(doc).body_text
    check("body 'Proceedings of...' sentence kept", "attention beats recurrence" in body)


if __name__ == "__main__":
    for fn in (
        test_url_repair,
        test_url_repair_does_not_merge_prose,
        test_segmentation,
        test_reference_parsing_and_arxiv_urls,
        test_plain_essay_unchanged,
        test_header_footer_exclusion,
        test_authorline_only_in_front_matter,
        test_model_output_block_exclusion,
        test_pdf_fragment_filter,
        test_header_less_refs_not_body_list,
        test_table_row_exclusion,
        test_venue_banner_body_sentence_kept,
    ):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
