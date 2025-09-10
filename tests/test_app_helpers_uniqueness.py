from pathlib import Path


def _read_app() -> str:
    # Assume repo root is parent of tests
    root = Path(__file__).resolve().parents[1]
    return (root / "app.py").read_text(encoding="utf-8")


def test_prepared_helpers_unique() -> None:
    src = _read_app()
    assert src.count("def _load_prepared_lister(") == 1, (
        "Expected exactly one _load_prepared_lister() definition"
    )
    assert src.count("def _load_prepared_api(") == 1, (
        "Expected exactly one _load_prepared_api() definition"
    )
    assert src.count("def _persist_dir_safe(") == 1, (
        "Expected exactly one _persist_dir_safe() definition"
    )


def test_no_nested_helper_defs_in_admin_sections() -> None:
    src = _read_app()
    # Extract admin sections by markers
    i1 = src.find("# =================== [13] ADMIN: Index Panel")
    i1_end = src.find("# =================== [13B]", i1)
    sec13 = src[i1:i1_end] if i1 >= 0 and i1_end >= 0 else ""

    i2 = src.find("# =================== [13B]")
    i2_end = src.find("# ============= [14] ", i2)
    sec13b = src[i2:i2_end] if i2 >= 0 and i2_end >= 0 else ""

    for sec in (sec13, sec13b):
        assert "def _load_prepared_lister(" not in sec, (
            "Nested _load_prepared_lister() should be removed from admin sections"
        )
        assert "def _load_prepared_api(" not in sec, (
            "Nested _load_prepared_api() should be removed from admin sections"
        )
        # other local helpers can remain; we only guard the prepared helpers
