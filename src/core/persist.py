# src/core/persist.py
"""
[core-persist.SSOT] Persist 경로 단일 진실 소스(SSOT)

우선순위(높은 → 낮은):
  1) st.session_state['_PERSIST_DIR']                    (세션 오버라이드)
  2) Secrets/Env: MAIC_PERSIST_DIR                       (운영자 설정)
  3) src.rag.index_build.PERSIST_DIR                     (인덱서 기본값)
  4) ~/.maic/persist                                     (최종 기본값)

다른 모듈은 이 모듈의 effective_persist_dir()만 참조하세요.
"""

from __future__ import annotations

from pathlib import Path
import os
from typing import Optional

# Streamlit이 없을 수도 있으므로 방어적 임포트
try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None  # type: ignore


def _from_secrets(name: str, default: Optional[str] = None) -> Optional[str]:
    """st.secrets → os.environ 순으로 조회. 실패 시 default."""
    try:
        if st is not None and hasattr(st, "secrets"):
            val = st.secrets.get(name, None)  # type: ignore[attr-defined]
            if isinstance(val, str) and val:
                return val
    except Exception:
        pass
    return os.getenv(name, default)


def _session_persist_dir() -> Optional[Path]:
    """세션에 지정된 persist 경로 가져오기(없으면 None)."""
    try:
        if st is not None and hasattr(st, "session_state"):
            p = st.session_state.get("_PERSIST_DIR")  # type: ignore[attr-defined]
            if p:
                return Path(str(p)).expanduser()
    except Exception:
        pass
    return None


def _indexer_default_dir() -> Optional[Path]:
    """내부 인덱서의 기본 PERSIST_DIR을 쓸 수 있으면 사용."""
    try:
        from src.rag.index_build import PERSIST_DIR as _IDX_DIR  # lazy import
        return Path(str(_IDX_DIR)).expanduser()
    except Exception:
        return None


def effective_persist_dir() -> Path:
    """Persist 디렉터리의 최종 결론(SSOT)."""
    # 1) 세션 오버라이드
    p = _session_persist_dir()
    if p:
        return p

    # 2) Secrets/Env
    envp = _from_secrets("MAIC_PERSIST_DIR", None)
    if envp:
        return Path(envp).expanduser()

    # 3) 인덱서 기본값
    p = _indexer_default_dir()
    if p:
        return p

    # 4) 최종 기본값
    return Path.home() / ".maic" / "persist"


def share_persist_dir_to_session(p: Path) -> None:
    """결정된 경로를 세션에 반영(있을 때만). 실패 무해화."""
    try:
        if st is not None and hasattr(st, "session_state"):
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()  # type: ignore[attr-defined]
    except Exception:
        pass


# 모듈 로드 시 한 번 디렉터리 보장(없어도 무해)
PERSIST_DIR: Path = effective_persist_dir()
try:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

__all__ = ["effective_persist_dir", "share_persist_dir_to_session", "PERSIST_DIR"]
