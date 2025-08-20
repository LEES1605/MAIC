# ===== [01] HELPERS ==========================================================
from __future__ import annotations
from typing import Any, Mapping

def get_drive_id(file: Mapping[str, Any]) -> str:
    return str(file.get("id", "") or "")
