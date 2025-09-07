# =============================== [01] imports ===============================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None

# =========================== [02] effective dir =============================
def effective_persist_dir() -> Path:
    """
    Persist 경로의 단일 소스(SSOT).
    우선순위: st.session_state['_PERSIST_DIR'] → src.rag.index_build.PERSIST_DIR
            → env(MAIC_PERSIST_DIR) → ~/.maic/persist
    """
    # 세션 우선
    try:
        if st is not None and "_PERSIST_DIR" in st.session_state:
            p = Path(str(st.session_state["_PERSIST_DIR"])).expanduser()
            return p
    except Exception:
        pass

    # 인덱서 기본값
    try:
        from src.rag.index_build import PERSIST_DIR as _pp  # lazy import
        return Path(str(_pp)).expanduser()
    except Exception:
        pass

    # 환경변수
    envp = os.getenv("MAIC_PERSIST_DIR")
    if envp:
        return Path(envp).expanduser()

    # 기본
    return Path.home() / ".maic" / "persist"

# ===================== [03] share to session (optional) =====================
def share_persist_dir_to_session(p: Path) -> None:
    """세션과 persist 경로를 공유(있으면). 실패시 무해."""
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()
    except Exception:
        pass
