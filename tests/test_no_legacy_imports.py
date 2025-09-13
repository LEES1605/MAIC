# [TEST-LEGACY] START: tests/test_no_legacy_imports.py (NEW FILE)
from __future__ import annotations

import re
from pathlib import Path

PATTERN = re.compile(r"\b(from|import)\s+modes\.types\b")

def test_no_legacy_imports_in_src() -> None:
    root = Path(__file__).resolve().parents[1] / "src"
    bad: list[str] = []
    for py in root.rglob("*.py"):
        try:
            txt = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if PATTERN.search(txt):
            bad.append(str(py.relative_to(root.parent)))
    assert not bad, "Legacy imports found:\n" + "\n".join(bad)
# [TEST-LEGACY] END
