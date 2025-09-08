# ============== [01] imports & module docstring — START ==============
"""
Persist path resolver (SSOT).

우선순위(높음 → 낮음):
  1) 세션: st.session_state["_PERSIST_DIR"]
  2) 환경변수(신규): MAIC_PERSIST
  3) 환경변수(레거시): MAIC_PERSIST_DIR
  4) 레거시 상수: src.rag.index_build.PERSIST_DIR (가능할 때만)
  5) 기본값: ~/.maic/persist

주의:
- 이 모듈은 "경로만 결정"합니다. 디렉터리 생성 등 부수효과는 없습니다.
- 반환값은 항상 expanduser()가 적용된 pathlib.Path 입니다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:  # noqa: BLE001
    st = None  # Streamlit 미설치/런타임 예외 대비

__all__ = ["effective_persist_dir", "share_persist_dir_to_session"]

# 기본 Persist 경로(최후의 보루)
_DEFAULT_PERSIST_DIR: Path = Path.home() / ".maic" / "persist"
# ============== [01] imports & module docstring — END ================


# =========================== [02] effective dir — START ===========================
def _normalize_path(value: Optional[str]) -> Optional[Path]:
    """문자열 경로를 정규화하여 Path로 반환. 공백/빈값은 None."""
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    return Path(s).expanduser()


def effective_persist_dir() -> Path:
    """
    Persist 경로의 단일 소스(SSOT).

    Precedence (high→low):
      1) st.session_state["_PERSIST_DIR"]
      2) env "MAIC_PERSIST"
      3) env "MAIC_PERSIST_DIR"  # legacy
      4) src.rag.index_build.PERSIST_DIR  # legacy helper
      5) _DEFAULT_PERSIST_DIR (~/.maic/persist)

    Side effects: None (no directory creation).
    """
    # 1) 세션 우선
    try:
        if st is not None and "_PERSIST_DIR" in st.session_state:
            p = _normalize_path(str(st.session_state["_PERSIST_DIR"]))
            if p is not None:
                return p
    except Exception:  # noqa: BLE001
        pass

    # 2) 신규 환경변수
    p = _normalize_path(os.getenv("MAIC_PERSIST"))
    if p is not None:
        return p

    # 3) 레거시 환경변수(하위 호환)
    p = _normalize_path(os.getenv("MAIC_PERSIST_DIR"))
    if p is not None:
        return p

    # 4) 레거시 상수(있을 때만; lazy import로 의존 최소화)
    try:
        from src.rag.index_build import PERSIST_DIR as _pp
        p = _normalize_path(str(_pp))
        if p is not None:
            return p
    except Exception:  # noqa: BLE001
        pass

    # 5) 기본 경로
    return _DEFAULT_PERSIST_DIR
# =========================== [02] effective dir — END =============================


# ===================== [03] share to session (optional) — START ===================
def share_persist_dir_to_session(p: Path) -> None:
    """
    Persist 경로를 세션에 공유(있을 때만). 실패해도 무해(no-op).
    """
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()
    except Exception:  # noqa: BLE001
        pass
# ===================== [03] share to session (optional) — END =====================
