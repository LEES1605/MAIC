# =============================== common/utils.py — START =========================
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def from_env_or_secrets(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    os.environ 우선, 없으면 streamlit secrets에서 조회.
    """
    val = os.getenv(key)
    if val is not None and str(val).strip():
        return str(val)
    try:
        import streamlit as st

        v = st.secrets.get(key)
        if v is None:
            return default
        return str(v)
    except Exception:
        return default


def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding=encoding)


def write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding=encoding)


def read_json(path: str | Path, default: Any = None) -> Any:
    try:
        raw = read_text(path)
        return json.loads(raw) if raw else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def write_json(path: str | Path, obj: Any) -> None:
    try:
        write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))
    except Exception:
        pass
# ================================ common/utils.py — END ==========================
