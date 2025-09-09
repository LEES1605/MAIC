# ======================= [01] Module docstring — START =======================
"""
Persist path resolver (SSOT).

Order (high → low):
  1) Streamlit session: st.session_state["_PERSIST_DIR"]
  2) Env (new): MAIC_PERSIST
  3) Env (legacy): MAIC_PERSIST_DIR
  4) Legacy const: src.rag.index_build.PERSIST_DIR (if exists)
  5) Default: ~/.maic/persist

This module only decides the path (no side effects).
Always returns a Path with expanduser().
"""
# ======================== [01] Module docstring — END ========================

from __future__ import annotations

# ======================== [02] Imports & exports — START =====================
import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:  # Streamlit 미설치/런타임 예외 대비
    st = None

__all__ = ["effective_persist_dir", "share_persist_dir_to_session"]

# 기본 Persist 경로(최후의 보루)
_DEFAULT_PERSIST_DIR: Path = Path.home() / ".maic" / "persist"
# ========================= [02] Imports & exports — END ======================


# ======================= [03] Path normalization — START =====================
def _normalize_path(value: Optional[str]) -> Optional[Path]:
    """문자열 경로를 정규화하여 Path로 반환. 공백/빈값은 None."""
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    return Path(s).expanduser()
# ======================== [03] Path normalization — END ======================


# ===================== [04] effective_persist_dir — START ====================
def effective_persist_dir() -> Path:
    """
    Persist 경로의 단일 소스(SSOT).

    Precedence (high → low):
      1) st.session_state["_PERSIST_DIR"]
      2) env "MAIC_PERSIST"            # new
      3) env "MAIC_PERSIST_DIR"        # legacy
      4) src.rag.index_build.PERSIST_DIR (if exists)
      5) _DEFAULT_PERSIST_DIR (~/.maic/persist)
    """
    # 1) 세션 우선
    try:
        if st is not None and "_PERSIST_DIR" in st.session_state:
            p = _normalize_path(str(st.session_state["_PERSIST_DIR"]))
            if p is not None:
                return p
    except Exception:
        pass

    # 2) 신규 환경변수
    p = _normalize_path(os.getenv("MAIC_PERSIST"))
    if p is not None:
        return p

    # 3) 레거시 환경변수
    p = _normalize_path(os.getenv("MAIC_PERSIST_DIR"))
    if p is not None:
        return p

    # 4) 레거시 상수(있을 때만; lazy import로 의존 축소)
    try:
        from src.rag.index_build import PERSIST_DIR as _pp  # noqa: WPS433
        p = _normalize_path(str(_pp))
        if p is not None:
            return p
    except Exception:
        pass

    # 5) 기본 경로
    return _DEFAULT_PERSIST_DIR
# ====================== [04] effective_persist_dir — END =====================


# ============== [05] share_persist_dir_to_session (optional) — START =========
def share_persist_dir_to_session(p: Path) -> None:
    """Persist 경로를 세션에 공유(있을 때만). 실패해도 무해(no-op)."""
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()
    except Exception:
        pass
# =============== [05] share_persist_dir_to_session — END =====================
