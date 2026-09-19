"""Demo data for judging: `python -m classroom.seed` (idempotent; safe to re-run).

Creates teacher prof@demo.edu, students ana@/ben@/cara@demo.edu (password Passw0rd!x), the
class "Writing 101" with code DEMO26, one published assignment, and Ben's already-submitted
essay produced from a synthetic *human-like* ledger (jittered keystrokes, pauses at clause
boundaries, a few revisions) so the review page has real signals, a certificate and a replay.
"""
from __future__ import annotations

import hashlib
import random
import sys
import time

from fastapi.testclient import TestClient

from attest.chain import link_hash
from attest.replay import replay

from .app import create_app
from .settings import settings

PASSWORD = "Passw0rd!x"
CLASS_CODE = "DEMO26"
ESSAY = (
    "Cities should price road use by the hour rather than build their way out of congestion. "
    "Every driver who joins a jammed street imposes a cost on everyone already in it, and a price is the "
    "only instrument that makes that cost visible at the moment the decision is made (Vickrey, 1969). "
    "Stockholm's trial cut inner-city traffic by about a fifth and the reduction persisted after the "
    "charge became permanent (Eliasson, 2008; see DOI 10.1016/j.tra.2008.09.003). Critics call pricing "
    "regressive, but the revenue can fund the buses that low-income commuters actually ride. The evidence "
    "base is stronger than the politics suggests.\n\n"
    "References\n"
    "Vickrey, W. 1969. Congestion theory and transport investment. American Economic Review.\n"
    "Eliasson, J. 2008. Lessons from the Stockholm congestion charging trial. Transport Policy. 10.1016/j.tra.2008.09.003\n"
)
BOUNDARY = set(" \n.,;:!?")


def human_ledger(text: str, genesis: str, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    ts = int(time.time() * 1000) - 25 * 60_000  # "written" over the last ~25 minutes
    ops = []
    for n, ch in enumerate(text):
        ts += max(45, int(rng.gauss(210, 80)))
        if n and text[n - 1] in BOUNDARY and rng.random() < 0.4:
            ts += rng.randint(900, 4000)
        ops.append({"ts": ts, "p": n, "d": 0, "i": ch, "k": "type"})
    for _ in range(18):  # revisions: delete a short run and retype it
        k = rng.randint(1, 3)
        pos = rng.randint(0, len(text) - k - 1)
        ts += rng.randint(500, 3000)
        ops.append({"ts": ts, "p": pos, "d": k, "i": "", "k": "type"})
        for j, ch in enumerate(text[pos:pos + k]):
            ts += rng.randint(120, 320)
            ops.append({"ts": ts, "p": pos + j, "d": 0, "i": ch, "k": "type"})
    events, prev = [], genesis
    for n, raw in enumerate(ops):
        ev = {"seq": n, **raw, "src": None, "prev": prev}
        ev["hash"] = link_hash(ev)
        events.append(ev)
        prev = ev["hash"]
    return events


def main() -> int:
    client = TestClient(create_app(settings))
    h = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731

    def login_or_signup(email: str, name: str, role: str, class_code: str | None = None) -> str:
        r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code == 200:
            return r.json()["token"]
        body = {"email": email, "password": PASSWORD, "name": name, "role": role}
        if class_code:
            body["class_code"] = class_code
        r = client.post("/api/auth/signup", json=body)
        assert r.status_code == 201, r.text
        return r.json()["token"]

    prof = login_or_signup("prof@demo.edu", "Prof Demo", "teacher")
    classes = client.get("/api/classes", headers=h(prof)).json()
    klass = next((c for c in classes if c["name"] == "Writing 101"), None)
    if klass is None:
        klass = client.post("/api/classes", json={"name": "Writing 101"}, headers=h(prof)).json()
    db = client.app.state.db
    db.exec("UPDATE classes SET class_code = ? WHERE class_id = ?", (CLASS_CODE, klass["class_id"]))

    detail = client.get(f"/api/classes/{klass['class_id']}", headers=h(prof)).json()
    assignment = next((a for a in detail["assignments"] if a["title"] == "Position paper"), None)
    if assignment is None:
        assignment = client.post("/api/assignments", json={
            "class_id": klass["class_id"], "title": "Position paper",
            "instructions": "Argue one position on a contested question in your field. 500-900 words, cite at least two sources.",
            "due_ms": int(time.time() * 1000) + 7 * 86_400_000, "points": 100,
        }, headers=h(prof)).json()

    ana = login_or_signup("ana@demo.edu", "Ana Lee", "student", CLASS_CODE)
    ben = login_or_signup("ben@demo.edu", "Ben Ortiz", "student", CLASS_CODE)
    login_or_signup("cara@demo.edu", "Cara Nguyen", "student", CLASS_CODE)
    for tok in (ana, ben):
        client.post("/api/classes/join", json={"class_code": CLASS_CODE}, headers=h(tok))

    sub = client.post("/api/submissions/start", json={"assignment_id": assignment["assignment_id"]}, headers=h(ben)).json()
    if sub["status"] == "draft":
        led = client.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=h(ben)).json()
        if led["event_count"] == 0:
            events = human_ledger(ESSAY, led["genesis"])
            for i in range(0, len(events), 500):
                batch = events[i:i + 500]
                so_far = replay(events[:i + len(batch)])
                r = client.post("/v1/ingest", headers=h(ben), json={
                    "session_id": led["session_id"], "events": batch,
                    "content_sha256": hashlib.sha256(so_far.encode()).hexdigest(), "content_len": len(so_far)})
                assert r.status_code == 200 and r.json()["replay_ok"], r.text
        r = client.post(f"/api/submissions/{sub['submission_id']}/submit", headers=h(ben),
                        json={"session_id": led["session_id"], "text": ESSAY})
        assert r.status_code == 200, r.text
        print(f"Ben's essay submitted: level {r.json()['certificate']['assurance_level']}, "
              f"{r.json()['certificate']['event_count']} events, verdict {r.json()['submission']['integrity']['verdict']}")
    else:
        print("Ben's essay already submitted.")

    print(f"""
Seeded. Log in at http://localhost:9100/login  (password for everyone: {PASSWORD})
  teacher  prof@demo.edu      class "Writing 101", code {CLASS_CODE}, assignment "Position paper"
  student  ana@demo.edu       nothing submitted yet — write live in the demo
  student  ben@demo.edu       essay submitted (synthetic human ledger)
  student  cara@demo.edu      nothing submitted yet
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
