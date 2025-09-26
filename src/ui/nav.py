# -*- coding: utf-8 -*-
"""공통 사이드바 네비게이션."""
from __future__ import annotations
import streamlit as st

def hide_default_multipage_nav() -> None:
    # Streamlit 기본 멀티페이지 네비 숨김 (모든 로그인 이후 페이지에 적용)
    st.markdown(
        """
        <style>
          section[data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar() -> None:
    """로그인/관리자 상태에 따라 동일한 메뉴를 일관되게 렌더."""
    hide_default_multipage_nav()

    is_admin = bool(st.session_state.get("admin_mode"))
    st.sidebar.markdown("### 메뉴")

    # 멀티페이지 구성이 pages/든 루트든 상관없이 st.page_link가 알아서 매핑
    st.sidebar.page_link("app.py", label="채팅")
    if is_admin:
        st.sidebar.page_link("admin_prompt.py", label="관리자: 프롬프트")
        st.sidebar.page_link("index_status.py", label="관리자: 인덱스 상태")

    st.sidebar.divider()
    # (선택) 로그아웃/상태칩 등 공통 액션
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()
