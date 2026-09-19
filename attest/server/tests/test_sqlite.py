from fastapi.testclient import TestClient

from attest.chain import sha256_hex
from attest.main import create_app
from attest.settings import Settings
from attest.storage import SqliteStore
from attest.storage.base import SessionRecord

from conftest import build_chain, typed


def test_sqlite_store_roundtrip(tmp_path):
    store = SqliteStore(str(tmp_path / "t.db"))
    rec = SessionRecord(session_id="s1", server_nonce="n", genesis="g" * 64, created_ms=1, head="g" * 64)
    store.create(rec)
    events = build_chain("g" * 64, typed("hé🙂"))
    store.append_events("s1", events, events[-1]["hash"], replay_ok=False)
    got = store.get("s1")
    assert got.events == events and got.head == events[-1]["hash"] and got.replay_mismatches == 1
    store.set_certificate("s1", {"version": 1})
    assert store.get("s1").certificate == {"version": 1}
    assert store.get("missing") is None


def test_session_survives_app_restart(tmp_path):
    path = str(tmp_path / "attest.db")
    c1 = TestClient(create_app(Settings(STORE="sqlite", SQLITE_PATH=path)))
    s = c1.post("/v1/session/start", json={}).json()
    events = build_chain(s["genesis"], typed("persist"))
    r = c1.post("/v1/ingest", json={"session_id": s["session_id"], "events": events,
                                    "content_sha256": sha256_hex("persist"), "content_len": 7})
    assert r.status_code == 200

    c2 = TestClient(create_app(Settings(STORE="sqlite", SQLITE_PATH=path)))  # "restart"
    view = c2.get(f"/v1/session/{s['session_id']}").json()
    assert view["event_count"] == 7 and view["chain_head"] == events[-1]["hash"]
    cert = c2.post(f"/v1/session/{s['session_id']}/finalize", json={"final_text": "persist"})
    assert cert.status_code == 200 and cert.json()["event_count"] == 7
