# ============== [01] sys.path bootstrap — START ==============
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'import src.*' works under CI/pytest.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ============== [01] sys.path bootstrap — END ================
