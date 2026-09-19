from attest.chain import sha256_hex
from classroom.factcheck import CachedResolver, HttpResolver, extract_references, run_factcheck

from classroom_helpers import auth, capp, signup  # noqa: F401
from conftest import build_chain, typed

ESSAY = """Transformers replaced recurrence with attention (Vaswani et al., 2017). Later work scaled this up
(Brown et al., 2020; Kaplan & McCandlish, 2020) and Smith (2019) argued the opposite. A retracted
study claimed a 35% gain (DOI: 10.9999/fake.2021.12345). See https://doi.org/10.1038/nature14539 and
the dataset at https://example.org/data/set-1. A dead link: https://example.org/gone.

References
Vaswani, A. et al. 2017. Attention is all you need. NeurIPS. https://doi.org/10.48550/arXiv.1706.03762
Brown, T. et al. 2020. Language models are few-shot learners. NeurIPS.
LeCun, Y. 2015. Deep learning. Nature. 10.1038/nature14539.
"""


class FakeResolver:
    def __init__(self, dois=None, urls=None):
        self.dois, self.urls, self.calls = dois or {}, urls or {}, 0

    def doi(self, doi):
        self.calls += 1
        return self.dois.get(doi, {"status": "not_found", "detail": "fake: unknown"})

    def url(self, url):
        self.calls += 1
        return self.urls.get(url, {"status": "unreachable", "detail": "fake: no route"})


FAKE = FakeResolver(
    dois={
        "10.9999/fake.2021.12345": {"status": "invalid", "detail": "DOI prefix 10.9999 is not registered with any publisher"},
        "10.1038/nature14539": {"status": "valid", "detail": "found in Crossref",
                                "metadata": {"title": "Deep learning", "authors": ["LeCun, Yann", "Bengio, Yoshua"], "year": 2015, "venue": "Nature"}},
        "10.48550/arxiv.1706.03762": {"status": "valid", "detail": "resolves at doi.org (registered outside Crossref)", "metadata": None},
    },
    urls={
        "https://example.org/data/set-1": {"status": "valid", "detail": "HTTP 200"},
        "https://example.org/gone": {"status": "not_found", "detail": "HTTP 404"},
    },
)


def test_extraction():
    ex = extract_references(ESSAY)
    assert ex["dois"] == ["10.9999/fake.2021.12345", "10.1038/nature14539", "10.48550/arxiv.1706.03762"]
    assert ex["urls"] == ["https://example.org/data/set-1", "https://example.org/gone"]  # doi.org URLs folded into DOIs
    cites = {(c["surname"], c["year"]) for c in ex["author_year"]}
    assert cites == {("Vaswani", "2017"), ("Brown", "2020"), ("Kaplan", "2020"), ("Smith", "2019")}
    assert ex["has_reference_list"] and [e["surname"] for e in ex["entries"]] == ["Vaswani", "Brown", "LeCun"]
    assert ex["entries"][0]["doi"] == "10.48550/arxiv.1706.03762" and ex["entries"][2]["doi"] == "10.1038/nature14539"
    by = {c["surname"]: c for c in ex["author_year"]}
    assert by["Vaswani"]["matched_entry"] == 1 and by["Brown"]["matched_entry"] == 2
    assert by["Smith"]["matched_entry"] is None and by["Kaplan"]["matched_entry"] is None
    assert [e["cited"] for e in ex["entries"]] == [True, True, False]  # LeCun listed but never cited in-text


def test_run_with_fake_resolver_counts_and_pairs():
    fake = FakeResolver(FAKE.dois, FAKE.urls)
    res = run_factcheck(ESSAY, fake)
    s = res["summary"]
    assert s["total"] == 3 + 2 + 4 and s["valid"] == 3 and s["invalid"] == 1 and s["not_found"] == 1
    assert s["unverifiable"] == 4 and s["orphan_cites"] == 2 and s["uncited_entries"] == 1
    assert fake.calls == 5
    statuses = {r["raw"]: r["status"] for r in res["references"] if r["kind"] != "author_year"}
    assert statuses["10.9999/fake.2021.12345"] == "invalid" and statuses["https://example.org/gone"] == "not_found"
    nature = next(r for r in res["references"] if r["raw"] == "10.1038/nature14539")
    assert nature["metadata"]["title"] == "Deep learning" and nature["flags"] == []
    smith = next(r for r in res["references"] if r["kind"] == "author_year" and "Smith" in r["raw"])
    assert smith["status"] == "unverifiable" and "orphan" in smith["flags"]
    vas = next(r for r in res["references"] if r["kind"] == "author_year" and "Vaswani" in r["raw"])
    assert vas["matched_entry"] == 1 and "DOI 10.48550/arxiv.1706.03762" in vas["detail"]


def test_year_mismatch_flag():
    fake = FakeResolver(dois={"10.1000/x": {"status": "valid", "detail": "", "metadata": {"title": "T", "authors": ["Doe, J"], "year": 2015, "venue": "V"}}})
    res = run_factcheck("As Doe (2021) showed (DOI 10.1000/x).", fake)
    ref = next(r for r in res["references"] if r["kind"] == "doi")
    assert ref["flags"] == ["year_mismatch: cited 2021, published 2015"] and res["summary"]["flags"] == 1


def test_no_reference_list_is_not_orphan():
    res = run_factcheck("Smith (2019) said so.", FakeResolver())
    ref = res["references"][0]
    assert ref["status"] == "unverifiable" and ref["flags"] == [] and "no reference list" in ref["detail"]


def test_cached_resolver_hits_once(capp):
    fake = FakeResolver(FAKE.dois, FAKE.urls)
    cached = CachedResolver(fake, capp.app.state.db)
    assert cached.doi("10.1038/nature14539")["status"] == "valid"
    assert cached.doi("10.1038/nature14539")["status"] == "valid"
    assert fake.calls == 1
    cached2 = CachedResolver(FakeResolver(), capp.app.state.db)  # fresh process, warm DB cache
    assert cached2.doi("10.1038/nature14539")["metadata"]["title"] == "Deep learning"
    # transient failures are not cached
    cached2.url("https://example.org/flaky")
    cached2.url("https://example.org/flaky")
    assert cached2.inner.calls == 2


def test_http_resolver_unreachable_never_raises(monkeypatch):
    r = HttpResolver(timeout_s=0.5)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("no network")))
    assert r.doi("10.1038/nature14539")["status"] == "unreachable"
    assert r.url("https://example.org")["status"] == "unreachable"


def test_submit_triggers_factcheck_and_teacher_can_rerun(capp):
    capp.app.state.resolver = FakeResolver(FAKE.dois, FAKE.urls)
    t = signup(capp, "prof@demo.edu", "teacher")
    klass = capp.post("/api/classes", json={"name": "W"}, headers=auth(t["token"])).json()
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "E"}, headers=auth(t["token"])).json()
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    sub = capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).json()
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    text = "See https://example.org/gone and DOI 10.9999/fake.2021.12345."
    events = build_chain(led["genesis"], [{"ts": 1_700_000_000_000, "p": 0, "d": 0, "i": text, "k": "paste"}])
    capp.post("/v1/ingest", headers=auth(s["token"]), json={"session_id": led["session_id"], "events": events,
                                                             "content_sha256": sha256_hex(text), "content_len": len(text)})
    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                  json={"session_id": led["session_id"], "text": text})
    assert r.status_code == 200

    fc = capp.get(f"/api/factcheck/submissions/{sub['submission_id']}", headers=auth(t["token"])).json()
    assert fc["status"] == "done" and fc["result"]["summary"] == {
        "total": 2, "valid": 0, "not_found": 1, "invalid": 1, "unreachable": 0, "unverifiable": 0,
        "orphan_cites": 0, "uncited_entries": 0, "entries": 0, "flags": 0}
    table = capp.get(f"/api/assignments/{a['assignment_id']}/submissions", headers=auth(t["token"])).json()
    assert table[0]["factcheck_summary"]["invalid"] == 1 and table[0]["factcheck_status"] == "done"

    assert capp.post(f"/api/factcheck/submissions/{sub['submission_id']}/run", headers=auth(s["token"])).status_code == 403
    assert capp.post(f"/api/factcheck/submissions/{sub['submission_id']}/run", headers=auth(t["token"])).json()["status"] == "pending"
    assert capp.get(f"/api/factcheck/submissions/{sub['submission_id']}", headers=auth(s["token"])).json()["status"] == "done"
