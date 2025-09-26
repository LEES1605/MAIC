# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore


def _switch_to(target: str) -> bool:
    """Streamlit 버전별 네비게이션 폴백."""
    if st is None:
        return False
    # 1) 최신: switch_page
    try:
        st.switch_page(target)  # type: ignore[attr-defined]
        return True
    except Exception:
        pass
    # 2) page_link (사이드바에 링크만 노출)
    try:
        st.sidebar.page_link(target, label="프롬프트 편집기")  # type: ignore[attr-defined]
        return True
    except Exception:
        pass
    return False


def ensure_admin_sidebar() -> None:
    """사이드바를 강제로 보이게(가능할 때)."""
    if st is None:
        return
    try:
        st.sidebar.empty()
    except Exception:
        pass


def show_sidebar() -> None:
    """현재 테마에서 사이드바를 보이도록 하는 보조 유틸(호환용)."""
    ensure_admin_sidebar()


def apply_admin_chrome(*, back_page: str = "app.py", icon_only: bool = True) -> None:
    """
    관리자용 미니 사이드바를 구성한다.
    - 홈으로(오케스트레이터): app.py
    - 프롬프트 편집기: src/ui/admin_prompt.py → (폴백) admin_prompt.py
    """
    if st is None:
        return
    with st.sidebar:
        st.markdown("### 🛠️ Admin")
        if st.button("🏠 오케스트레이터", use_container_width=True):
            _switch_to(back_page)

        if st.button("🧰 프롬프트 편집기", use_container_width=True):
            if not _switch_to("src/ui/admin_prompt.py"):
                _switch_to("admin_prompt.py")  # 루트 래퍼 폴백


def render_minimal_admin_sidebar(*, back_page: str = "app.py") -> None:
    """프롬프트 화면 등에서 보여줄 최소 사이드바."""
    apply_admin_chrome(back_page=back_page)
