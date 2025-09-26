# [02] START: FILE src/ui/nav.py — single-router version (replace entire file)
from __future__ import annotations
import streamlit as st

def hide_default_multipage_nav() -> None:
    # Streamlit 기본 "Pages" 네비를 전역 숨김
    st.markdown(
        """
        <style>section[data-testid="stSidebarNav"]{display:none !important;}</style>
        """,
        unsafe_allow_html=True,
    )

def _goto(view: str) -> None:
    st.session_state["_view"] = view
    try:
        st.experimental_set_query_params(view=view)
    except Exception:
        pass
    st.rerun()

def render_sidebar() -> None:
    hide_default_multipage_nav()
    is_admin = bool(st.session_state.get("admin_mode"))

    st.sidebar.markdown("### 메뉴")
    st.sidebar.button("채팅", on_click=_goto, args=("chat",))
    if is_admin:
        st.sidebar.button("관리자: 프롬프트", on_click=_goto, args=("admin_prompt",))
        st.sidebar.button("관리자: 인덱스 상태", on_click=_goto, args=("index_status",))

    st.sidebar.divider()
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()
# [02] END: FILE src/ui/nav.py — single-router version
