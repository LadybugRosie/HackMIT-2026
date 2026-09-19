import random

from hypothesis import given, settings as hsettings, strategies as st

from attest.chain import sha256_hex
from classroom.similarity import all_gram_hashes, compare, fingerprint, tokenize, winnow

from classroom_helpers import auth, capp, signup  # noqa: F401
from conftest import build_chain

K, W = 5, 4

PARA_A = ("The committee met on a grey Tuesday to decide whether the library should extend its evening "
          "hours, and after two hours of argument about budgets, staffing and the habits of students, "
          "it voted narrowly to keep the doors open until midnight during examination weeks.")
PARA_B = ("Volcanic soils are unusually fertile because weathering releases potassium and phosphorus, "
          "which is why vineyards cluster on old lava flows from Sicily to the Canary Islands despite the "
          "obvious risk of living beside a mountain that occasionally erupts.")
SHARED = ("Every measurement carries uncertainty, and the honest report states that uncertainty rather "
          "than hiding it behind a single confident number that readers will mistake for a fact.")


def words(rng, n):
    return " ".join(rng.choice(["alpha", "beta", "gamma", "delta", "omega", "kappa", "sigma", "theta", "iota", "zeta"]) for _ in range(n))


def test_tokenize_keeps_code_point_offsets():
    text = "Héllo 🙂 world's end."
    toks, spans = tokenize(text)
    assert toks == ["héllo", "world's", "end"]
    assert [text[s:e] for s, e in spans] == ["Héllo", "world's", "end"]


def test_winnow_picks_one_per_window_and_dedupes():
    assert winnow([], W) == []
    assert winnow([5, 3, 9], W) == [(3, 1)]
    picks = winnow([9, 8, 7, 6, 5, 4, 3, 2, 1], 3)
    assert picks == [(7, 2), (6, 3), (5, 4), (4, 5), (3, 6), (2, 7), (1, 8)]
    assert all(picks[i] != picks[i + 1] for i in range(len(picks) - 1))


def test_identical_and_unrelated():
    a, b = fingerprint(PARA_A, K, W), fingerprint(PARA_A, K, W)
    assert compare(a, b, K, PARA_A)["score"] == 100
    assert compare(fingerprint(PARA_A, K, W), fingerprint(PARA_B, K, W), K, PARA_A) is None


def test_shared_paragraph_is_found_with_exact_segment():
    essay_a = PARA_A + " " + SHARED + " " + PARA_B
    essay_b = PARA_B + " In short: " + SHARED
    m = compare(fingerprint(essay_a, K, W), fingerprint(essay_b, K, W), K, essay_a)
    assert m is not None and 20 <= m["score"] <= 80, m["score"]  # PARA_B and SHARED are both shared here
    seg = m["segments"][0]
    assert essay_a[seg["a_start"]:seg["a_end"]] == seg["text"]
    shared_seg = next(s for s in m["segments"] if "uncertainty" in s["text"])
    a_words, b_words = shared_seg["text"].split(), essay_b[shared_seg["b_start"]:shared_seg["b_end"]].split()
    assert a_words[:8] == b_words[:8]  # same passage located in B by code-point offsets


def test_prompt_grams_are_excluded():
    exclude = all_gram_hashes(SHARED, K)
    a = fingerprint(SHARED + " " + PARA_A, K, W, exclude=exclude)
    b = fingerprint(SHARED + " " + PARA_B, K, W, exclude=exclude)
    assert compare(a, b, K, SHARED + " " + PARA_A) is None  # only the quoted prompt overlapped
    # Excluding just the prompt's own winnowed fingerprints is NOT enough — context changes the picks.
    leaky = fingerprint(SHARED, K, W).hashes
    assert compare(fingerprint(SHARED + " " + PARA_A, K, W, leaky), fingerprint(SHARED + " " + PARA_B, K, W, leaky),
                   K, SHARED + " " + PARA_A) is not None


@given(st.integers(min_value=0, max_value=10_000), st.integers(min_value=K + W - 1, max_value=30))
@hsettings(max_examples=60)
def test_winnowing_guarantee_any_shared_run_is_detected(seed, run_len):
    rng = random.Random(seed)
    shared = words(rng, run_len)
    a = words(rng, 12) + " " + shared + " " + words(rng, 12)
    b = words(rng, 12) + " " + shared + " " + words(rng, 12)
    fa, fb = fingerprint(a, K, W), fingerprint(b, K, W)
    assert fa.hashes & fb.hashes, "a shared run of >= K+W-1 tokens must yield a shared fingerprint"


def test_emoji_offsets_round_trip():
    a = "🙂🙂 " + SHARED + " 🎉"
    b = "Intro — " + SHARED
    m = compare(fingerprint(a, K, W), fingerprint(b, K, W), K, a)
    seg = m["segments"][0]
    assert a[seg["a_start"]:seg["a_end"]] == seg["text"] and "uncertainty" in seg["text"]
    assert b[seg["b_start"]:seg["b_end"]].split()[-3:] == seg["text"].split()[-3:]  # same passage on both sides


def _submit(capp, token, assignment_id, text):
    sub = capp.post("/api/submissions/start", json={"assignment_id": assignment_id}, headers=auth(token)).json()
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(token)).json()
    events = build_chain(led["genesis"], [{"ts": 1_700_000_000_000, "p": 0, "d": 0, "i": text, "k": "paste"}])
    capp.post("/v1/ingest", headers=auth(token), json={"session_id": led["session_id"], "events": events,
                                                       "content_sha256": sha256_hex(text), "content_len": len(text)})
    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(token),
                  json={"session_id": led["session_id"], "text": text})
    assert r.status_code == 200, r.text
    return sub["submission_id"]


def test_two_students_overlap_is_symmetric(capp):
    t = signup(capp, "prof@demo.edu", "teacher")
    klass = capp.post("/api/classes", json={"name": "W"}, headers=auth(t["token"])).json()
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "E", "instructions": PARA_B,
                                             "settings": {"factcheck": False, "similarity": True}}, headers=auth(t["token"])).json()
    ana = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    ben = signup(capp, "ben@demo.edu", class_code=klass["class_code"])

    sid_ana = _submit(capp, ana["token"], a["assignment_id"], PARA_A + " " + SHARED + " " + PARA_B)
    first = capp.get(f"/api/similarity/submissions/{sid_ana}", headers=auth(t["token"])).json()
    assert first["status"] == "done" and first["result"]["matches"] == [] and first["result"]["max_score"] == 0

    sid_ben = _submit(capp, ben["token"], a["assignment_id"], "My view. " + SHARED + " " + PARA_B)
    ben_res = capp.get(f"/api/similarity/submissions/{sid_ben}", headers=auth(t["token"])).json()["result"]
    assert ben_res["matches"][0]["student_name"] == "Ana" and ben_res["max_score"] > 0
    assert "uncertainty" in ben_res["matches"][0]["segments"][0]["text"]
    assert ben_res["params"]["prompt_grams_excluded"] > 0  # PARA_B was the prompt, so it does not count

    ana_res = capp.get(f"/api/similarity/submissions/{sid_ana}", headers=auth(t["token"])).json()["result"]
    assert ana_res["matches"][0]["submission_id"] == sid_ben and ana_res["max_score"] > 0  # mirrored

    table = capp.get(f"/api/assignments/{a['assignment_id']}/submissions", headers=auth(t["token"])).json()
    assert all(r["similarity_max"] > 0 and r["similarity_status"] == "done" for r in table)

    assert capp.get(f"/api/similarity/submissions/{sid_ana}", headers=auth(ben["token"])).status_code == 404
    assert capp.post(f"/api/similarity/assignments/{a['assignment_id']}/recompute", headers=auth(ana["token"])).status_code == 403
    assert capp.post(f"/api/similarity/assignments/{a['assignment_id']}/recompute", headers=auth(t["token"])).json() == {"count": 2}
