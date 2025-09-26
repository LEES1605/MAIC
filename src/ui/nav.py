# [12] START: nav — multipage-friendly version (replace entire file)
from __future__ import annotations
import streamlit as st

def hide_default_multipage_nav() -> None:
    # Streamlit 기본 멀티페이지 네비 숨김
    st.markdown(
        """
        <style>
          section[data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar() -> None:
    """로그인/관리자 상태에 따라 동일한 메뉴를 렌더(모든 페이지에서 호출)."""
    hide_default_multipage_nav()

    is_admin = bool(st.session_state.get("admin_mode"))
    st.sidebar.markdown("### 메뉴")

    # ✔️ 현재 실행 루트가 src/라면, 멀티페이지 엔트리는 'pages/...' 경로로 지정해야 정확함
    st.sidebar.page_link("app.py", label="채팅")

    if is_admin:
        # 실제 존재하는 파일명/순번에 맞춰 조정
        st.sidebar.page_link("pages/10_admin_prompt.py", label="관리자: 프롬프트")
        st.sidebar.page_link("pages/20_index_status.py", label="관리자: 인덱스 상태")

    st.sidebar.divider()
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()
# [12] END
