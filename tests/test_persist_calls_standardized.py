from pathlib import Path


def _read_app() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "app.py").read_text(encoding="utf-8")


def test_no_runtime_calls_to_legacy_effective_persist_dir() -> None:
    src = _read_app()
    # 정의는 정확히 1회 존재해야 한다.
    assert src.count("def _effective_persist_dir(") == 1, (
        "Legacy helper definition should exist exactly once"
    )
    # 호출은 0회(즉, 전체 카운트 == 1[정의 라인만])
    total = src.count("_effective_persist_dir(")
    assert total == 1, "Expected zero runtime calls to _effective_persist_dir()"
