from pathlib import Path


def _read_app() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "app.py").read_text(encoding="utf-8")


def test_no_legacy_effective_persist_dir_left() -> None:
    src = _read_app()
    # 정의가 없어야 한다.
    assert "def _effective_persist_dir(" not in src, (
        "Legacy wrapper `_effective_persist_dir()` must be removed"
    )
    # 호출도 없어야 한다.
    assert "_effective_persist_dir(" not in src, (
        "No runtime calls to `_effective_persist_dir()` should remain"
    )
