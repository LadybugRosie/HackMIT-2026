from attest.analysis import analyze
from attest.signals import build_context, run_all

from conftest import build_chain
from synth import SAMPLE, human_composition, paste_dump, scripted, transcription

G = "b" * 64


def by_name(signals):
    return {s.name: s for s in signals}


def test_human_composition_reads_genuine():
    events = build_chain(G, human_composition(SAMPLE))
    sig = by_name(run_all(build_context(events)))
    assert sig["inter_key_interval"].verdict == "genuine"
    assert sig["typed_speed"].verdict == "genuine"
    assert sig["transcription_cadence"].verdict == "genuine", sig["transcription_cadence"].label
    assert sig["revision_effort"].verdict == "genuine"
    assert sig["edit_locality"].verdict == "genuine"
    res = analyze(events)
    assert res.verdict == "genuine" and res.warnings == []
    assert res.scores.trust == 100 and res.mix.typed == 1.0


def test_transcription_cadence_flags_metronomic_chunks():
    events = build_chain(G, transcription(SAMPLE))
    sig = by_name(run_all(build_context(events)))
    cad = sig["transcription_cadence"]
    assert cad.verdict == "suspicious", cad.label
    assert cad.data["boundary_ratio"] < 0.35 and cad.data["burst_cv"] < 0.5
    assert sig["edit_locality"].verdict == "suspicious"  # strictly forward
    res = analyze(events)
    assert res.verdict == "suspicious"
    assert {w.code for w in res.warnings} >= {"transcription_cadence", "edit_locality"}


def test_scripted_input_is_caught_by_timing_and_speed():
    events = build_chain(G, scripted(SAMPLE, interval_ms=20))
    sig = by_name(run_all(build_context(events)))
    assert sig["inter_key_interval"].verdict == "suspicious"
    assert sig["typed_speed"].verdict == "suspicious"
    assert sig["typed_speed"].data["peak_typed_wpm"] > 200
    assert analyze(events).verdict == "suspicious"


def test_paste_dump_is_external_and_low_effort():
    events = build_chain(G, paste_dump(SAMPLE))
    res = analyze(events)
    assert res.mix.external == 1.0 and res.scores.trust == 60
    assert res.ext_spans[0].start == 0 and res.ext_spans[0].end == len(SAMPLE)
    sig = by_name(res.signals)
    assert sig["revision_effort"].verdict == "suspicious"
    assert any(w.code == "external_content" for w in res.warnings)


def test_short_session_is_insufficient_not_accused():
    events = build_chain(G, human_composition("Just a few words.", revisions=0))
    res = analyze(events)
    assert res.verdict == "review"  # downgraded because too little could be measured
    assert all(s.verdict == "insufficient_data" for s in res.signals)
    assert [w.code for w in res.warnings] == ["needs_review"]


def test_keydown_events_become_timing_source():
    ops = human_composition(SAMPLE)
    kd = [{"ts": o["ts"] - 5, "p": 0, "d": 0, "i": "", "k": "kd"} for o in ops if o["i"]]
    merged = sorted(ops + kd, key=lambda o: o["ts"])
    ctx = build_context(build_chain(G, merged))
    assert ctx.timing_source == "keydown" and len(ctx.keystroke_ts) == len(kd)
