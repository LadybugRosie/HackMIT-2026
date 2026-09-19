"""Classroom + L2: a student's key is enrolled under their user id and works across their bound
sessions; teachers and other students cannot enroll or sign; submit yields an L2 certificate that the
review page's server-verify confirms."""
from __future__ import annotations

import os

from attest.attestors.webauthn import b64url_decode
from attest.chain import sha256_hex

from classroom_helpers import auth, capp, signup  # noqa: F401
from conftest import build_chain, typed
from fake_authenticator import FakeAuthenticator

RP, ORIGIN = "localhost", "http://localhost:9100"


def _setup(capp):
    t = signup(capp, "prof@demo.edu", "teacher")
    klass = capp.post("/api/classes", json={"name": "W"}, headers=auth(t["token"])).json()
    a = capp.post("/api/assignments", json={"class_id": klass["class_id"], "title": "E", "instructions": "",
                                             "settings": {"factcheck": False, "similarity": False}}, headers=auth(t["token"])).json()
    ana = signup(capp, "ana@demo.edu", class_code=klass["class_code"])
    ben = signup(capp, "ben@demo.edu", class_code=klass["class_code"])
    return t, a, ana, ben


def _draft(capp, token, assignment_id):
    sub = capp.post("/api/submissions/start", json={"assignment_id": assignment_id}, headers=auth(token)).json()
    led = capp.post(f"/api/submissions/{sub['submission_id']}/ledger", headers=auth(token)).json()
    return sub, led


def test_student_enrolls_signs_and_submits_l2(capp):
    capp.app.state.attest_settings.TSA_URL = ""  # offline
    t, a, ana, ben = _setup(capp)
    sub, led = _draft(capp, ana["token"], a["assignment_id"])
    sid = led["session_id"]
    device = FakeAuthenticator(RP, ORIGIN)

    # only the owner may enroll / read credentials / sign
    assert capp.get(f"/v1/session/{sid}/enroll/options").status_code == 401
    assert capp.get(f"/v1/session/{sid}/enroll/options", headers=auth(t["token"])).status_code == 404
    assert capp.get(f"/v1/session/{sid}/enroll/options", headers=auth(ben["token"])).status_code == 404
    opts = capp.get(f"/v1/session/{sid}/enroll/options", headers=auth(ana["token"])).json()
    r = capp.post(f"/v1/session/{sid}/enroll", json=device.create(b64url_decode(opts["challenge"])), headers=auth(ana["token"]))
    assert r.status_code == 201, r.text

    text = "Written and sealed on my own laptop."
    events = build_chain(led["genesis"], typed(text))
    capp.post("/v1/ingest", headers=auth(ana["token"]), json={"session_id": sid, "events": events,
                                                             "content_sha256": sha256_hex(text), "content_len": len(text)})
    head = events[-1]["hash"]
    assert capp.post(f"/v1/session/{sid}/attest", json={"head": head, **device.get(bytes.fromhex(head))},
                     headers=auth(ben["token"])).status_code == 404
    r = capp.post(f"/v1/session/{sid}/attest", json={"head": head, **device.get(bytes.fromhex(head))}, headers=auth(ana["token"]))
    assert r.status_code == 200 and r.json()["level_if_sealed_now"] == "L2", r.text

    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(ana["token"]), json={"session_id": sid, "text": text})
    assert r.status_code == 200, r.text
    assert r.json()["certificate"]["assurance_level"] == "L2"
    assert r.json()["verify"]["ok"] and r.json()["verify"]["assurance_level"] == "L2"

    # sealed: signing is refused (guard says not_draft before the engine says finalized)
    assert capp.post(f"/v1/session/{sid}/attest", json={"head": head, **device.get(bytes.fromhex(head))},
                     headers=auth(ana["token"])).status_code == 409

    # the teacher's server re-verify sees L2 with named attestation checks
    v = capp.post(f"/api/review/submissions/{sub['submission_id']}/verify", headers=auth(t["token"])).json()
    assert v["ok"] and v["assurance_level"] == "L2"
    assert any(c["name"] == "webauthn[0]" and c["ok"] for c in v["checks"])

    # the same device key carries over to Ana's next assignment without re-enrolling
    a2 = capp.post("/api/assignments", json={"class_id": a["class_id"], "title": "E2", "instructions": "",
                                              "settings": {"factcheck": False, "similarity": False}}, headers=auth(t["token"])).json()
    sub2, led2 = _draft(capp, ana["token"], a2["assignment_id"])
    creds = capp.get(f"/v1/session/{led2['session_id']}/credentials", headers=auth(ana["token"])).json()
    assert [c["credential_id"] for c in creds] == [r.json()["certificate"]["attestations"][0]["credential_id"]]


def test_unsigned_submission_stays_l1(capp):
    capp.app.state.attest_settings.TSA_URL = ""
    t, a, ana, _ben = _setup(capp)
    sub, led = _draft(capp, ana["token"], a["assignment_id"])
    text = "No device key here."
    events = build_chain(led["genesis"], typed(text))
    capp.post("/v1/ingest", headers=auth(ana["token"]), json={"session_id": led["session_id"], "events": events,
                                                             "content_sha256": sha256_hex(text), "content_len": len(text)})
    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(ana["token"]),
                  json={"session_id": led["session_id"], "text": text})
    assert r.status_code == 200 and r.json()["certificate"]["assurance_level"] == "L1"
    assert r.json()["certificate"]["claims"]["attestation"]["device_checkpoints"] == 0


def test_hid_witness_in_classroom_owner_only(capp):
    from fake_hid import FakeHelper
    from test_hid import kd_ts, typed_with_kd
    capp.app.state.attest_settings.TSA_URL = ""
    t, a, ana, ben = _setup(capp)
    sub, led = _draft(capp, ana["token"], a["assignment_id"])
    sid = led["session_id"]
    device, helper = FakeAuthenticator(RP, ORIGIN), FakeHelper()

    def challenge(token):
        return b64url_decode(capp.get(f"/v1/session/{sid}/enroll/options", headers=auth(token)).json()["challenge"])

    assert capp.post(f"/v1/session/{sid}/enroll-hid", json=helper.enroll_payload(os.urandom(32)), headers=auth(ben["token"])).status_code == 404
    assert capp.post(f"/v1/session/{sid}/enroll", json=device.create(challenge(ana["token"])), headers=auth(ana["token"])).status_code == 201
    assert capp.post(f"/v1/session/{sid}/enroll-hid", json=helper.enroll_payload(challenge(ana["token"])), headers=auth(ana["token"])).status_code == 201

    text = "Every one of these keystrokes was seen by the keyboard driver."
    events = build_chain(led["genesis"], typed_with_kd(text))
    capp.post("/v1/ingest", headers=auth(ana["token"]), json={"session_id": sid, "events": events,
                                                             "content_sha256": sha256_hex(text), "content_len": len(text)})
    root = events[-1]["hash"]
    sts = helper.witness(sid, led["genesis"], root, kd_ts(events))
    assert capp.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts},
                     headers=auth(t["token"])).status_code == 404  # teacher cannot witness for a student
    r = capp.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts}, headers=auth(ana["token"]))
    assert r.status_code == 200 and r.json()["final"], r.text
    capp.post(f"/v1/session/{sid}/attest", json={"head": root, **device.get(bytes.fromhex(root))}, headers=auth(ana["token"]))
    r = capp.post(f"/api/submissions/{sub['submission_id']}/submit", headers=auth(ana["token"]), json={"session_id": sid, "text": text})
    assert r.status_code == 200 and r.json()["certificate"]["assurance_level"] == "L3", r.text
    v = capp.post(f"/api/review/submissions/{sub['submission_id']}/verify", headers=auth(t["token"])).json()
    assert v["ok"] and v["assurance_level"] == "L3" and any(c["name"] == "hid_correlation" and c["ok"] for c in v["checks"])
