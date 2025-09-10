from pathlib import Path


def _read(p: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / p).read_text(encoding="utf-8")


def test_responder_has_no_local_helpers() -> None:
    src = _read("src/agents/responder.py")
    assert "def _split_sentences(" not in src, (
        "Local _split_sentences() must be removed from responder.py"
    )
    assert "def _on_piece(" not in src, (
        "Local _on_piece() must not exist in responder.py"
    )
    assert "def _runner(" not in src, (
        "Local _runner() must not exist in responder.py"
    )


def test_evaluator_has_no_local_helpers() -> None:
    src = _read("src/agents/evaluator.py")
    assert "def _split_sentences(" not in src, (
        "Local _split_sentences() must be removed from evaluator.py"
    )
    assert "def _on_piece(" not in src, (
        "Local _on_piece() must not exist in evaluator.py"
    )
    assert "def _runner(" not in src, (
        "Local _runner() must not exist in evaluator.py"
    )
