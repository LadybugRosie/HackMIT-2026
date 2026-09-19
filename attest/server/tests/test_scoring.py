from attest.models import Signal
from attest.scoring import aggregate, build_warnings, composition_scores


def sig(name, verdict):
    return Signal(name=name, verdict=verdict, confidence=0.5, label=name)


NAMES = ["inter_key_interval", "typed_speed", "transcription_cadence", "revision_effort", "edit_locality"]


def test_composition_scores_cap_external_penalty():
    assert composition_scores({"typed": 1.0, "external": 0.0}).trust == 100
    assert composition_scores({"typed": 0.5, "external": 0.5}).trust == 60
    assert composition_scores({"typed": 0.0, "external": 1.0}).trust == 60
    assert composition_scores({"typed": 0.42, "external": 0.1}).composition == 42


def test_all_genuine_is_genuine():
    v, c = aggregate([sig(n, "genuine") for n in NAMES])
    assert v == "genuine" and c >= 0.9


def test_three_unmeasured_forces_review():
    v, c = aggregate([sig(n, "insufficient_data") for n in NAMES[:3]] + [sig(n, "genuine") for n in NAMES[3:]])
    assert v == "review"


def test_one_suspicious_is_review_not_suspicious():
    v, _ = aggregate([sig(NAMES[0], "suspicious")] + [sig(n, "genuine") for n in NAMES[1:]])
    assert v == "review"


def test_two_heavy_suspicious_is_suspicious():
    v, _ = aggregate([sig("typed_speed", "suspicious"), sig("transcription_cadence", "suspicious"),
                      sig("inter_key_interval", "genuine"), sig("revision_effort", "genuine"), sig("edit_locality", "genuine")])
    assert v == "suspicious"


def test_two_light_suspicious_stay_review():
    v, _ = aggregate([sig("revision_effort", "suspicious"), sig("edit_locality", "suspicious"),
                      sig("inter_key_interval", "genuine"), sig("typed_speed", "genuine"), sig("transcription_cadence", "genuine")])
    assert v == "review"


def test_warnings_are_neutral_and_coverage_aware():
    w = build_warnings({"external": 0.4}, [sig("typed_speed", "suspicious")], "suspicious")
    codes = [x.code for x in w]
    assert codes == ["external_content", "typed_speed"]
    assert all("cheat" not in x.reason.lower() for x in w)
    assert [x.code for x in build_warnings({"external": 0.0}, [], "review")] == ["needs_review"]
    assert build_warnings({"external": 0.0}, [sig("x", "genuine")], "genuine") == []
