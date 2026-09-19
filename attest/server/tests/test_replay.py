import pytest

from attest.replay import ReplayError, replay

from conftest import build_chain, typed


def test_typing_replays(genesis):
    assert replay(build_chain(genesis, typed("hello"))) == "hello"


def test_insert_delete_and_paste(genesis):
    ops = typed("helo") + [
        {"p": 3, "d": 0, "i": "l", "k": "type"},            # hello
        {"p": 5, "d": 0, "i": " world", "k": "paste", "src": "ext"},
        {"p": 0, "d": 1, "i": "H", "k": "type"},            # Hello world
        {"p": 5, "d": 6, "i": "", "k": "type"},             # Hello
    ]
    assert replay(build_chain(genesis, ops)) == "Hello"


def test_checkpoint_resets_text(genesis):
    ops = typed("abc") + [{"k": "ckpt", "i": "fresh"}] + [{"p": 5, "d": 0, "i": "!", "k": "type"}]
    assert replay(build_chain(genesis, ops)) == "fresh!"


def test_non_text_kinds_are_noops(genesis):
    ops = typed("ab") + [{"k": "kd"}, {"k": "ku"}, {"k": "copy", "p": 0, "d": 2, "i": "ab"}]
    assert replay(build_chain(genesis, ops)) == "ab"


def test_code_point_positions(genesis):
    ops = [{"p": 0, "d": 0, "i": "🙂", "k": "type"}, {"p": 1, "d": 0, "i": "x", "k": "type"}]
    assert replay(build_chain(genesis, ops)) == "🙂x"


def test_out_of_range_raises(genesis):
    with pytest.raises(ReplayError) as exc:
        replay(build_chain(genesis, [{"p": 3, "d": 0, "i": "x", "k": "type"}]))
    assert exc.value.index == 0
