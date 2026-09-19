from attest.provenance import PieceTable

from conftest import build_chain, typed

T = 1_700_000_000_000


def spans(table):
    return [(p.start, p.end, p.origin) for p in table.pieces]


def test_typing_is_one_merged_typed_piece(genesis):
    t = PieceTable().apply_all(build_chain(genesis, typed("hello")))
    assert spans(t) == [(0, 5, "T")] and t.length == 5
    assert t.composition() == {"typed": 1.0, "internal": 0.0, "external": 0.0}


def test_external_paste_without_copy(genesis):
    ops = typed("ab") + [{"ts": T + 5000, "p": 2, "d": 0, "i": "PASTED", "k": "paste"}]
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert spans(t) == [(0, 2, "T"), (2, 8, "EXT")]
    assert t.external_spans() == [(2, 8)]
    assert abs(t.composition()["external"] - 6 / 8) < 1e-9


def test_paste_matching_recent_copy_is_internal(genesis):
    ops = typed("hello world") + [
        {"ts": T + 3000, "p": 0, "d": 0, "i": "hello", "k": "copy"},
        {"ts": T + 4000, "p": 11, "d": 0, "i": " ", "k": "type"},
        {"ts": T + 4100, "p": 12, "d": 0, "i": "hello", "k": "paste"},   # appended at the end
    ]
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert [o for _, _, o in spans(t)] == ["T", "INT"]
    assert t.composition()["internal"] > 0 and t.composition()["external"] == 0


def test_copy_older_than_window_is_external(genesis):
    ops = typed("hello") + [
        {"ts": T + 1000, "p": 0, "d": 0, "i": "hello", "k": "copy"},
        {"ts": T + 1000 + 31_000, "p": 5, "d": 0, "i": "hello", "k": "paste"},
    ]
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert [o for _, _, o in spans(t)] == ["T", "EXT"]


def test_insert_in_middle_splits_piece(genesis):
    ops = [{"ts": T, "p": 0, "d": 0, "i": "PASTE", "k": "paste"}, {"ts": T + 10, "p": 2, "d": 0, "i": "x", "k": "type"}]
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert spans(t) == [(0, 2, "EXT"), (2, 3, "T"), (3, 6, "EXT")]


def test_delete_across_pieces(genesis):
    ops = typed("abc") + [{"ts": T + 10, "p": 3, "d": 0, "i": "PASTE", "k": "paste"},
                          {"ts": T + 20, "p": 2, "d": 3, "i": "", "k": "type"}]   # deletes "cPA"
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert spans(t) == [(0, 2, "T"), (2, 5, "EXT")] and t.length == 5


def test_delete_entire_external_span_removes_it(genesis):
    ops = typed("ab") + [{"ts": T + 10, "p": 2, "d": 0, "i": "XYZ", "k": "paste"},
                         {"ts": T + 20, "p": 2, "d": 3, "i": "", "k": "type"}]
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert spans(t) == [(0, 2, "T")] and t.external_spans() == []


def test_checkpoint_is_external(genesis):
    t = PieceTable().apply_all(build_chain(genesis, [{"ts": T, "k": "ckpt", "i": "restored text"}]))
    assert spans(t) == [(0, 13, "EXT")]


def test_client_src_hint_is_ignored(genesis):
    ops = typed("ab") + [{"ts": T + 10, "p": 2, "d": 0, "i": "XYZ", "k": "paste", "src": "int"}]
    t = PieceTable().apply_all(build_chain(genesis, ops))
    assert [o for _, _, o in spans(t)] == ["T", "EXT"]


def test_length_tracks_replay(genesis):
    from attest.replay import replay
    ops = typed("hello world") + [{"ts": T + 10, "p": 5, "d": 6, "i": "!", "k": "type"},
                                  {"ts": T + 20, "p": 0, "d": 0, "i": "Oh ", "k": "paste"}]
    events = build_chain(genesis, ops)
    t = PieceTable().apply_all(events)
    assert t.length == len(replay(events)) == len("Oh hello!")
