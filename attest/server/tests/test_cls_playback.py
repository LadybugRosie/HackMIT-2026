from attest.chain import sha256_hex
from attest.provenance import PieceTable
from attest.storage.base import SessionRecord
from classroom.playback import build_playback

from classroom_helpers import auth, capp, signup  # noqa: F401
from conftest import build_chain, typed

T = 1_700_000_000_000


def session_with(events):
    return SessionRecord(session_id="s", server_nonce="n", genesis="g" * 64, created_ms=T, events=events,
                         head=events[-1]["hash"] if events else "g" * 64)


def replay_with_origins(events):
    """Client-side rules: code-point arrays, a parallel origins array."""
    cps, origins = [], []
    for ev in events:
        if ev["k"] == "ckpt":
            cps, origins = list(ev["i"]), ["EXT"] * len(ev["i"])
            continue
        ins = list(ev["i"])
        cps[ev["p"]:ev["p"] + ev["d"]] = ins
        origins[ev["p"]:ev["p"] + ev["d"]] = [ev["origin"]] * len(ins)
    return "".join(cps), origins


def test_playback_labels_and_pauses():
    ops = typed("hello", start_ts=T)                                        # 5 keystrokes, 120 ms apart
    ops += [{"ts": T + 3000, "p": 5, "d": 0, "i": " world", "k": "paste"}]  # EXT paste after a 2.5 s pause
    ops += [{"ts": T + 3100, "p": 0, "d": 0, "i": "", "k": "kd"}, {"ts": T + 3150, "p": 0, "d": 0, "i": "", "k": "ku"}]
    ops += [{"ts": T + 3200, "p": 0, "d": 0, "i": "hello", "k": "copy"}]
    ops += [{"ts": T + 3300, "p": 11, "d": 0, "i": "hello", "k": "paste"}] # INT paste (copied 100 ms ago)
    ops += [{"ts": T + 3400, "p": 0, "d": 1, "i": "H", "k": "type"}]        # deletion + type
    events = build_chain("g" * 64, ops)
    pb = build_playback(session_with(events))

    kinds = [e["k"] for e in pb["events"]]
    assert "kd" not in kinds and "ku" not in kinds and "copy" not in kinds
    origins = [e["origin"] for e in pb["events"] if e["k"] == "paste"]
    assert origins == ["EXT", "INT"]
    assert pb["pauses"] == [{"after_seq": 4, "ms": 3000 - 480}]
    assert pb["summary"]["keystroke_events"] == 6 and pb["summary"]["paste_events"] == 2
    assert pb["summary"]["internal_paste_events"] == 1 and pb["summary"]["deletion_events"] == 1
    assert pb["final_text"] == "Hello worldhello" and pb["duration_ms"] == 3400

    # Client-style replay of the labelled events reproduces the text and the piece table's EXT spans.
    text, origins = replay_with_origins(pb["events"])
    assert text == pb["final_text"]
    ext_spans = []
    for i, o in enumerate(origins):
        if o == "EXT":
            if ext_spans and ext_spans[-1][1] == i:
                ext_spans[-1][1] = i + 1
            else:
                ext_spans.append([i, i + 1])
    table = PieceTable().apply_all(events)
    assert [tuple(s) for s in ext_spans] == table.external_spans()
    assert pb["summary"]["ext_chars"] == sum(e - s for s, e in table.external_spans())


def test_checkpoint_resets_playback():
    ops = typed("abc", start_ts=T) + [{"ts": T + 5000, "p": 0, "d": 0, "i": "restored", "k": "ckpt"}]
    pb = build_playback(session_with(build_chain("g" * 64, ops)))
    assert pb["events"][-1]["origin"] == "EXT" and pb["final_text"] == "restored"
    assert replay_with_origins(pb["events"])[0] == "restored"


def test_empty_ledger():
    pb = build_playback(session_with([]))
    assert pb["events"] == [] and pb["duration_ms"] == 0 and pb["final_text"] == ""


def test_playback_endpoint_access(capp):
    t = signup(capp, "prof@demo.edu", "teacher")
    klass = capp.post("/api/classes", json={"name": "W"}, headers=auth(t["token"])).json()
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "E"}, headers=auth(t["token"])).json()
    s = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    other = signup(capp, "ben@demo.edu", class_code=klass["class_code"])
    sub = capp.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=auth(s["token"])).json()
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(s["token"])).json()
    events = build_chain(led["genesis"], typed("hi there"))
    capp.post("/v1/ingest", headers=auth(s["token"]), json={"session_id": led["session_id"], "events": events,
                                                             "content_sha256": sha256_hex("hi there"), "content_len": 8})
    url = f"/api/review/submissions/{sub['submission_id']}/playback"
    assert capp.get(url, headers=auth(t["token"])).json()["final_text"] == "hi there"
    assert capp.get(url, headers=auth(s["token"])).status_code == 200      # students may watch their own
    assert capp.get(url, headers=auth(other["token"])).status_code == 404
    assert capp.get(url).status_code == 401
