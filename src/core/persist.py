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
# ============== [01] imports & module docstring — END ==============



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
