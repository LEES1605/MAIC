# =============================== [01] imports ===============================
from __future__ import annotations

import os
import json
from typing import Optional, Sequence, Any

try:
    import streamlit as st  # Streamlit 아닐 수도 있음
except Exception:
    st = None  # Streamlit 미사용 환경 허용

# =============================== [02] helpers ===============================
def _from_secrets(name: str) -> Any | None:
    """st.secrets 있으면 먼저 읽고, 없거나 키 없으면 None."""
    if st is not None and hasattr(st, "secrets"):
        try:
            # st.secrets는 Mapping 유사 객체라 .get 사용 가능
            return st.secrets.get(name)
        except Exception:
            return None
    return None

# =============================== [03] API: get ==============================
def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """secrets → env 순으로 읽어서 문자열로 반환. dict/list는 JSON 직렬화."""
    val = _from_secrets(name)
    if val is None:
        return os.getenv(name, default)
    if isinstance(val, str):
        return val
    # dict/list 등은 JSON 문자열로 고정
    return json.dumps(val, ensure_ascii=False)

# =========================== [04] API: promote_env ==========================
def promote_env(names: Sequence[str], *, also_env: bool = True) -> None:
    """
    secrets 값을 os.environ으로 '승격'.
    - also_env=True: 이미 env에 값이 있어도 덮어쓰지 않음(기본 동작 유지)
    - also_env=False: env에 비어있을 때만 채움
    """
    for k in names:
        if not k:
            continue
        # 이미 환경변수가 있다면 그대로 둠
        if also_env and os.getenv(k):
            continue
        val = get(k, None)
        if val is not None and not os.getenv(k):
            os.environ[k] = str(val)
