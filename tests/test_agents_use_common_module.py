from pathlib import Path


def _read(p: str) -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / p).read_text(encoding="utf-8")


def test_responder_imports_common() -> None:
    src = _read("src/agents/responder.py")
    assert "src.agents._common" in src, (
        "responder.py should import from src.agents._common"
    )


def test_evaluator_imports_common() -> None:
    src = _read("src/agents/evaluator.py")
    assert "src.agents._common" in src, (
        "evaluator.py should import from src.agents._common"
    )
