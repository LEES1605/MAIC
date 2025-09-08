# =============================== [01] imports ===============================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None

# =========================== [02] effective dir — START =============================
def effective_persist_dir() -> Path:
    """
    Persist 경로의 단일 소스(SSOT).

    우선순위(상위 → 하위):
      1) 세션: st.session_state["_PERSIST_DIR"]
      2) 환경변수(신규): MAIC_PERSIST               # 마스터플랜 권고
      3) 환경변수(레거시): MAIC_PERSIST_DIR        # 하위 호환
      4) 상수(레거시): src.rag.index_build.PERSIST_DIR  # 최후의 보조
      5) 기본값: ~/.maic/persist

    주의:
    - 부수효과 없음(디렉터리 생성 X)
    - '~' 등은 expanduser()로 정규화하여 Path로 반환
    """
    # 1) 세션 우선
    try:
        if st is not None and "_PERSIST_DIR" in st.session_state:
            raw = str(st.session_state["_PERSIST_DIR"]).strip()
            if raw:
                return Path(raw).expanduser()
    except Exception:
        # 세션 관련 예외는 무시(순수 결정 함수 유지)
        pass

    # 2) 신규 환경변수(우선)
    envp = os.getenv("MAIC_PERSIST")
    if envp:
        envp = envp.strip()
        if envp:
            return Path(envp).expanduser()

    # 3) 레거시 환경변수(하위 호환)
    legacy_envp = os.getenv("MAIC_PERSIST_DIR")
    if legacy_envp:
        legacy_envp = legacy_envp.strip()
        if legacy_envp:
            return Path(legacy_envp).expanduser()

    # 4) 레거시 상수(옵션, lazy import)
    try:
        from src.rag.index_build import PERSIST_DIR as _pp  # lazy import
        if _pp:
            return Path(str(_pp)).expanduser()
    except Exception:
        pass

    # 5) 기본 경로
    return Path.home() / ".maic" / "persist"
# =========================== [02] effective dir — END ===============================

# ===================== [03] share to session (optional) =====================
def share_persist_dir_to_session(p: Path) -> None:
    """세션과 persist 경로를 공유(있으면). 실패시 무해."""
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()
    except Exception:
        pass
