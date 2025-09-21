# ===== [01] FILE: src/core/readiness.py — START =====
from __future__ import annotations

from pathlib import Path
from typing import Optional

# 통일된 허용 토큰(SSOT): 값은 소문자/공백제거/UTF-8 BOM 제거 후 비교
_TRUE_TOKENS = {"ready", "ok", "true", "1", "on", "yes", "y", "green"}


def norm_ready_text(raw: str | bytes | None) -> str:
    """
    Normalize ready text for tolerant comparison:
    - bytes → utf-8 decode(ignore errors)
    - strip whitespace
    - remove BOM(\ufeff)
    - lowercase
    """
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    return raw.replace("\ufeff", "").strip().lower()


def is_ready_text(raw: str | bytes | None) -> bool:
    """
    Return True if 'raw' represents a valid 'ready' value under our tolerant rules.
    """
    return norm_ready_text(raw) in _TRUE_TOKENS


def read_ready_text(persist_dir: Path) -> str:
    """
    Read the '.ready' file text (utf-8) if present; return empty string on any failure.
    """
    try:
        return (persist_dir / ".ready").read_text(encoding="utf-8")
    except Exception:
        return ""


def normalize_ready_file(persist_dir: Path, *, value: str = "ready") -> bool:
    """
    Ensure '.ready' file exists and contains the canonical token (default: 'ready').
    Returns True on success, False on failure.
    """
    try:
        (persist_dir / ".ready").write_text(value, encoding="utf-8")
        return True
    except Exception:
        return False


__all__ = [
    "norm_ready_text",
    "is_ready_text",
    "read_ready_text",
    "normalize_ready_file",
]
# ===== [01] FILE: src/core/readiness.py — END =====
