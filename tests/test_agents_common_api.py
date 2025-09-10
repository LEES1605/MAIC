from pathlib import Path
import importlib


def test_agents_common_importable() -> None:
    mod = importlib.import_module("src.agents._common")
    assert hasattr(mod, "_split_sentences")
    assert hasattr(mod, "_on_piece")
    assert hasattr(mod, "_runner")
    assert hasattr(mod, "StreamState")

def test_split_sentences_basic() -> None:
    mod = importlib.import_module("src.agents._common")
    f = getattr(mod, "_split_sentences")
    sents = f("안녕? 반가워요! This is good. 좋아요.")
    # 분해 결과가 2개 이상이면 충분(언어·기호 혼합 대비)
    assert isinstance(sents, list) and len(sents) >= 2

def test_stream_helpers_flow() -> None:
    mod = importlib.import_module("src.agents._common")
    state = mod.StreamState()
    out = []
    def emit(x: str) -> None:
        out.append(x)
    mod._on_piece(state, "A", emit)
    mod._on_piece(state, "B", emit)
    assert "".join(out) == "AB"
    assert state.buffer == "AB"
