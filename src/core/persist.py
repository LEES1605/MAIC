# ============== [01] imports & docstring — START ==============
"""
Persist path resolver (SSOT) - PathResolver 클래스 사용

이 모듈은 이제 PathResolver 클래스를 사용하여 경로 해석을 수행합니다.
기존 함수들은 호환성을 위해 유지되지만, 내부적으로는 PathResolver를 사용합니다.
"""
from __future__ import annotations

from pathlib import Path

# PathResolver 클래스 사용
from .path_resolver import get_path_resolver

__all__ = ["effective_persist_dir", "share_persist_dir_to_session"]
# ============== [01] imports & docstring — END ==============


# ============== [02] effective dir — START ==============
def effective_persist_dir() -> Path:
    """
    Single source of truth (SSOT) for persist directory.
    PathResolver 클래스를 사용하여 경로를 해석합니다.
    """
    return get_path_resolver().get_persist_dir()
# ============== [02] effective dir — END ==============


# ============== [03] share to session — START ==============
def share_persist_dir_to_session(p: Path) -> None:
    """Share path to Streamlit session if available (no-op on failure)."""
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = Path(str(p)).expanduser()
    except Exception:  # noqa: BLE001
        pass
# ============== [03] share to session — END ==============
