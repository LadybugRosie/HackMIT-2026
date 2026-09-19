import pytest

from attest.chain import sha256_hex

from classroom_helpers import auth, capp, signup  # noqa: F401
from conftest import build_chain, typed


@pytest.fixture
def world(capp):
    t = signup(capp, "prof@demo.edu", "teacher")
    klass = capp.post("/api/classes", json={"name": "Writing 101"}, headers=auth(t["token"])).json()
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "Essay"}, headers=auth(t["token"])).json()
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    other = signup(capp, "ben@demo.edu", class_code=klass["class_code"])
    sub = capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).json()
    return {"t": t, "s": s, "other": other, "a": a, "sub": sub, "class": klass}


def ingest(capp, token, session_id, events, text):
    return capp.post("/v1/ingest", headers=auth(token), json={
        "session_id": session_id, "events": events, "content_sha256": sha256_hex(text), "content_len": len(text)})


def test_ledger_is_created_once_and_bound_to_submission(capp, world):
    s, sub = world["s"], world["sub"]
    l1 = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    l2 = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    assert l1["session_id"] == l2["session_id"] and l1["text"] == "" and l1["finalized"] is False
    assert l1["chain_head"] == l1["genesis"] and l1["event_count"] == 0
    rec = capp.app.state.store.get(l1["session_id"])
    assert rec.doc_id == sub["submission_id"]
    assert capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(world["other"]["token"])).status_code == 404


def test_bound_session_is_guarded_but_demo_sessions_stay_public(capp, world):
    s, other, t, sub = world["s"], world["other"], world["t"], world["sub"]
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    sid = led["session_id"]
    events = build_chain(led["genesis"], typed("hi"))

    assert ingest(capp, other["token"], sid, events, "hi").status_code == 404
    assert capp.post("/v1/ingest", json={"session_id": sid, "events": events, "content_sha256": sha256_hex("hi"), "content_len": 2}).status_code == 401
    assert ingest(capp, s["token"], sid, events, "hi").status_code == 200

    assert capp.get(f"/v1/session/{sid}").status_code == 401
    assert capp.get(f"/v1/session/{sid}", headers=auth(other["token"])).status_code == 404
    assert capp.get(f"/v1/session/{sid}", headers=auth(t["token"])).status_code == 200   # class teacher may read
    assert capp.get(f"/v1/session/{sid}/events", headers=auth(s["token"])).json()["events"][0]["i"] == "h"

    # Anonymous engine demo still works: unbound sessions are not anyone's data.
    demo = capp.post("/v1/session/start", json={}).json()
    demo_events = build_chain(demo["genesis"], typed("demo"))
    r = capp.post("/v1/ingest", json={"session_id": demo["session_id"], "events": demo_events,
                                      "content_sha256": sha256_hex("demo"), "content_len": 4})
    assert r.status_code == 200
    assert capp.get(f"/v1/session/{demo['session_id']}").status_code == 200


def test_submit_binds_text_and_stores_certificate(capp, world):
    s, t, sub, a = world["s"], world["t"], world["sub"], world["a"]
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    sid = led["session_id"]
    text = "hello world"
    events = build_chain(led["genesis"], typed(text))
    assert ingest(capp, s["token"], sid, events, text).status_code == 200

    bad = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                    json={"session_id": sid, "text": "hello world!"})
    assert bad.status_code == 409 and bad.json()["detail"]["code"] == "not_bound"

    stray = capp.post("/v1/session/start", json={}).json()
    wrong = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                      json={"session_id": stray["session_id"], "text": text})
    assert wrong.status_code == 409 and wrong.json()["detail"]["code"] == "wrong_session"

    ok = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                   json={"session_id": sid, "text": text, "certificate": {"chain_root": events[-1]["hash"]}})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["submission"]["status"] == "submitted" and body["submission"]["content"] == text
    assert body["certificate"]["assurance_level"] == "L1" and body["certificate"]["chain_root"] == events[-1]["hash"]
    assert body["verify"]["ok"] is True and body["client_certificate_matches"] is True
    assert body["submission"]["integrity"]["mix"]["typed"] == 1.0
    assert body["submission"]["factcheck_status"] == "pending"  # response is built before the background task
    after = capp.get(f"/api/submissions/{sub['submission_id']}", headers=auth(s["token"])).json()
    assert after["factcheck_status"] == "done"  # background task ran once the response was sent
    assert after["factcheck"]["summary"]["total"] == 0  # "hello world" cites nothing, so no network was needed

    # Locked: no more ingest, no re-submit, no draft edits; certificate persisted server-side.
    more = build_chain(events[-1]["hash"], typed("!", start_pos=len(text)), start_seq=len(events))
    assert ingest(capp, s["token"], sid, more, text + "!").status_code == 409
    assert capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                     json={"session_id": sid, "text": text}).status_code == 409
    assert capp.app.state.store.get(sid).certificate["doc_sha256"] == sha256_hex(text)

    # Teacher sees the chips and can re-verify + download the ledger; a classmate cannot.
    table = capp.get(f"/api/assignments/{a['assignment_id']}/submissions", headers=auth(t["token"])).json()
    ana = next(r for r in table if r["student"]["name"] == "Ana")
    assert ana["status"] == "submitted" and ana["trust"] == 100 and ana["assurance_level"] == "L1"
    v = capp.post(f"/api/review/submissions/{sub['submission_id']}/verify", headers=auth(t["token"])).json()
    assert v["ok"] is True and v["event_count"] == len(events)
    ledger = capp.get(f"/api/review/submissions/{sub['submission_id']}/ledger", headers=auth(t["token"])).json()
    assert ledger["genesis"] == led["genesis"] and len(ledger["events"]) == len(events)
    assert capp.get(f"/api/review/submissions/{sub['submission_id']}/ledger", headers=auth(world["other"]["token"])).status_code == 404


def test_resume_continues_the_chain(capp, world):
    s, sub = world["s"], world["sub"]
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    first = build_chain(led["genesis"], typed("hello"))
    assert ingest(capp, s["token"], led["session_id"], first, "hello").status_code == 200

    resumed = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    assert resumed["text"] == "hello" and resumed["event_count"] == 5 and resumed["chain_head"] == first[-1]["hash"]

    second = build_chain(resumed["chain_head"], typed(" world", start_pos=5), start_seq=resumed["event_count"])
    assert ingest(capp, s["token"], led["session_id"], second, "hello world").status_code == 200
    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                  json={"session_id": led["session_id"], "text": "hello world"})
    assert r.status_code == 200 and r.json()["certificate"]["event_count"] == 11


def test_client_finalize_then_submit_uses_stored_certificate(capp, world):
    s, sub = world["s"], world["sub"]
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    events = build_chain(led["genesis"], typed("done"))
    ingest(capp, s["token"], led["session_id"], events, "done")

    cert = capp.post(f"/v1/session/{led['session_id']}/finalize", headers=auth(s["token"]), json={"final_text": "done"})
    assert cert.status_code == 200
    assert capp.post(f"/v1/session/{led['session_id']}/finalize", json={"final_text": "done"}).status_code == 401

    mismatch = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                         json={"session_id": led["session_id"], "text": "done!"})
    assert mismatch.status_code == 409 and mismatch.json()["detail"]["code"] == "hash_mismatch"

    ok = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                   json={"session_id": led["session_id"], "text": "done"})
    assert ok.status_code == 200 and ok.json()["certificate"]["chain_root"] == cert.json()["chain_root"]


def test_settings_disable_checks(capp, world):
    t, s, sub, a = world["t"], world["s"], world["sub"], world["a"]
    capp.put(f"/api/assignments/{a['assignment_id']}", headers=auth(t["token"]),
             json={"settings": {"factcheck": False, "similarity": False}})
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    events = build_chain(led["genesis"], typed("x"))
    ingest(capp, s["token"], led["session_id"], events, "x")
    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(s["token"]),
                  json={"session_id": led["session_id"], "text": "x"}).json()
    assert r["submission"]["factcheck_status"] == "skipped" and r["submission"]["similarity_status"] == "skipped"
