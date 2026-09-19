"""Stage 3 (L2): crypto primitives, timestamp tokens, WebAuthn verification, and the engine path
enroll -> checkpoint -> finalize -> L2 certificate -> offline verify, using a software authenticator."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from attest.attestors import offline_attestors, timestamp as ts
from attest.attestors.webauthn import WebAuthnAttestor, b64url_decode, parse_registration
from attest.certificate import verify_certificate
from attest.chain import sha256_hex
from attest.crypto import cbor, der, ec
from attest.main import create_app
from attest.models import Certificate
from attest.settings import Settings

from conftest import build_chain, typed
from fake_authenticator import FakeAuthenticator

FIX = pathlib.Path(__file__).parent / "fixtures"
RP, ORIGIN = "localhost", "http://localhost:9100"


# -- crypto ----------------------------------------------------------------------------

def test_ec_sign_verify_both_curves():
    for curve, hname in ((ec.P256, "sha256"), (ec.P384, "sha512")):
        d = ec.generate_private(curve)
        pub = ec.public_from_private(d, curve)
        msg = os.urandom(40)
        sig = ec.sign(d, hashlib.new(hname, msg).digest(), curve)
        assert ec.verify_hashed(pub, hname, msg, sig, curve)
        assert not ec.verify_hashed(pub, hname, msg + b"!", sig, curve)
        assert not ec.verify_hashed(pub, hname, msg, (sig[0], sig[1] ^ 1), curve)
        assert ec.decode_uncompressed(ec.encode_uncompressed(pub, curve), curve) == pub
        assert ec.sig_from_der(ec.sig_to_der(sig)) == sig


@pytest.mark.skipif(pytest.importorskip("cryptography", reason="cross-check needs cryptography") is None, reason="")
def test_ec_matches_reference_library():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec as ref
    for _ in range(5):
        k = ref.generate_private_key(ref.SECP256R1())
        nums = k.public_key().public_numbers()
        msg = os.urandom(64)
        sig = k.sign(msg, ref.ECDSA(hashes.SHA256()))
        assert ec.verify_sha256((nums.x, nums.y), msg, ec.sig_from_der(sig))


def test_der_and_cbor_round_trips():
    for n in (0, 1, 127, 128, 255, 256, 2**64, 2**521 - 1):
        assert der.Reader(der.encode_integer(n)).read_integer() == n
    for oid in ("1.2.840.113549.1.1.11", "2.16.840.1.101.3.4.2.1", "1.3.132.0.34"):
        assert der.Reader(der.encode_oid(oid)).read().oid() == oid
    obj = {1: 2, 3: -7, -1: 1, -2: b"\x01" * 32, "fmt": "none", "arr": [1, "x", None, True, False]}
    assert cbor.decode(cbor.encode(obj)) == obj


# -- RFC 3161 --------------------------------------------------------------------------

def test_timestamp_request_encoding():
    req = der.Reader(ts.build_request(b"\x11" * 32, nonce=12345)).read_sequence()
    assert req.read_integer() == 1
    imprint = req.read_sequence()
    assert der.Reader(imprint.expect(der.SEQUENCE).body).expect(der.OID).oid() == ts.OID_SHA256
    assert imprint.expect(der.OCTET_STRING).body == b"\x11" * 32
    assert req.read_integer() == 12345
    assert req.expect(der.BOOLEAN).body == b"\xff"


def test_real_freetsa_token_verifies_offline():
    raw = (FIX / "freetsa_response.der").read_bytes()
    head = (FIX / "freetsa_response.head").read_text().strip()
    token = ts.parse_response(raw)
    assert token.status == 0 and token.gen_time.startswith("2026-")
    ok, detail = ts.verify_token(token, bytes.fromhex(head), set(ts.KNOWN_TSAS))
    assert ok, detail
    assert ts.verify_token(token, b"\x00" * 32, set(ts.KNOWN_TSAS)) == (False, "token is not over this chain head")
    assert not ts.verify_token(token, bytes.fromhex(head), set())[0]  # unpinned TSA is not trusted
    bad = bytearray(raw)
    bad[raw.rfind(token.signature) + 12] ^= 0x01  # inside r, past the DER headers
    assert ts.verify_token(ts.parse_response(bytes(bad)), bytes.fromhex(head), set(ts.KNOWN_TSAS))[1] == "TSA signature does not verify"
    res = ts.TimestampAttestor().verify(bytes.fromhex(head), {"kind": "timestamp", "head": head, "token": base64.b64encode(raw).decode()})
    assert res.ok and res.level == "L1" and res.data["tsa"].startswith("FreeTSA")


# -- WebAuthn --------------------------------------------------------------------------

def test_webauthn_registration_and_assertion():
    auth = FakeAuthenticator(RP, ORIGIN)
    challenge = os.urandom(32)
    reg = auth.create(challenge)
    cred = parse_registration(reg["attestation_object"], reg["client_data_json"], challenge, RP, [ORIGIN])
    assert cred["public_key"]["crv"] == "P-256" and cred["uv_at_enroll"]
    with pytest.raises(ValueError):
        parse_registration(reg["attestation_object"], reg["client_data_json"], os.urandom(32), RP, [ORIGIN])
    with pytest.raises(ValueError):
        parse_registration(reg["attestation_object"], reg["client_data_json"], challenge, "evil.example", [ORIGIN])

    head = os.urandom(32)
    att = {"kind": "webauthn", "head": head.hex(), **auth.get(head)}
    a = WebAuthnAttestor(RP, [ORIGIN], lookup=lambda cid: cred if cid == cred["credential_id"] else None)
    ok = a.verify(head, att)
    assert ok.ok and ok.level == "L2" and ok.data["uv"]
    assert not a.verify(os.urandom(32), att).ok
    assert a.verify(head, {**att, **auth.get(head, tamper_signature=True)}).detail == "signature does not verify"
    assert "origin" in a.verify(head, {**att, **auth.get(head, origin="http://evil")}).detail
    assert not a.verify(head, {**att, "credential_id": "nope"}).ok
    assert not a.verify(head, {**att, **auth.get(head, uv=False)}).data.get("uv", True)
    offline = WebAuthnAttestor()  # keys come from the record
    assert offline.verify(head, {**att, "public_key": cred["public_key"], "rp_id": RP}).ok
    assert not offline.verify(head, {**att, "public_key": {**cred["public_key"], "y": "00" * 32}, "rp_id": RP}).ok


# -- engine API: the whole L2 path ----------------------------------------------------------

@pytest.fixture
def app_client():
    # TSA_URL="" keeps tests offline; the timestamp path is covered by the fixture test above.
    return TestClient(create_app(Settings(STORE="memory", TSA_URL="", WEBAUTHN_RP_ID=RP, WEBAUTHN_ORIGINS=[ORIGIN])))


def enroll(client: TestClient, session_id: str, auth: FakeAuthenticator, headers=None) -> str:
    opts = client.get(f"/v1/session/{session_id}/enroll/options", headers=headers).json()
    assert opts["rp"]["id"] == RP and opts["authenticatorSelection"]["userVerification"] == "required"
    r = client.post(f"/v1/session/{session_id}/enroll", json=auth.create(b64url_decode(opts["challenge"])), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["credential_id"]


def ingest(client, session_id, genesis, raw, start_seq=0, prev=None, headers=None):
    events = build_chain(prev or genesis, raw, start_seq)
    text_events = events
    r = client.post("/v1/ingest", json={"session_id": session_id, "events": events,
                                        "content_sha256": sha256_hex(_replay_text(client, session_id, events)),
                                        "content_len": len(_replay_text(client, session_id, events))}, headers=headers)
    assert r.status_code == 200, r.text
    return events, r.json()


def _replay_text(client, session_id, new_events):
    from attest.replay import replay
    got = client.get(f"/v1/session/{session_id}/events").json()["events"]
    return replay(got + new_events)


def test_l2_end_to_end_and_offline_verify(app_client):
    c = app_client
    s = c.post("/v1/session/start", json={}).json()
    sid, genesis = s["session_id"], s["genesis"]
    auth = FakeAuthenticator(RP, ORIGIN)
    cred_id = enroll(c, sid, auth)
    assert c.get(f"/v1/session/{sid}/credentials").json()[0]["credential_id"] == cred_id

    events, res = ingest(c, sid, genesis, typed("Hello, attested world. "))
    mid_head = res["chain_head"]
    # checkpoint over the current head
    r = c.post(f"/v1/session/{sid}/attest", json={"head": mid_head, **auth.get(bytes.fromhex(mid_head), uv=False)})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["ok"] and r.json()["level_if_sealed_now"] == "L2"
    # a head that never existed is refused; a signature over a wrong head is refused
    bogus = os.urandom(32).hex()
    assert c.post(f"/v1/session/{sid}/attest", json={"head": bogus, **auth.get(bytes.fromhex(bogus))}).status_code == 409
    assert c.post(f"/v1/session/{sid}/attest", json={"head": mid_head, **auth.get(os.urandom(32))}).status_code == 400
    # stranger's key is unknown
    other = FakeAuthenticator(RP, ORIGIN)
    assert c.post(f"/v1/session/{sid}/attest", json={"head": mid_head, **other.get(bytes.fromhex(mid_head))}).status_code == 404

    # keep typing: the checkpoint is now an intermediate head; sealing now would be L1
    more, res2 = ingest(c, sid, genesis, typed("More.", start_pos=23, start_ts=1_700_000_100_000), start_seq=len(events), prev=events[-1]["hash"])
    final_head = res2["chain_head"]
    text = "Hello, attested world. More."
    cert_l1 = c.post(f"/v1/session/{sid}/finalize", json={"final_text": text})
    # finalize is idempotent and would freeze L1 — so do NOT finalize yet; instead sign the final head first.
    assert cert_l1.status_code == 200 and cert_l1.json()["assurance_level"] == "L1"
    assert cert_l1.json()["claims"]["attestation"]["device_checkpoints"] == 1
    assert not cert_l1.json()["claims"]["attestation"]["final_head_signed"]

    # New session: sign the final head *before* finalizing -> L2
    s2 = c.post("/v1/session/start", json={}).json()
    sid2, gen2 = s2["session_id"], s2["genesis"]
    auth2 = FakeAuthenticator(RP, ORIGIN)
    enroll(c, sid2, auth2)
    ev2, r2 = ingest(c, sid2, gen2, typed("Sealed on device."))
    head2 = r2["chain_head"]
    a = c.post(f"/v1/session/{sid2}/attest", json={"head": head2, **auth2.get(bytes.fromhex(head2), uv=True)}).json()
    assert a["level_if_sealed_now"] == "L2"
    cert = c.post(f"/v1/session/{sid2}/finalize", json={"final_text": "Sealed on device."}).json()
    assert cert["assurance_level"] == "L2"
    summ = cert["claims"]["attestation"]
    assert summ["final_head_signed"] and summ["uv_at_seal"] and summ["device_checkpoints"] == 1
    assert len(cert["attestations"]) == 1 and cert["attestations"][0]["public_key"]["x"]
    # sealed: no more signatures
    assert c.post(f"/v1/session/{sid2}/attest", json={"head": head2, **auth2.get(bytes.fromhex(head2))}).status_code == 409

    # verify via API (certificate + ledger) and purely offline (no store, no lookup)
    ledger = c.get(f"/v1/session/{sid2}/events").json()["events"]
    v = c.post("/v1/verify", json={"certificate": cert, "text": "Sealed on device.", "events": ledger}).json()
    assert v["ok"] and v["assurance_level"] == "L2"
    names = {ch["name"]: ch for ch in v["checks"]}
    assert names["webauthn[0]"]["ok"] and names["assurance_level"]["ok"]
    ok, level, checks = verify_certificate(Certificate(**cert), "Sealed on device.", ledger)
    assert ok and level == "L2"
    # certificate-only verification still checks the signature over the final head
    ok2, level2, checks2 = verify_certificate(Certificate(**cert), "Sealed on device.")
    assert ok2 and level2 == "L2"

    # forgeries: claim L2 without a signature; swap in a different key; tamper the signature
    forged = {**cert, "assurance_level": "L2", "attestations": []}
    ok3, level3, checks3 = verify_certificate(Certificate(**forged), "Sealed on device.", ledger)
    assert not ok3 and {ch.name: ch for ch in checks3}["assurance_level"].detail.startswith("attestations support L1")
    swapped = json.loads(json.dumps(cert))
    swapped["attestations"][0]["public_key"] = {"crv": "P-256", **{k: f"{v:064x}" for k, v in zip("xy", FakeAuthenticator().pub)}}
    ok4, _l, checks4 = verify_certificate(Certificate(**swapped), "Sealed on device.", ledger)
    assert not ok4 and not {ch.name: ch for ch in checks4}["webauthn[0]"].ok
    tampered = json.loads(json.dumps(cert))
    sig = bytearray(b64url_decode(tampered["attestations"][0]["signature"]))
    sig[-1] ^= 1
    tampered["attestations"][0]["signature"] = base64.urlsafe_b64encode(bytes(sig)).decode().rstrip("=")
    assert not verify_certificate(Certificate(**tampered), "Sealed on device.", ledger)[0]


def test_enroll_requires_fresh_challenge_and_matching_origin(app_client):
    c = app_client
    sid = c.post("/v1/session/start", json={}).json()["session_id"]
    auth = FakeAuthenticator(RP, ORIGIN)
    assert c.post(f"/v1/session/{sid}/enroll", json=auth.create(os.urandom(32))).status_code == 409  # no options call
    opts = c.get(f"/v1/session/{sid}/enroll/options").json()
    evil = FakeAuthenticator(RP, "http://evil.example")
    r = c.post(f"/v1/session/{sid}/enroll", json=evil.create(b64url_decode(opts["challenge"])))
    assert r.status_code == 400 and "origin" in r.json()["detail"]["detail"]
    opts = c.get(f"/v1/session/{sid}/enroll/options").json()  # challenge is single-use; get a new one
    assert c.post(f"/v1/session/{sid}/enroll", json=auth.create(b64url_decode(opts["challenge"]))).status_code == 201
