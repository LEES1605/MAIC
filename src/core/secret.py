# ======================= [S0] secrets helpers — FULL =======================
from __future__ import annotations

import os
from typing import Any, Mapping, Sequence, Optional

# Streamlit이 없을 수도 있으니 안전하게 처리 (type: ignore 사용 금지)
try:
    import streamlit as _st_mod  # noqa: F401
    st: Any | None = _st_mod
except Exception:
    st = None


def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """st.secrets → env 순으로 안전하게 조회."""
    # 1) st.secrets
    try:
        if st is not None:
            secrets_obj = getattr(st, "secrets", None)
            if isinstance(secrets_obj, Mapping):
                val = secrets_obj.get(name, None)
                if val is not None:
                    return str(val)
    except Exception:
        pass

    # 2) os.environ
    return os.environ.get(name, default)


def promote_env(keys: Sequence[str] | None = None) -> None:
    """st.secrets의 값을 환경변수로 승격. 이미 env에 있으면 보존."""
    src: Mapping[str, Any] = {}
    try:
        if st is not None:
            maybe = getattr(st, "secrets", {})
            if isinstance(maybe, Mapping):
                src = maybe
    except Exception:
        src = {}

    use_keys: Sequence[str]
    if keys is None:
        use_keys = tuple(src.keys())
    else:
        use_keys = keys

    for k in use_keys:
        if k and (k not in os.environ):
            v = src.get(k)
            if v is not None:
                os.environ[k] = str(v)
# ========================================================================== 
