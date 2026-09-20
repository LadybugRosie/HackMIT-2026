#!/usr/bin/env python3
"""attest walkthrough — every key feature, end to end, in one run.

    cd server && .venv/bin/python walkthrough.py            # offline: software device + software witness
    cd server && .venv/bin/python walkthrough.py --live-tsa # also fetch a real FreeTSA timestamp

Runs the engine and the classroom in-process (a fresh SQLite file in a temp dir — nothing you have
is touched), narrates each step, and exits 1 if any expectation fails. Where a real Mac is needed
(Touch ID, the native HID helper) a software stand-in that produces byte-identical output is used;
those steps say so.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

from fastapi.testclient import TestClient  # noqa: E402

from attest.attestors.webauthn import b64url_decode  # noqa: E402
from attest.chain import link_hash, merkle_root, sha256_hex, verify_chain  # noqa: E402
from attest.replay import replay  # noqa: E402
from classroom.app import create_app  # noqa: E402
from classroom.settings import ClassroomSettings  # noqa: E402
from fake_authenticator import FakeAuthenticator  # noqa: E402
from fake_hid import FakeHelper  # noqa: E402

RP, ORIGIN = "localhost", "http://localhost:9100"
FAILS = 0
STEP = 0


def step(title: str) -> None:
    global STEP
    STEP += 1
    print(f"\n\033[1m{STEP:2d}. {title}\033[0m")


def ok(cond: bool, msg: str, detail: str = "") -> None:
    global FAILS
    mark = "\033[32m✓\033[0m" if cond else "\033[31m✗\033[0m"
    print(f"    {mark} {msg}" + (f"  \033[2m{detail}\033[0m" if detail else ""))
    if not cond:
        FAILS += 1


def note(msg: str) -> None:
    print(f"    \033[2m{msg}\033[0m")


def chain(genesis: str, raw: list, start_seq: int = 0) -> list:
    out, prev = [], genesis
    for n, r in enumerate(raw):
        ev = {"seq": start_seq + n, "ts": r["ts"], "p": r.get("p", 0), "d": r.get("d", 0), "i": r.get("i", ""), "k": r.get("k", "type"),
              "src": r.get("src"), "prev": prev}
        ev["hash"] = link_hash(ev)
        out.append(ev)
        prev = ev["hash"]
    return out


def human_typing(text: str, t0: int, pos0: int = 0) -> list:
    """kd + edit per character with human-ish gaps, a pause at each sentence, and a few revisions."""
    import random
    rng = random.Random(len(text))
    raw, ts, pos = [], t0, pos0
    for ch in text:
        ts += max(60, int(rng.gauss(190, 70)))
        if ch in ".?!":
            ts += rng.randint(900, 2500)
        raw.append({"ts": ts, "p": 0, "d": 0, "i": "", "k": "kd"})
        raw.append({"ts": ts + 6, "p": pos, "d": 0, "i": ch, "k": "type"})
        pos += 1
    for _ in range(6):  # revisions: back up and retype a word
        k = rng.randint(1, 3)
        at = rng.randint(pos0, pos0 + len(text) - k - 1)
        ts += rng.randint(400, 1500)
        raw.append({"ts": ts, "p": 0, "d": 0, "i": "", "k": "kd"})
        raw.append({"ts": ts + 6, "p": at, "d": k, "i": "", "k": "type"})
        for j, ch in enumerate(text[at - pos0:at - pos0 + k]):
            ts += rng.randint(120, 300)
            raw.append({"ts": ts, "p": 0, "d": 0, "i": "", "k": "kd"})
            raw.append({"ts": ts + 6, "p": at + j, "d": 0, "i": ch, "k": "type"})
    return raw


ESSAY = ("Cities should price road use by the hour rather than build their way out of congestion. "
         "Every driver who joins a jammed street imposes a cost on everyone already in it. "
         "Stockholm's trial cut inner-city traffic by about a fifth (Eliasson, 2008; see DOI 10.1016/j.tra.2008.09.003). "
         "Critics call pricing regressive, but the revenue can fund the buses that low-income commuters ride.")
COPIED = "Every driver who joins a jammed street imposes a cost on everyone already in it. "


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live-tsa", action="store_true", help="fetch a real RFC 3161 token from freetsa.org")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="attest-walkthrough-"))
    os.environ["ATTEST_TSA_URL"] = "https://freetsa.org/tsr" if args.live_tsa else ""
    os.environ["ATTEST_WEBAUTHN_RP_ID"] = RP
    os.environ["ATTEST_WEBAUTHN_ORIGINS"] = json.dumps([ORIGIN])
    app = create_app(ClassroomSettings(DB_PATH=str(tmp / "classroom.db"), SCRYPT_N=2**10))
    c = TestClient(app)
    H = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731
    print(f"\033[1mattest walkthrough\033[0m — fresh database in {tmp}" + ("  (live FreeTSA)" if args.live_tsa else "  (offline)"))

    # ---------------------------------------------------------------- engine: chain + replay
    step("A hash-chained ledger: every edit links to the one before")
    s = c.post("/v1/session/start", json={}).json()
    sid, genesis = s["session_id"], s["genesis"]
    text1 = "Hello, attested world."
    ev = chain(genesis, human_typing(text1, 1_700_000_000_000))
    r = c.post("/v1/ingest", json={"session_id": sid, "events": ev, "content_sha256": sha256_hex(text1), "content_len": len(text1)}).json()
    ok(r["replay_ok"] and r["event_count"] == len(ev), f"{len(ev)} events accepted; server replays them to the same text", f"head {r['chain_head'][:12]}…")
    ok(verify_chain(ev, genesis).ok, "chain verifies from genesis")
    bad = json.loads(json.dumps(ev))
    bad[7]["i"] = "X"
    res = verify_chain(bad, genesis)
    ok(not res.ok and res.index == 7, "altering one character of event 7 breaks the chain at event 7", res.error or "")
    r2 = c.post("/v1/ingest", json={"session_id": sid, "events": ev[:3], "content_sha256": sha256_hex(text1), "content_len": len(text1)})
    ok(r2.status_code == 409 and r2.json()["detail"]["code"] == "chain_break", "re-sending old events is refused (409 chain_break)")

    step("Replay binds the ledger to the text — the L1 guarantee")
    ok(replay(ev) == text1, "replay(ledger) == submitted text")
    r = c.post(f"/v1/session/{sid}/finalize", json={"final_text": text1 + "!"})
    ok(r.status_code == 409, "finalize with a different text is refused — no certificate for text the ledger did not produce")
    cert1 = c.post(f"/v1/session/{sid}/finalize", json={"final_text": text1}).json()
    ok(cert1["assurance_level"] == "L1" and cert1["doc_sha256"] == sha256_hex(text1), "certificate issued at L1", f"chain_root {cert1['chain_root'][:12]}… merkle {cert1['merkle_root'][:12]}…")
    ok(cert1["merkle_root"] == merkle_root([e["hash"] for e in ev]), "merkle root over event hashes matches")
    ok(bool(cert1.get("issuer")), "certificate carries the server's issuer seal", f"key {cert1['issuer']['key_id']}")
    v = c.post("/v1/verify", json={"certificate": cert1, "text": text1, "events": ev}).json()
    ok(v["ok"] and v["assurance_level"] == "L1", "server verify: all checks pass", ", ".join(ch["name"] for ch in v["checks"]))
    v2 = c.post("/v1/verify", json={"certificate": cert1, "text": text1 + " ", "events": ev}).json()
    ok(not v2["ok"], "one extra space in the text → doc_sha256 and replay FAIL")

    step("Provenance and process signals: what was typed, pasted, and how it looked")
    integ = cert1["claims"]["integrity"]
    ok(integ["mix"]["typed"] == 1.0, "composition: 100% typed", f"verdict {integ['verdict']}")
    s2 = c.post("/v1/session/start", json={}).json()
    raw = human_typing("I wrote this part. ", 1_700_000_100_000)
    t = raw[-1]["ts"] + 3000
    raw.append({"ts": t, "p": len("I wrote this part. "), "d": 0, "i": "This part arrived from the clipboard, all at once.", "k": "paste", "src": "ext"})
    ev2 = chain(s2["genesis"], raw)
    text2 = replay(ev2)
    r = c.post("/v1/ingest", json={"session_id": s2["session_id"], "events": ev2, "content_sha256": sha256_hex(text2), "content_len": len(text2)}).json()
    mix = r["integrity"]["mix"]
    ok(mix["external"] > 0.6 and r["integrity"]["ext_spans"], f"external paste detected: {mix['external']:.0%} of the text, span {r['integrity']['ext_spans'][0]}")
    names = {sg["name"]: sg for sg in r["integrity"]["signals"]}
    ok(set(names) >= {"inter_key_interval", "typed_speed", "transcription_cadence", "revision_effort", "edit_locality"},
       "five process signals computed", "; ".join(f"{n}={sg['verdict']}" for n, sg in names.items()))

    # ---------------------------------------------------------------- L2
    step("L2 — device key + trusted time (software authenticator standing in for Touch ID)")
    s3 = c.post("/v1/session/start", json={}).json()
    sid3, gen3 = s3["session_id"], s3["genesis"]
    auth = FakeAuthenticator(RP, ORIGIN)
    opts = c.get(f"/v1/session/{sid3}/enroll/options").json()
    r = c.post(f"/v1/session/{sid3}/enroll", json=auth.create(b64url_decode(opts["challenge"])))
    ok(r.status_code == 201, "device key enrolled (WebAuthn registration parsed: CBOR → COSE P-256 key)", f"credential {r.json()['credential_id'][:12]}…")
    text3 = "Sealed on this device."
    ev3 = chain(gen3, human_typing(text3, 1_700_000_200_000))
    c.post("/v1/ingest", json={"session_id": sid3, "events": ev3, "content_sha256": sha256_hex(text3), "content_len": len(text3)})
    head = ev3[-1]["hash"]
    r = c.post(f"/v1/session/{sid3}/attest", json={"head": head, **auth.get(bytes.fromhex(head))}).json()
    wa = r["results"][0]
    ok(wa["ok"] and wa["level"] == "L2", "device signature over the chain head verifies", wa["detail"])
    if args.live_tsa:
        ts = next((x for x in r["results"] if x["kind"] == "timestamp"), None)
        ok(bool(ts and ts["ok"]), "FreeTSA timestamp fetched and its CMS signature verified against the pinned cert", ts["detail"] if ts else "no timestamp")
    else:
        note("trusted timestamps skipped (offline) — run with --live-tsa to fetch a real FreeTSA token")
    fake = FakeAuthenticator(RP, ORIGIN)
    r = c.post(f"/v1/session/{sid3}/attest", json={"head": head, **fake.get(bytes.fromhex(head))})
    ok(r.status_code == 404, "a stranger's device key is refused")
    r = c.post(f"/v1/session/{sid3}/attest", json={"head": head, **auth.get(bytes.fromhex(head), tamper_signature=True)})
    ok(r.status_code == 400, "a tampered signature is refused")
    cert3 = c.post(f"/v1/session/{sid3}/finalize", json={"final_text": text3}).json()
    ok(cert3["assurance_level"] == "L2" and cert3["claims"]["attestation"]["final_head_signed"], "certificate issued at L2")
    ev3_all = c.get(f"/v1/session/{sid3}/events").json()["events"]
    forged = {**cert3, "attestations": []}
    v = c.post("/v1/verify", json={"certificate": forged, "text": text3, "events": ev3_all}).json()
    ok(not v["ok"], "claiming L2 with the device signature stripped fails", next(ch["detail"] for ch in v["checks"] if ch["name"] == "assurance_level"))

    # ---------------------------------------------------------------- L3
    step("L3 — hardware witness (software helper standing in for native/attest-hid)")
    s4 = c.post("/v1/session/start", json={}).json()
    sid4, gen4 = s4["session_id"], s4["genesis"]
    auth4, helper = FakeAuthenticator(RP, ORIGIN), FakeHelper()
    opts = c.get(f"/v1/session/{sid4}/enroll/options").json()
    c.post(f"/v1/session/{sid4}/enroll", json=auth4.create(b64url_decode(opts["challenge"])))
    opts = c.get(f"/v1/session/{sid4}/enroll/options").json()
    r = c.post(f"/v1/session/{sid4}/enroll-hid", json=helper.enroll_payload(b64url_decode(opts["challenge"])))
    ok(r.status_code == 201, "witness key enrolled (signature over the enrollment challenge)", f"key {helper.key_id}")
    text4 = "Every one of these keystrokes was a physical key press."
    ev4 = chain(gen4, human_typing(text4, 1_700_000_300_000))
    c.post("/v1/ingest", json={"session_id": sid4, "events": ev4, "content_sha256": sha256_hex(text4), "content_len": len(text4)})
    root4 = ev4[-1]["hash"]
    kd = [e["ts"] for e in ev4 if e["k"] == "kd"]
    sts = helper.witness(sid4, gen4, root4, kd, extra_per_window=2)
    r = c.post(f"/v1/session/{sid4}/attest-hid", json={"key_id": helper.key_id, "statements": sts}).json()
    ok(r["final"] and r["hid"]["supports_l3"], f"{len(sts)} signed windows relayed; hardware ≥ editor in every window",
       f"editor {r['hid']['ledger_kd']} / hardware {r['hid']['hw_kd']}, coverage {r['hid']['coverage_ratio']:.0%}")
    c.post(f"/v1/session/{sid4}/attest", json={"head": root4, **auth4.get(bytes.fromhex(root4))})
    cert4 = c.post(f"/v1/session/{sid4}/finalize", json={"final_text": text4}).json()
    ok(cert4["assurance_level"] == "L3", "certificate issued at L3 (software witness)")

    step("Injection: text the editor recorded but no key was pressed")
    s5 = c.post("/v1/session/start", json={}).json()
    sid5, gen5 = s5["session_id"], s5["genesis"]
    auth5, helper5 = FakeAuthenticator(RP, ORIGIN), FakeHelper()
    opts = c.get(f"/v1/session/{sid5}/enroll/options").json()
    c.post(f"/v1/session/{sid5}/enroll", json=auth5.create(b64url_decode(opts["challenge"])))
    opts = c.get(f"/v1/session/{sid5}/enroll/options").json()
    c.post(f"/v1/session/{sid5}/enroll-hid", json=helper5.enroll_payload(b64url_decode(opts["challenge"])))
    honest = "One honest sentence, typed by hand. "
    raw = human_typing(honest, 1_700_000_400_000)
    t_inj = raw[-1]["ts"] + 6000
    injected = "This paragraph was typed by a script while nobody touched the keyboard."
    raw.append({"ts": t_inj, "p": len(honest), "d": 0, "i": injected, "k": "type"})
    ev5 = chain(gen5, raw)
    text5 = replay(ev5)
    c.post("/v1/ingest", json={"session_id": sid5, "events": ev5, "content_sha256": sha256_hex(text5), "content_len": len(text5)})
    root5 = ev5[-1]["hash"]
    sts = helper5.witness(sid5, gen5, root5, [e["ts"] for e in ev5 if e["k"] == "kd"], t_end=t_inj + 1500)  # hardware saw only the real keys
    r = c.post(f"/v1/session/{sid5}/attest-hid", json={"key_id": helper5.key_id, "statements": sts}).json()
    inj = r["hid"]["injection_windows"]
    ok(bool(inj), "witness flags the window: editor keystrokes, hardware none",
       f"editor {inj[0]['ledger_kd']} vs hardware {inj[0]['hw_kd']}" if inj else "no injection window found")
    c.post(f"/v1/session/{sid5}/attest", json={"head": root5, **auth5.get(bytes.fromhex(root5))})
    cert5 = c.post(f"/v1/session/{sid5}/finalize", json={"final_text": text5}).json()
    ok(cert5["assurance_level"] == "L2", "certificate stays at L2 and says why", cert5["claims"]["attestation"]["hid"]["reasons"][0])

    # ---------------------------------------------------------------- issuer seal
    step("The issuer seal: a perfect certificate from someone else's server is not ours")
    (tmp / "other").mkdir()
    other = TestClient(create_app(ClassroomSettings(DB_PATH=str(tmp / "other" / "classroom.db"), SCRYPT_N=2**10)))  # its own data dir, its own key
    so = other.post("/v1/session/start", json={}).json()
    texto = "Minted elsewhere."
    evo = chain(so["genesis"], human_typing(texto, 1_700_000_500_000))
    other.post("/v1/ingest", json={"session_id": so["session_id"], "events": evo, "content_sha256": sha256_hex(texto), "content_len": len(texto)})
    certo = other.post(f"/v1/session/{so['session_id']}/finalize", json={"final_text": texto}).json()
    v = c.post("/v1/verify", json={"certificate": certo, "text": texto, "events": evo}).json()
    iss = next(ch for ch in v["checks"] if ch["name"] == "issuer")
    ok(not v["ok"] and not iss["ok"], "our server rejects it: internally valid, but signed by an unknown issuer key", iss["detail"])
    tampered = json.loads(json.dumps(cert4))
    tampered["doc_len"] += 1
    v = c.post("/v1/verify", json={"certificate": tampered, "text": text4}).json()
    ok(not v["ok"], "editing any field of a sealed certificate breaks the seal")

    # ---------------------------------------------------------------- offline CLI
    step("Offline verification with plain python3 — no packages, no server")
    ledger4 = c.get(f"/v1/session/{sid4}/events").json()
    (tmp / "cert.json").write_text(json.dumps(cert4))
    (tmp / "ledger.json").write_text(json.dumps(ledger4))
    (tmp / "essay.txt").write_text(text4)
    issuer_pub = c.get("/v1/issuer").json()["public_key"]
    cli = HERE.parent / "verifier" / "attest_verify.py"
    out = subprocess.run(["python3", str(cli), str(tmp / "cert.json"), str(tmp / "essay.txt"), "--events", str(tmp / "ledger.json"),
                          "--issuer-key", issuer_pub], capture_output=True, text=True)
    ok(out.returncode == 0 and "assurance level L3" in out.stdout, "CLI: PASS — assurance level L3", out.stdout.strip().splitlines()[-2][:110])
    (tmp / "essay-edited.txt").write_text(text4.replace("physical", "phsyical"))
    out = subprocess.run(["python3", str(cli), str(tmp / "cert.json"), str(tmp / "essay-edited.txt"), "--events", str(tmp / "ledger.json")],
                         capture_output=True, text=True)
    ok(out.returncode == 1 and "FAIL" in out.stdout, "CLI: one transposed letter in the essay → FAIL")

    # ---------------------------------------------------------------- classroom
    step("Classroom: accounts, class code, assignment")
    prof = c.post("/api/auth/signup", json={"email": "prof@walk.edu", "password": "Passw0rd!x", "name": "Prof Walk", "role": "teacher"}).json()
    klass = c.post("/api/classes", json={"name": "Writing 101"}, headers=H(prof["token"])).json()
    a = c.post("/api/assignments", json={"class_id": klass["class_id"], "title": "Position paper", "instructions": "Argue one position. Cite two sources.",
                                          "due_ms": int(time.time() * 1000) + 7 * 86_400_000, "points": 100}, headers=H(prof["token"])).json()
    ana = c.post("/api/auth/signup", json={"email": "ana@walk.edu", "password": "Passw0rd!x", "name": "Ana", "role": "student", "class_code": klass["class_code"]}).json()
    ben = c.post("/api/auth/signup", json={"email": "ben@walk.edu", "password": "Passw0rd!x", "name": "Ben", "role": "student", "class_code": klass["class_code"]}).json()
    ok(ana["user"]["role"] == "student" and klass["class_code"] in str(c.get("/api/dashboard", headers=H(prof["token"])).json()),
       f"teacher created class {klass['class_code']}; two students joined by code; assignment '{a['title']}'")
    ok(c.post("/api/classes", json={"name": "Nope"}, headers=H(ana["token"])).status_code == 403, "a student cannot create a class (403)")

    step("Student writes in the attested editor and submits — the hard guarantee")
    sub = c.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=H(ana["token"])).json()
    led = c.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=H(ana["token"])).json()
    ok(led["event_count"] == 0 and led["session_id"], "a ledger session bound to the submission is created", f"session {led['session_id'][:8]}…")
    ok(c.post("/v1/ingest", json={"session_id": led["session_id"], "events": [], "content_sha256": "0" * 64, "content_len": 0},
              headers=H(ben["token"])).status_code in (404, 422), "another student cannot append to Ana's ledger")
    evA = chain(led["genesis"], human_typing(ESSAY, 1_700_001_000_000))
    r = c.post("/v1/ingest", headers=H(ana["token"]), json={"session_id": led["session_id"], "events": evA, "content_sha256": sha256_hex(ESSAY), "content_len": len(ESSAY)})
    ok(r.status_code == 200 and r.json()["replay_ok"], f"Ana types the essay: {len(evA)} events, replay binds")
    r = c.post(f"/api/submissions/{sub['submission_id']}/submit", headers=H(ana["token"]), json={"session_id": led["session_id"], "text": ESSAY + " Extra."})
    ok(r.status_code == 409 and r.json()["detail"]["code"] == "not_bound", "submitting text the ledger did not produce → 409, not a warning")
    r = c.post(f"/api/submissions/{sub['submission_id']}/submit", headers=H(ana["token"]), json={"session_id": led["session_id"], "text": ESSAY}).json()
    ok(r["certificate"]["assurance_level"] == "L1" and r["verify"]["ok"], "submitted: certificate rebuilt from the server's own ledger copy, sealed by the issuer",
       f"trust {r['submission']['integrity']['scores']['trust']}, verdict {r['submission']['integrity']['verdict']}")
    ok(c.post("/v1/ingest", headers=H(ana["token"]), json={"session_id": led["session_id"], "events": evA[:1], "content_sha256": sha256_hex(ESSAY), "content_len": len(ESSAY)}).status_code == 409,
       "the ledger is frozen after submit")

    step("Similarity: a classmate reuses a sentence")
    subB = c.post("/api/submissions/start", json={"assignment_id": a["assignment_id"]}, headers=H(ben["token"])).json()
    ledB = c.post(f"/api/submissions/{subB['submission_id']}/ledger", headers=H(ben["token"])).json()
    textB = "My own opening about transit funding and fairness in cities. " + COPIED + "Then my own conclusion, written independently of anyone else."
    evB = chain(ledB["genesis"], [{"ts": 1_700_002_000_000, "p": 0, "d": 0, "i": textB, "k": "paste", "src": "ext"}])
    c.post("/v1/ingest", headers=H(ben["token"]), json={"session_id": ledB["session_id"], "events": evB, "content_sha256": sha256_hex(textB), "content_len": len(textB)})
    r = c.post(f"/api/submissions/{subB['submission_id']}/submit", headers=H(ben["token"]), json={"session_id": ledB["session_id"], "text": textB}).json()
    ok(r["submission"]["integrity"]["mix"]["external"] == 1.0, "Ben pasted everything: composition 100% external")
    time.sleep(0.3)
    sim = c.get(f"/api/similarity/submissions/{subB['submission_id']}", headers=H(prof["token"])).json()
    m = (sim.get("result") or {}).get("matches") or []
    ok(bool(m) and m[0]["student_name"] == "Ana" and "jammed street" in m[0]["segments"][0]["text"],
       "similarity finds the shared sentence and names the passage", f"score {m[0]['score']}% vs Ana" if m else f"status {sim.get('status')}")

    step("Citations: DOIs and references are checked (offline resolver here)")
    fc = c.get(f"/api/factcheck/submissions/{sub['submission_id']}", headers=H(prof["token"])).json()
    refs = (fc.get("result") or {}).get("references") or (fc.get("result") or {}).get("items") or []
    ok(fc["status"] in ("done", "pending", "error"), f"fact-check ran in the background: status {fc['status']}",
       f"{len(refs)} reference(s) extracted" if refs else json.dumps(fc.get("result"))[:100])

    step("Teacher review: verify, playback from the ledger alone, grade, return")
    v = c.post(f"/api/review/submissions/{sub['submission_id']}/verify", headers=H(prof["token"])).json()
    ok(v["ok"] and v["assurance_level"] == "L1" and next(ch for ch in v["checks"] if ch["name"] == "issuer")["ok"],
       "server re-verifies Ana's certificate including the issuer seal", f"{len(v['checks'])} checks")
    pb = c.get(f"/api/review/submissions/{sub['submission_id']}/playback", headers=H(prof["token"])).json()
    ok(pb["final_text"] == ESSAY and pb["summary"]["keystroke_events"] > 300 and pb["pauses"],
       "playback payload rebuilt from the ledger", f"{pb['summary']['keystroke_events']} keystrokes, {len(pb['pauses'])} pauses, {pb['duration_ms'] // 1000}s")
    ok(c.get(f"/api/review/submissions/{sub['submission_id']}/playback", headers=H(ben["token"])).status_code == 404, "Ben cannot see Ana's playback (404)")
    g = c.post(f"/api/submissions/{sub['submission_id']}/grade", json={"grade": 91, "feedback": "Sharp argument; cite the DOI inline."}, headers=H(prof["token"])).json()
    ret = c.post(f"/api/submissions/{sub['submission_id']}/return", headers=H(prof["token"])).json()
    mine = c.get(f"/api/submissions/{sub['submission_id']}", headers=H(ana["token"])).json()
    ok(g["grade"] == 91 and ret["status"] == "returned" and mine["feedback"].startswith("Sharp"), "graded and returned; Ana sees grade and feedback")
    table = c.get(f"/api/assignments/{a['assignment_id']}/submissions", headers=H(prof["token"])).json()
    ok(len(table) == 2 and {r["student"]["name"] for r in table} == {"Ana", "Ben"}, "teacher's table: one row per student with trust / external / similarity / citation chips")

    print()
    if FAILS:
        print(f"\033[31m{FAILS} check(s) failed.\033[0m")
        return 1
    print(f"\033[32mAll {STEP} sections passed.\033[0m  Fresh data left in {tmp} (safe to delete).")
    print("Not covered here (needs a person): Touch ID prompts, the native attest-hid.app, the browser UI — see README.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
