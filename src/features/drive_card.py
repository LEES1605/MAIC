# ===== [01] HELPERS ==========================================================
from __future__ import annotations

from typing import Any, Mapping


def get_drive_id(file: Mapping[str, Any]) -> str:
    """Drive 파일 메타에서 id를 항상 문자열로 반환(없으면 빈 문자열)."""
    return str(file.get("id", "") or "")


# ===== [02] END ==============================================================
