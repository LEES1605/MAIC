# ============================== [01] module header ==============================
"""
core.secret — Streamlit secrets ↔ env 접근 SSOT

- get(name, default): st.secrets 우선, 없으면 os.environ, 문자열화하여 반환
- promote_env(keys): 주어진 키들에 대해 secrets→env 승격 (env가 비어있을 때만)
- token(): GH_TOKEN 또는 GITHUB_TOKEN 반환
- resolve_owner_repo(): (owner, repo)를 여러 소스에서 안전하게 도출
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple
import os

try:
    import streamlit as st  # pragma: no cover
except Exception:  # pragma: no cover
    st = None  # type: ignore[assignment]

# ============================== [02] api ========================================
def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """st.secrets → os.environ 순으로 조회하고 문자열로 반환."""
    try:
        if st is not None and hasattr(st, "secrets"):
            val = st.secrets.get(name)  # type: ignore[attr-defined]
            if val is not None:
                return str(val)
    except Exception:
        pass
    return os.getenv(name, default)


def promote_env(keys: Iterable[str]) -> None:
    """지정된 키에 대해 secrets 값을 env로 승격(env가 비어있을 때만)."""
    for k in keys:
        try:
            if not os.getenv(k):
                v = get(k)
                if v is not None:
                    os.environ[k] = str(v)
        except Exception:
            # best-effort
            pass


def token() -> Optional[str]:
    """GitHub 토큰(GH_TOKEN 또는 GITHUB_TOKEN)."""
    return get("GH_TOKEN") or get("GITHUB_TOKEN")


def resolve_owner_repo() -> Tuple[str, str]:
    """(owner, repo) 결정: GH_OWNER/GH_REPO → GITHUB_REPO → GITHUB_OWNER/GITHUB_REPO_NAME."""
    owner = get("GH_OWNER") or get("GITHUB_OWNER") or ""
    repo = get("GH_REPO") or get("GITHUB_REPO_NAME") or ""

    combo = get("GITHUB_REPO")
    if (not owner or not repo) and combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()

    return owner, repo

__all__ = ["get", "promote_env", "token", "resolve_owner_repo"]
# ============================== [EOF] ===========================================
