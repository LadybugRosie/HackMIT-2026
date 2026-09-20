"""Issuer signatures: a certificate from *another* server — internally perfect — is not ours."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from attest.certificate import verify_certificate
from attest.chain import sha256_hex
from attest.issuer import Issuer, canon_certificate, verify_issuer
from attest.main import create_app
from attest.models import Certificate
from attest.settings import Settings

from conftest import build_chain, typed


def _finalize(client: TestClient, text: str):
    s = client.post("/v1/session/start", json={}).json()
    events = build_chain(s["genesis"], typed(text))
    client.post("/v1/ingest", json={"session_id": s["session_id"], "events": events, "content_sha256": sha256_hex(text), "content_len": len(text)})
    cert = client.post(f"/v1/session/{s['session_id']}/finalize", json={"final_text": text}).json()
    return cert, client.get(f"/v1/session/{s['session_id']}/events").json()["events"]


def test_certificate_is_signed_and_verifies_against_this_server():
    c = TestClient(create_app(Settings(STORE="memory", ISSUER_KEY_PATH="")))
    info = c.get("/v1/issuer").json()
    text = "Sealed by this server."
    cert, events = _finalize(c, text)
    assert cert["issuer"]["key_id"] == info["key_id"] and cert["issuer"]["public_key"] == info["public_key"]
    v = c.post("/v1/verify", json={"certificate": cert, "text": text, "events": events}).json()
    assert v["ok"] and {ch["name"]: ch for ch in v["checks"]}["issuer"]["detail"].startswith("issued by trusted key")


def test_certificate_from_another_server_fails_issuer_here():
    ours = TestClient(create_app(Settings(STORE="memory", ISSUER_KEY_PATH="")))
    theirs = TestClient(create_app(Settings(STORE="memory", ISSUER_KEY_PATH="")))
    text = "A perfectly consistent certificate — from someone else's server."
    cert, events = _finalize(theirs, text)
    # internally valid everywhere...
    ok, level, checks = verify_certificate(Certificate(**cert), text, events)
    assert ok and level == "L1" and {c.name: c for c in checks}["issuer"].ok
    # ...but not issued here
    v = ours.post("/v1/verify", json={"certificate": cert, "text": text, "events": events}).json()
    issuer = {ch["name"]: ch for ch in v["checks"]}["issuer"]
    assert not v["ok"] and not issuer["ok"] and "UNKNOWN issuer key" in issuer["detail"]


def test_tampering_after_issue_breaks_the_seal():
    c = TestClient(create_app(Settings(STORE="memory", ISSUER_KEY_PATH="")))
    text = "Tamper with me."
    cert, events = _finalize(c, text)
    forged = json.loads(json.dumps(cert))
    forged["assurance_level"] = "L3"  # inflate the level, keep the signature
    present, sig_ok, _t, detail = verify_issuer(forged, None)
    assert present and not sig_ok and "does not verify" in detail
    ok, _l, checks = verify_certificate(Certificate(**forged), text, events)
    assert not ok and not {ch.name: ch for ch in checks}["issuer"].ok


def test_unsigned_certificate_is_info_without_issuer_list_and_fails_with_one():
    c = TestClient(create_app(Settings(STORE="memory", ISSUER_KEY_PATH="")))
    text = "Issued before issuer keys existed."
    cert, events = _finalize(c, text)
    cert["issuer"] = None
    ok, level, checks = verify_certificate(Certificate(**cert), text, events)  # no issuer list
    by = {ch.name: ch for ch in checks}
    assert ok and by["issuer"].info and not by["issuer"].ok and "no issuer signature" in by["issuer"].detail
    v = c.post("/v1/verify", json={"certificate": cert, "text": text, "events": events}).json()  # server has a list
    assert not v["ok"]


def test_issuer_key_persists_across_restarts(tmp_path):
    path = str(tmp_path / "issuer.json")
    a = Issuer.load_or_create(path)
    b = Issuer.load_or_create(path)
    assert a.key_id == b.key_id and a.public_key_hex == b.public_key_hex
    cert = {"session_id": "x", "doc_sha256": "0" * 64, "assurance_level": "L1"}
    signed = {**cert, "issuer": a.sign(cert)}
    assert canon_certificate(signed) == canon_certificate(cert)
    assert verify_issuer(signed, {b.key_id: b.public_key_hex})[2] is True
