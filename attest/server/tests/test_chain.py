from __future__ import annotations

import copy

from hypothesis import given, settings as hsettings, strategies as st

from attest.chain import canon, link_hash, merkle_root, verify_chain
from attest.replay import replay

from conftest import build_chain, typed


def test_canon_is_deterministic_and_excludes_hash(genesis):
    ev = build_chain(genesis, typed("a"))[0]
    a = canon(ev)
    ev2 = dict(ev, hash="0" * 64)
    assert canon(ev2) == a
    assert b'"hash"' not in a
    # keys sorted, compact, raw utf-8
    assert a.startswith(b'{"d":0,"i":"a","k":"type","p":0,"prev":"')


def test_canon_keeps_unicode_raw(genesis):
    ev = build_chain(genesis, [{"i": "é🙂", "k": "type"}])[0]
    assert "é🙂".encode("utf-8") in canon(ev)


def test_valid_chain_verifies(genesis):
    events = build_chain(genesis, typed("hello"))
    res = verify_chain(events, genesis)
    assert res.ok and res.head == events[-1]["hash"]


def test_empty_chain_head_is_genesis(genesis):
    res = verify_chain([], genesis)
    assert res.ok and res.head == genesis


def test_wrong_genesis_fails(genesis):
    events = build_chain(genesis, typed("hi"))
    res = verify_chain(events, "f" * 64)
    assert not res.ok and res.index == 0


def test_single_char_edit_breaks_chain(genesis):
    events = build_chain(genesis, typed("hello"))
    events[2]["i"] = "X"
    res = verify_chain(events, genesis)
    assert not res.ok and res.index == 2 and "altered" in res.error


def test_dropped_event_breaks_chain(genesis):
    events = build_chain(genesis, typed("hello"))
    del events[1]
    res = verify_chain(events, genesis)
    assert not res.ok and res.index == 1


def test_reordered_events_break_chain(genesis):
    events = build_chain(genesis, typed("hello"))
    events[1], events[2] = events[2], events[1]
    assert not verify_chain(events, genesis).ok


def test_continuation_from_head(genesis):
    first = build_chain(genesis, typed("ab"))
    second = build_chain(first[-1]["hash"], typed("cd", start_pos=2), start_seq=2)
    assert verify_chain(second, first[-1]["hash"], start_seq=2).ok
    assert verify_chain(first + second, genesis).ok
    assert not verify_chain(second, genesis, start_seq=0).ok


def test_merkle_root_changes_with_any_leaf(genesis):
    events = build_chain(genesis, typed("abc"))
    root = merkle_root([e["hash"] for e in events])
    assert len(root) == 64
    altered = [e["hash"] for e in events]
    altered[1] = "0" * 64
    assert merkle_root(altered) != root
    assert merkle_root([]) != root


# ---- property: the append-only invariant --------------------------------------------

@st.composite
def edit_sequences(draw):
    """Valid edit op sequences against a running text (positions always in range)."""
    text = ""
    ops = []
    for _ in range(draw(st.integers(min_value=1, max_value=25))):
        kind = draw(st.sampled_from(["type", "type", "type", "paste", "ckpt"]))
        if kind == "ckpt":
            new = draw(st.text(max_size=20))
            ops.append({"k": "ckpt", "p": 0, "d": 0, "i": new})
            text = new
            continue
        p = draw(st.integers(min_value=0, max_value=len(text)))
        d = draw(st.integers(min_value=0, max_value=len(text) - p))
        ins = draw(st.text(max_size=8))
        ops.append({"k": kind, "p": p, "d": d, "i": ins, "src": "ext" if kind == "paste" else None})
        text = text[:p] + ins + text[p + d:]
    return ops, text


@given(edit_sequences())
@hsettings(max_examples=150)
def test_built_chain_always_verifies_and_replays(seq_and_text):
    ops, expected = seq_and_text
    genesis = "a" * 64
    events = build_chain(genesis, ops)
    res = verify_chain(events, genesis)
    assert res.ok
    assert replay(events) == expected


@given(edit_sequences(), st.data())
@hsettings(max_examples=150)
def test_any_single_mutation_breaks_chain(seq_and_text, data):
    ops, _ = seq_and_text
    genesis = "a" * 64
    events = build_chain(genesis, ops)
    idx = data.draw(st.integers(min_value=0, max_value=len(events) - 1))
    field = data.draw(st.sampled_from(["i", "ts", "p", "d", "k", "prev"]))
    mutated = copy.deepcopy(events)
    ev = mutated[idx]
    if field == "i":
        ev["i"] = ev["i"] + "x"
    elif field == "k":
        ev["k"] = "paste" if ev["k"] != "paste" else "type"
    elif field == "prev":
        ev["prev"] = ("0" if ev["prev"][0] != "0" else "1") + ev["prev"][1:]
    else:
        ev[field] = ev[field] + 1
    res = verify_chain(mutated, genesis)
    assert not res.ok
    assert res.index == idx
