# [01] imports & doc START
from __future__ import annotations
"""
Persist path resolver (SSOT).
우선순위: 세션 → env MAIC_PERSIST → env MAIC_PERSIST_DIR(레거시)
        → src.rag.index_build.PERSIST_DIR(레거시) → ~/.maic/persist
이 모듈은 경로만 결정합니다(부수효과 없음).
"""
import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None

__all__ = ["effective_persist_dir", "share_persist_dir_to_session"]
_DEFAULT = Path.home() / ".maic" / "persist"
# [01] END


# [02] resolver START
def _norm(v: Optional[str]) -> Optional[Path]:
    if not v:
        return None
    s = v.strip()
    return Path(s).expanduser() if s else None


def effective_persist_dir() -> Path:
    try:
        if st is not None and "_PERSIST_DIR" in st.session_state:
            p = _norm(str(st.session_state["_PERSIST_DIR"]))
            if p is not None:
                return p
    except Exception:
        pass

    p = _norm(os.getenv("MAIC_PERSIST"))
    if p is not None:
        return p

    p = _norm(os.getenv("MAIC_PERSIST_DIR"))
    if p is not None:
        return p

    try:
        from src.rag.index_build import PERSIST_DIR as _pp  # lazy import
        p = _norm(str(_pp))
        if p is not None:
            return p
    except Exception:
        pass

    return _DEFAULT
# [02] END


# [03] share to session START
def share_persist_dir_to_session(p: Path) -> None:
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()
    except Exception:
        pass
# [03] END
