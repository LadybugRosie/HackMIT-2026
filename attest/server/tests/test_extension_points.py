from attest.attestors import AttestationResult, compute_assurance_level, verify_attestations
from attest.settings import Settings
from attest.stylometry import StubStylometryClient, get_client

from synth import SAMPLE


class FakeAttestor:
    kind = "fake"

    def __init__(self, ok: bool, level: str):
        self.ok, self.level = ok, level

    def verify(self, statement, attestation):
        return AttestationResult(kind=self.kind, ok=self.ok, level=self.level, detail="fake")


def test_levels_only_rise_through_verified_attestations():
    ok_l2 = AttestationResult("webauthn", True, "L2")
    ok_l3 = AttestationResult("hid", True, "L3")
    bad_l3 = AttestationResult("hid", False, "L3")
    assert compute_assurance_level("L1", []) == "L1"
    assert compute_assurance_level("L1", [ok_l2]) == "L2"
    assert compute_assurance_level("L1", [ok_l3]) == "L1"          # cannot skip L2
    assert compute_assurance_level("L1", [ok_l3, ok_l2]) == "L3"   # order-independent
    assert compute_assurance_level("L1", [ok_l2, bad_l3]) == "L2"  # failed attestation adds nothing
    assert compute_assurance_level("none", [ok_l2]) == "none"


def test_unknown_attestation_kind_fails_closed():
    res = verify_attestations({"fake": FakeAttestor(True, "L2")}, b"head",
                              [{"kind": "fake"}, {"kind": "mystery"}])
    assert [r.ok for r in res] == [True, False]
    assert res[1].detail == "no verifier for this kind"


def test_stub_stylometry_is_deterministic_and_degrades():
    client = get_client(Settings(STYLOMETRY_BASE=""))
    assert isinstance(client, StubStylometryClient)
    a = client.verify(SAMPLE, "alice")
    b = client.verify(SAMPLE, "alice")
    assert a == b and a.verdict in ("verified", "flagged") and 0.5 <= a.score <= 1.0
    assert client.verify("too short", "alice").verdict == "unknown"


def test_http_stylometry_unreachable_is_unknown_not_error():
    client = get_client(Settings(STYLOMETRY_BASE="http://127.0.0.1:9"))
    res = client.verify(SAMPLE, "alice", "cs101")
    assert res.verdict == "unknown" and "unreachable" in res.detail
