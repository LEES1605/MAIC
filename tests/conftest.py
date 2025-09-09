# [01] START: tests/conftest.py (NEW FILE)
from __future__ import annotations

import sys
from pathlib import Path

# Ensure 'src' is importable for all tests without per-file sys.path hacks.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# [01] END: tests/conftest.py
