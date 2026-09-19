"""
Offline regression tests for the engine-correctness pass (no network, no LLM).

Covers the deterministic bugs that produced wrong verdicts:
  1. quoted sentences were dropped by the extractor ("no valid claims")
  2. the knowledge base substring-matched and vouched for false sentences
  3. transient registry timeouts were reported as "DOI not found"
  4. venue phrases with "of the" were never extracted; lookup errors were flags
  5. institution containment ("Bell Labs" in "Nokia Bell Labs") was a flag
  6. citation-bearing sentences were decomposed, orphaning their identifiers
  7. author-year / quoted-title citation extraction and venue mapping

Run: cd factcheck-service && .venv/bin/python test_engine_correctness.py
"""
import asyncio
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx  # noqa: E402

from app import cited_work as cw  # noqa: E402
from app import fabrication_detectors as fd  # noqa: E402
from app import ref_integrity as ri  # noqa: E402
from app.preprocessor import split_sentences  # noqa: E402
from app.source_fetcher import SourceAuthor, SourceRecord, title_similarity  # noqa: E402
import openfactcheck as kb  # noqa: E402

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


# ── 1. extractor keeps quoted sentences ─────────────────────────────────────
def test_extractor_quotes():
    q1 = "As Albert Einstein famously said, 'The definition of insanity is doing the same thing over and over and expecting different results.'"
    q2 = "Abraham Lincoln once said, “The problem with internet quotes is that you can't always depend on their accuracy.”"
    check("quoted sentence (straight quote) kept", split_sentences(q1) == [q1])
    check("quoted sentence (curly quote) kept", split_sentences(q2) == [q2])
    doi = "Female breast cancer has surpassed lung cancer as the most common cancer. (doi:10.1016/s0140-6736(21)00516-x)"
    check("claim with parenthesised DOI kept", split_sentences(doi) == [doi])


# ── 2. KB coverage guard ────────────────────────────────────────────────────
def test_kb_guard():
    bad = [
        "The 2017 'Attention Is All You Need' paper was partially retracted in 2023 after independent researchers discovered a critical mathematical error.",
        "Attention Is All You Need (Vaswani et al., 2017) was published in ICML 2017 and introduced the Transformer architecture.",
        "The 2017 paper 'Attention Is All You Need' (DOI: 10.48550/arXiv.1706.03762) proved that recurrent networks outperform Transformers.",
    ]
    for t in bad:
        check(f"KB silent on extended sentence: {t[:45]}…", kb._match_known_fact(t) is None)
    good = [
        ("Marie Curie won the Nobel Prize in Physics in 1903.", "supported"),
        ("Paris is the capital of France.", "supported"),
        ("Water boils at 100 degrees Celsius at standard atmospheric pressure.", "supported"),
        ("GPT stands for Generative Pre-trained Transformer.", "supported"),
        ("The Berlin Wall fell in 1989, marking the end of the Cold War division of Germany.", "supported"),
    ]
    for t, v in good:
        r = kb._match_known_fact(t)
        check(f"KB still matches atomic fact: {t[:40]}…", r is not None and r["verdict"] == v)
    myth = "Antibiotics are effective in treating influenza and other viral infections when administered within the first 48 hours."
    r = kb._match_known_fact(myth)
    check("KB myth still contradicts inside a longer sentence", r is not None and r["verdict"] == "contradicted")
    reported = "It is a common misconception that antibiotics are effective in treating influenza."
    check("KB stays silent when the myth is reported, not asserted", kb._match_known_fact(reported) is None)


# ── 3. DOI status: timeout is NOT "not found" ───────────────────────────────
class _Resp:
    def __init__(self, status, url):
        self.status_code = status
        self.url = url

    def json(self):
        return {}


class _FakeClient:
    """Scripted httpx client: maps URL substrings to responses / exceptions."""
    def __init__(self, script):
        self.script = script

    async def _do(self, url):
        for key, outcome in self.script.items():
            if key in url:
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise httpx.TimeoutException("no script")

    async def head(self, url, **kw):
        return await self._do(url)

    async def get(self, url, **kw):
        return await self._do(url)

    async def aclose(self):
        pass


def test_doi_status():
    doi = "10.1038/s41586-023-06472-9"
    timeouts = _FakeClient({
        "doi.org": httpx.TimeoutException("t"),
        "crossref": httpx.TimeoutException("t"),
        "datacite": httpx.TimeoutException("t"),
    })
    r = asyncio.run(ri.check_doi(doi, timeouts))
    check("all registries timed out -> TIMEOUT, not NOT_FOUND", r.status == ri.DOIStatus.TIMEOUT)

    definitive = _FakeClient({
        "doi.org": _Resp(404, "https://doi.org/" + doi),
        "crossref": _Resp(404, "https://api.crossref.org/works/" + doi),
        "datacite": _Resp(404, "https://api.datacite.org/dois/" + doi),
    })
    r = asyncio.run(ri.check_doi(doi, definitive))
    check("definitive 404s -> NOT_FOUND", r.status == ri.DOIStatus.NOT_FOUND)

    mixed = _FakeClient({
        "doi.org": _Resp(404, "https://doi.org/" + doi),
        "crossref": httpx.TimeoutException("t"),
        "datacite": _Resp(500, "https://api.datacite.org/dois/" + doi),
    })
    r = asyncio.run(ri.check_doi(doi, mixed))
    check("doi.org 404 alone is definitive -> NOT_FOUND", r.status == ri.DOIStatus.NOT_FOUND)

    resolves = _FakeClient({
        "doi.org": _Resp(403, "https://www.nature.com/articles/x"),   # publisher blocks HEAD
        "crossref": httpx.TimeoutException("t"),
        "datacite": _Resp(404, "https://api.datacite.org/dois/" + doi),
    })
    r = asyncio.run(ri.check_doi(doi, resolves))
    check("publisher 403 after doi.org redirect -> VALID (resolves)", r.status == ri.DOIStatus.VALID)


# ── 4. venue phrase extraction ──────────────────────────────────────────────
def test_venue_extraction():
    cases = {
        "Published in the Journal of the American Chemical Association (2023), the study demonstrated a pathway.":
            ["Journal of the American Chemical Association"],
        "Their findings were reported in IEEE Transactions on Neural Computation (Vol. 35, 2023), demonstrating performance.":
            ["IEEE Transactions on Neural Computation"],
        "The British Medical Journal of Medicine published a landmark study in early 2024.":
            ["British Medical Journal of Medicine"],
        "The results were published in the Proceedings of the National Academy of Science, showing a 45% reduction.":
            ["Proceedings of the National Academy of Science"],
        "Presented at the 14th ACL Workshop on Computational Approaches to Linguistic Code-Switching (CALCS 2023).": [],
        "The paper appeared in Nature (2023), the leading multidisciplinary science journal.": [],
        "The paper was presented at NeurIPS 2023 in New Orleans.": [],
    }
    for text, want in cases.items():
        got = fd.extract_venue_phrases(text)
        check(f"venue phrases {want} <- {text[:40]}…", got == want)


# ── 5. name similarity: containment + light stemming ────────────────────────
def test_name_similarity():
    check("'Bell Labs' ~ 'Nokia Bell Labs'", fd._name_similarity("Bell Labs", "Nokia Bell Labs") == 1.0)
    check("'Max Planck Institute' ~ 'Max Planck Institute for Intelligent Systems'",
          fd._name_similarity("Max Planck Institute", "Max Planck Institute for Intelligent Systems") == 1.0)
    check("Science ~ Sciences", title_similarity("Proceedings of the National Academy of Science",
                                                  "Proceedings of the National Academy of Sciences") == 1.0)
    check("'British Medical Journal of Medicine' !~ 'British Journal of Medicine and Medical Research'",
          fd._name_similarity("British Medical Journal of Medicine", "British Journal of Medicine and Medical Research") < 0.85)
    check("'MIT' does not vouch for 'MIT Department of Quantum Linguistics'",
          fd._name_similarity("MIT Department of Quantum Linguistics", "MIT") < 0.55)
    check("Association !~ Society",
          fd._name_similarity("Journal of the American Chemical Association",
                              "Journal of the American Chemical Society") < 0.85)


# ── 6. citation anchors are never decomposed ────────────────────────────────
def test_citation_anchor():
    anchored = [
        "Wang et al. (2024) showed in their paper (doi:10.1038/s42256-024-00891-3) that models achieve accuracy across 14 specialties.",
        "Zhang, Bengio & LeCun (arXiv:2312.14892) proposed 'Constitutional Alignment via Recursive Self-Improvement'.",
        "Attention Is All You Need (Vaswani et al., 2017) was published in ICML 2017 and introduced the Transformer.",
        "The full methodology is available at https://economics.mit.edu/files/working-papers/wp-2023-0847.pdf.",
    ]
    for t in anchored:
        check(f"anchor: {t[:50]}…", cw.has_citation_anchor(t))
    plain = [
        "Albert Einstein received the Nobel Prize in Physics in 1921 for his theory of general relativity.",
        "Python was created by Guido van Rossum and first released in 1991.",
        "As Albert Einstein famously said, 'The definition of insanity is doing the same thing over and over and expecting different results.'",
    ]
    for t in plain:
        check(f"no anchor: {t[:50]}…", not cw.has_citation_anchor(t))


# ── 7. author-year / title extraction, venue mapping, ghost logic ───────────
def test_cited_work_extraction():
    t = "Building on the framework established by Park & Williams (2022) in 'Causal Transformers for Time-Series Forecasting,' Kim et al. (2023) extended the approach."
    cites = cw.extract_author_year_cites(t)
    check("two author-year cites", [c["surnames"] for c in cites] == [["Park", "Williams"], ["Kim"]])
    check("quoted title extracted", [x["title"] for x in cw.extract_quoted_titles(t)] == ["Causal Transformers for Time-Series Forecasting"])
    t2 = "Attention Is All You Need (Vaswani et al., 2017) was published in ICML 2017 and introduced the Transformer architecture."
    c = cw.extract_author_year_cites(t2)[0]
    check("preceding title query", cw._preceding_title_query(t2, c["start"]) == "Attention Is All You Need")
    check("claimed venue icml", cw.claimed_venues(t2) == ["icml"])
    check("NIPS aliases to neurips", cw.claimed_venues("(Chen et al., NIPS 2018)") == ["neurips"])
    check("'Nature' as a word is not a venue claim", cw.claimed_venues("The nature of Science is debated.") == [])
    check("'in Nature' is a venue claim", cw.claimed_venues("The paper was published in Nature in 1953.") == ["nature"])
    check("venue_key NAACL", cw.venue_key("Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics") == "naacl")
    check("venue_key NeurIPS", cw.venue_key("Neural Information Processing Systems") == "neurips")
    check("venue_key arXiv -> None", cw.venue_key("arXiv (Cornell University)") is None)
    rec = SourceRecord(title="Attention Is All You Need",
                       authors=[SourceAuthor(name="Ashish Vaswani"), SourceAuthor(name="Noam Shazeer")])
    check("ghost: Vaswani matches", fd.ghost_author_flags(["Vaswani"], rec, "x") == [])
    check("ghost: Park flagged", [f.kind for f in fd.ghost_author_flags(["Park"], rec, "x")] == ["ghost_author"])
    check("no speech quotes as titles", cw.extract_quoted_titles(
        "Abraham Lincoln once said, 'The problem with internet quotes is that you can't always depend on their accuracy.'") == [])
    check("NIH grant regex", fd._NIH_GRANT_RE.search("NIH R01-GM123456").group(0) == "R01-GM123456")
    check("NSF grant regex", fd._NSF_GRANT_RE.search("NSF Grant IIS-2134567 and").group(1) == "2134567")


if __name__ == "__main__":
    for fn in (test_extractor_quotes, test_kb_guard, test_doi_status, test_venue_extraction,
               test_name_similarity, test_citation_anchor, test_cited_work_extraction):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
