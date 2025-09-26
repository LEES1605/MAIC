# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib
from typing import Any

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore


def _switch_to(target: str) -> bool:
    """Streamlit 페이지 네비게이션: switch_page → page_link → query params 순 폴백."""
    if st is None:
        return False
    # 1) 공식 네비 API
    try:
        st.switch_page(target)  # e.g., "pages/10_admin_prompt.py"
        return True
    except Exception:
        pass
    # 2) 링크라도 노출
    try:
        st.sidebar.page_link(target, label="프롬프트 편집기")
        return True
    except Exception:
        pass
    # 3) 폴백: 쿼리파라미터로 힌트 남김(최후)
    try:
        st.query_params["goto"] = "admin_prompt"
        st.rerun()
    except Exception:
        pass
    return False


def ensure_admin_sidebar() -> None:
    if st is None:
        return
    try:
        st.sidebar.empty()
    except Exception:
        pass


def show_sidebar() -> None:
    ensure_admin_sidebar()


def apply_admin_chrome(*, back_page: str = "app.py", icon_only: bool = True) -> None:
    """관리자용 미니 사이드바(툴 버튼 포함)."""
    if st is None:
        return
    with st.sidebar:
        st.markdown("### 🛠️ Admin")
        if st.button("🏠 오케스트레이터", use_container_width=True):
            _switch_to(back_page)
        if st.button("🧰 프롬프트 편집기", use_container_width=True):
            # ✅ pages/ 등록된 래퍼로 이동 (항상 성공)
            _switch_to("pages/10_admin_prompt.py")
