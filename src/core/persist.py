# ============== [01] imports & docstring — START ==============
"""
Persist path resolver (SSOT).

Precedence (high → low):
  1) st.session_state["_PERSIST_DIR"]
  2) env "MAIC_PERSIST"
  3) env "MAIC_PERSIST_DIR"  # legacy
  4) src.rag.index_build.PERSIST_DIR  # legacy helper
  5) default: ~/.maic/persist

Note:
- This module only *decides* the path. No side effects (no mkdir).
- Always returns pathlib.Path with expanduser().
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:  # noqa: BLE001
    st = None  # Streamlit 없는 환경(예: CI) 대비

__all__ = ["effective_persist_dir", "share_persist_dir_to_session"]

_DEFAULT_PERSIST_DIR: Path = Path.home() / ".maic" / "persist"
# ============== [01] imports & docstring — END ==============


# ============== [02] effective dir — START ==============
def _normalize_path(value: Optional[str]) -> Optional[Path]:
    """Normalize non-empty string path to Path; else None."""
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    return Path(s).expanduser()


def effective_persist_dir() -> Path:
    """
    Single source of truth (SSOT) for persist directory.
    No side effects; just returns a normalized Path.
    """
    # 1) Session-stamped path
    try:
        if st is not None and "_PERSIST_DIR" in st.session_state:
            p = _normalize_path(str(st.session_state["_PERSIST_DIR"]))
            if p is not None:
                return p
    except Exception:  # noqa: BLE001
        pass

    # 2) New env
    p = _normalize_path(os.getenv("MAIC_PERSIST"))
    if p is not None:
        return p

    # 3) Legacy env
    p = _normalize_path(os.getenv("MAIC_PERSIST_DIR"))
    if p is not None:
        return p

    # 4) Legacy constant (lazy import to avoid hard dependency)
    try:
        from src.rag.index_build import PERSIST_DIR as _pp
        p = _normalize_path(str(_pp))
        if p is not None:
            return p
    except Exception:  # noqa: BLE001
        pass

    # 5) Default
    return _DEFAULT_PERSIST_DIR
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
