"""Stage 4 (L3): hardware-witness verification, the L2 -> L3 policy, the engine endpoints, and
the offline CLI — all with the software helper in fake_hid.py (no Input Monitoring needed)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from attest.attestors import offline_attestors
from attest.attestors.hid import HidAttestor, assess_hid, canon, statement_hash
from attest.attestors.policy import assess_attestations
from attest.attestors.webauthn import b64url_decode
from attest.certificate import verify_certificate
from attest.chain import sha256_hex
from attest.main import create_app
from attest.models import Certificate
from attest.settings import Settings

from conftest import build_chain
from fake_authenticator import FakeAuthenticator
from fake_hid import FakeHelper, random_head

RP, ORIGIN = "localhost", "http://localhost:9100"
T0 = 1_700_000_000_000


def typed_with_kd(text: str, start_ts: int = T0, gap: int = 180):
    """Raw ledger events for typing `text`: a content-free kd, then the edit, per character."""
    out, ts = [], start_ts
    for n, ch in enumerate(text):
        out.append({"ts": ts, "p": 0, "d": 0, "i": "", "k": "kd"})
        out.append({"ts": ts + 5, "p": n, "d": 0, "i": ch, "k": "type"})
        ts += gap
    return out


def kd_ts(events):
    return [e["ts"] for e in events if e["k"] == "kd"]


# -- statement format ---------------------------------------------------------------------------

def test_canon_is_key_sorted_compact_and_ignores_hash_sig():
    st = {"v": 1, "sid": "s", "seg": 0, "seq": 0, "t0": 1, "t1": 2, "kd": 3, "devices": [{"builtin": True, "kd": 3, "id": "x"}],
          "idle_ms": 0, "cdhash": "c", "anchor": {"head": "h"}, "final": False, "prev": "p", "hash": "zzz", "sig": "yyy", "extra": 1}
    c = canon(st).decode()
    assert c.startswith('{"anchor":{"head":"h"},"cdhash":"c","devices":[{"builtin":true,"id":"x","kd":3}]')
    assert '"hash"' not in c and '"sig"' not in c and '"extra"' not in c and " " not in c
    st2 = {**st, "hash": statement_hash(st)}
    assert statement_hash({**st2, "kd": 4}) != st2["hash"]


def test_batch_attestor_catches_tamper_and_breaks():
    h = FakeHelper()
    sts = h.witness("s", random_head(), random_head(), [T0 + 100, T0 + 300])
    a = HidAttestor(None)
    assert a.verify(b"", h.batch(sts)).ok
    tampered = [dict(s) for s in sts]
    tampered[0]["kd"] += 1
    assert "hash mismatch" in a.verify(b"", h.batch(tampered)).detail
    resigned = [dict(s) for s in sts]
    resigned[0]["kd"] += 1
    resigned[0]["hash"] = statement_hash(resigned[0])
    assert "signature does not verify" in a.verify(b"", h.batch(resigned)).detail
    other = FakeHelper()
    assert not a.verify(b"", {**h.batch(sts), "public_key": other.batch(sts)["public_key"]}).ok
    assert "chain break" in a.verify(b"", h.batch([sts[0], sts[2]])).detail if len(sts) > 2 else True


# -- assessment rules ------------------------------------------------------------------------------

def _ledger(text="The quick brown fox jumps over the lazy dog and keeps typing for a while longer."):
    genesis = random_head()
    events = build_chain(genesis, typed_with_kd(text))
    heads = {genesis, *(e["hash"] for e in events)}
    return genesis, events, heads, events[-1]["hash"]


def _assess(h, sts, events, heads, root, trusted=()):
    batches = [h.batch(sts)]
    results = [HidAttestor(None).verify(b"", b) for b in batches]
    return assess_hid(batches, results, events, root, heads, trusted)


def test_honest_witness_supports_l3():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    sts = h.witness("s", genesis, root, kd_ts(events), extra_per_window=3)
    s = _assess(h, sts, events, heads, root)
    assert s.ok and s.supports_l3, s.reasons
    assert s.coverage_ratio == 1.0 and s.ledger_kd == len(kd_ts(events)) and s.hw_kd > s.ledger_kd
    assert s.helper_trusted is None  # nothing pinned -> flagged, not failed
    assert {n: ok for n, ok, _ in s.checks}["hid_helper"] is True
    assert s.devices[0]["builtin"] and s.devices[0]["share"] == 1.0
    s2 = _assess(h, sts, events, heads, root, trusted=[h.cdhash])
    assert s2.helper_trusted is True
    s3 = _assess(h, sts, events, heads, root, trusted=["deadbeef"])
    assert s3.helper_trusted is False and not s3.ok


def test_injection_window_is_named_and_blocks_l3():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    sts = h.witness("s", genesis, root, kd_ts(events), inject_window=1)
    s = _assess(h, sts, events, heads, root)
    assert not s.supports_l3 and len(s.injection_windows) == 1
    w = s.injection_windows[0]
    assert w["seq"] == 1 and w["hw_kd"] == 0 and w["ledger_kd"] >= 8
    assert any("injection" in r for r in s.reasons)
    assert dict((n, ok) for n, ok, _ in s.checks)["hid_correlation"] is False


def test_gap_and_missing_final_and_wrong_anchor():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    checks = lambda s: {n: ok for n, ok, _ in s.checks}  # noqa: E731
    gap = _assess(h, h.witness("s", genesis, root, kd_ts(events), drop_window=1), events, heads, root)
    assert not gap.supports_l3 and checks(gap)["hid_chain"] is False
    nofinal = _assess(h, h.witness("s", genesis, root, kd_ts(events), no_final=True), events, heads, root)
    assert not nofinal.supports_l3 and checks(nofinal)["hid_anchors"] is False
    foreign = _assess(h, h.witness("s", random_head(), root, kd_ts(events)), events, heads, root)
    assert not foreign.supports_l3 and checks(foreign)["hid_anchors"] is False
    stale = _assess(h, h.witness("s", genesis, events[3]["hash"], kd_ts(events)), events, heads, root)
    assert not stale.supports_l3 and "chain root" in dict((n, d) for n, _, d in stale.checks)["hid_anchors"]


def test_unwitnessed_prefix_fails_coverage():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    ts = kd_ts(events)
    sts = h.witness("s", events[10]["hash"], root, ts, t_start=ts[6])  # helper started after 6 keystrokes
    s = _assess(h, sts, events, heads, root)
    assert not s.supports_l3 and s.coverage_ratio < 1.0 and "coverage" in s.reasons[0]


def test_idle_lie_and_external_device_are_reported():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    lie = _assess(h, h.witness("s", genesis, root, kd_ts(events), idle_lie_window=0), events, heads, root)
    assert dict((n, ok) for n, ok, _ in lie.checks)["hid_consistency"] is False
    gadget = _assess(h, h.witness("s", genesis, root, kd_ts(events), gadget_share=0.9), events, heads, root)
    assert gadget.supports_l3  # a real HID device passes; the certificate makes it visible
    ext = next(d for d in gadget.devices if not d["builtin"])
    assert ext["share"] > 0.8


def test_certificate_only_mode_checks_structure_not_correlation():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    sts = h.witness("s", genesis, root, kd_ts(events))
    s = assess_hid([h.batch(sts)], [HidAttestor(None).verify(b"", h.batch(sts))], None, root, None)
    assert s.supports_l3 and not s.correlation_checked
    assert dict((n, d) for n, _, d in s.checks)["hid_correlation"].startswith("not re-checked")


def test_policy_requires_l2_for_l3():
    genesis, events, heads, root = _ledger()
    h = FakeHelper()
    hid = h.batch(h.witness("s", genesis, root, kd_ts(events)))
    level, _r, summary = assess_attestations([hid], offline_attestors(), root, heads, events=events)
    assert level == "L1" and summary["hid"]["supports_l3"]  # witness fine, but no device seal
    auth = FakeAuthenticator(RP, ORIGIN)
    wa = {"kind": "webauthn", "head": root, **auth.get(bytes.fromhex(root)), "rp_id": RP,
          "public_key": {"crv": "P-256", "x": f"{auth.pub[0]:064x}", "y": f"{auth.pub[1]:064x}"}}
    level, _r, summary = assess_attestations([wa, hid], offline_attestors(), root, heads, events=events)
    assert level == "L3"
    bad = h.batch(h.witness("s", genesis, root, kd_ts(events), inject_window=0))
    level, _r, summary = assess_attestations([wa, bad], offline_attestors(), root, heads, events=events)
    assert level == "L2" and summary["hid"]["injection_windows"]


# -- engine API end to end -----------------------------------------------------------------------

@pytest.fixture
def app_client():
    return TestClient(create_app(Settings(STORE="memory", TSA_URL="", WEBAUTHN_RP_ID=RP, WEBAUTHN_ORIGINS=[ORIGIN])))


def _enroll_both(c, sid, auth, helper):
    opts = c.get(f"/v1/session/{sid}/enroll/options").json()
    assert c.post(f"/v1/session/{sid}/enroll", json=auth.create(b64url_decode(opts["challenge"]))).status_code == 201
    opts = c.get(f"/v1/session/{sid}/enroll/options").json()
    r = c.post(f"/v1/session/{sid}/enroll-hid", json=helper.enroll_payload(b64url_decode(opts["challenge"])))
    assert r.status_code == 201 and r.json()["type"] == "hid", r.text
    creds = c.get(f"/v1/session/{sid}/credentials").json()
    assert {x["type"] for x in creds} == {"webauthn", "hid"}


def test_l3_end_to_end(app_client, tmp_path):
    c = app_client
    s = c.post("/v1/session/start", json={}).json()
    sid, genesis = s["session_id"], s["genesis"]
    auth, helper = FakeAuthenticator(RP, ORIGIN), FakeHelper()
    _enroll_both(c, sid, auth, helper)

    text = "Typed for real, witnessed by hardware, sealed with Touch ID."
    events = build_chain(genesis, typed_with_kd(text))
    r = c.post("/v1/ingest", json={"session_id": sid, "events": events, "content_sha256": sha256_hex(text), "content_len": len(text)})
    assert r.status_code == 200, r.text
    root = events[-1]["hash"]

    # witness in two batches, then the terminal statement
    sts = helper.witness(sid, genesis, root, kd_ts(events))
    r1 = c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts[:2]})
    assert r1.status_code == 200 and r1.json()["accepted"] == 2 and not r1.json()["final"], r1.text
    # replay / skip / wrong key are refused
    assert c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts[:1]}).status_code == 409
    assert c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts[3:4]}).status_code == 409
    assert c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": "nope", "statements": sts[2:]}).status_code == 404
    r2 = c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts[2:]})
    assert r2.status_code == 200 and r2.json()["final"], r2.text
    assert r2.json()["hid"]["supports_l3"] and r2.json()["level_if_sealed_now"] == "L1"  # no device seal yet
    assert c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts[-1:]}).status_code == 409  # sealed

    a = c.post(f"/v1/session/{sid}/attest", json={"head": root, **auth.get(bytes.fromhex(root))}).json()
    assert a["level_if_sealed_now"] == "L3"
    cert = c.post(f"/v1/session/{sid}/finalize", json={"final_text": text}).json()
    assert cert["assurance_level"] == "L3"
    hid = cert["claims"]["attestation"]["hid"]
    assert hid["coverage_ratio"] == 1.0 and not hid["injection_windows"] and hid["helper_trusted"] is None
    ledger = c.get(f"/v1/session/{sid}/events").json()

    v = c.post("/v1/verify", json={"certificate": cert, "text": text, "events": ledger["events"]}).json()
    assert v["ok"] and v["assurance_level"] == "L3"
    names = {ch["name"]: ch for ch in v["checks"]}
    for n in ("hid_chain", "hid_anchors", "hid_helper", "hid_consistency", "hid_coverage", "hid_correlation", "assurance_level"):
        assert names[n]["ok"], names[n]
    # certificate-only still verifies structure
    ok, level, _ = verify_certificate(Certificate(**cert), text)
    assert ok and level == "L3"
    # forgery: claim L3 with the witness stripped
    forged = {**cert, "attestations": [a_ for a_ in cert["attestations"] if a_["kind"] != "hid"]}
    ok, _l, checks = verify_certificate(Certificate(**forged), text, ledger["events"])
    assert not ok and "support L2" in {ch.name: ch for ch in checks}["assurance_level"].detail

    # offline CLI with plain python3 (no venv): full L3 pass
    (tmp_path / "cert.json").write_text(json.dumps(cert))
    (tmp_path / "ledger.json").write_text(json.dumps(ledger))
    (tmp_path / "doc.txt").write_text(text)
    cli = Path(__file__).resolve().parents[2] / "verifier" / "attest_verify.py"
    out = subprocess.run([sys.executable if "python3" in sys.executable else "python3", str(cli), str(tmp_path / "cert.json"),
                          str(tmp_path / "doc.txt"), "--events", str(tmp_path / "ledger.json")], capture_output=True, text=True)
    assert out.returncode == 0 and "assurance level L3" in out.stdout and "[PASS] hid_correlation" in out.stdout, out.stdout + out.stderr


def test_injection_in_session_lands_at_l2(app_client):
    c = app_client
    s = c.post("/v1/session/start", json={}).json()
    sid, genesis = s["session_id"], s["genesis"]
    auth, helper = FakeAuthenticator(RP, ORIGIN), FakeHelper()
    _enroll_both(c, sid, auth, helper)
    text = "One honest paragraph. Then a paragraph that a script typed into the editor while nobody touched a key."
    events = build_chain(genesis, typed_with_kd(text))
    c.post("/v1/ingest", json={"session_id": sid, "events": events, "content_sha256": sha256_hex(text), "content_len": len(text)})
    root = events[-1]["hash"]
    sts = helper.witness(sid, genesis, root, kd_ts(events), inject_window=2)
    r = c.post(f"/v1/session/{sid}/attest-hid", json={"key_id": helper.key_id, "statements": sts})
    assert r.status_code == 200 and r.json()["hid"]["injection_windows"], r.text
    c.post(f"/v1/session/{sid}/attest", json={"head": root, **auth.get(bytes.fromhex(root))})
    cert = c.post(f"/v1/session/{sid}/finalize", json={"final_text": text}).json()
    assert cert["assurance_level"] == "L2"
    assert cert["claims"]["attestation"]["hid"]["injection_windows"][0]["seq"] == 2
    assert any("injection" in r for r in cert["claims"]["attestation"]["hid"]["reasons"])
