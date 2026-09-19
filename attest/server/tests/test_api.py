from attest.chain import sha256_hex

from conftest import build_chain, typed


def start(client):
    r = client.post("/v1/session/start", json={"doc_id": "essay-1"})
    assert r.status_code == 200
    return r.json()


def ingest(client, session, events, text):
    return client.post("/v1/ingest", json={
        "session_id": session["session_id"], "events": events,
        "content_sha256": sha256_hex(text), "content_len": len(text),
    })


def test_healthz(client):
    assert client.get("/healthz").json()["ok"] is True


def test_full_flow_start_ingest_finalize_verify(client):
    s = start(client)
    events = build_chain(s["genesis"], typed("hello"))
    r = ingest(client, s, events, "hello")
    assert r.status_code == 200
    body = r.json()
    assert body["replay_ok"] and body["event_count"] == 5 and body["chain_head"] == events[-1]["hash"]

    more = build_chain(events[-1]["hash"], typed(" world", start_pos=5), start_seq=5)
    r = ingest(client, s, more, "hello world")
    assert r.status_code == 200 and r.json()["event_count"] == 11

    r = client.post(f"/v1/session/{s['session_id']}/finalize", json={"final_text": "hello world"})
    assert r.status_code == 200
    cert = r.json()
    assert cert["doc_sha256"] == sha256_hex("hello world")
    assert cert["chain_root"] == more[-1]["hash"] and cert["event_count"] == 11
    assert cert["assurance_level"] == "L1"

    exported = client.get(f"/v1/session/{s['session_id']}/events").json()
    r = client.post("/v1/verify", json={"certificate": cert, "text": "hello world", "events": exported["events"]})
    assert r.status_code == 200
    assert r.json()["ok"] is True and r.json()["assurance_level"] == "L1"

    # Tampered text fails, and names the failing check.
    r = client.post("/v1/verify", json={"certificate": cert, "text": "hello world!", "events": exported["events"]})
    v = r.json()
    assert v["ok"] is False
    assert any(c["name"] == "doc_sha256" and not c["ok"] for c in v["checks"])

    # Tampered ledger fails at the chain.
    bad = [dict(e) for e in exported["events"]]
    bad[3]["i"] = "X"
    r = client.post("/v1/verify", json={"certificate": cert, "text": "hello world", "events": bad})
    v = r.json()
    assert v["ok"] is False
    assert any(c["name"] == "chain_links" and not c["ok"] for c in v["checks"])


def test_ingest_rejects_broken_prev_with_409(client):
    s = start(client)
    events = build_chain("f" * 64, typed("hi"))
    r = ingest(client, s, events, "hi")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "chain_break" and r.json()["detail"]["index"] == 0


def test_ingest_rejects_replayed_batch(client):
    s = start(client)
    events = build_chain(s["genesis"], typed("hi"))
    assert ingest(client, s, events, "hi").status_code == 200
    r = ingest(client, s, events, "hi")  # same seqs again
    assert r.status_code == 409 and r.json()["detail"]["code"] == "chain_break"


def test_ingest_reports_replay_mismatch(client):
    s = start(client)
    events = build_chain(s["genesis"], typed("hi"))
    r = ingest(client, s, events, "something else")
    assert r.status_code == 200 and r.json()["replay_ok"] is False
    view = client.get(f"/v1/session/{s['session_id']}").json()
    assert view["replay_mismatches"] == 1


def test_finalize_refuses_unbound_text(client):
    s = start(client)
    events = build_chain(s["genesis"], typed("hi"))
    ingest(client, s, events, "hi")
    r = client.post(f"/v1/session/{s['session_id']}/finalize", json={"final_text": "hi there"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_bound"


def test_ingest_after_finalize_is_refused(client):
    s = start(client)
    events = build_chain(s["genesis"], typed("hi"))
    ingest(client, s, events, "hi")
    client.post(f"/v1/session/{s['session_id']}/finalize", json={"final_text": "hi"})
    more = build_chain(events[-1]["hash"], typed("!", start_pos=2), start_seq=2)
    assert ingest(client, s, more, "hi!").status_code == 409


def test_unknown_session_404(client):
    assert client.get("/v1/session/nope").status_code == 404
