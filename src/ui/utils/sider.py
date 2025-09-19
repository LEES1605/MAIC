# ===== [01] FILE: src/ui/utils/sider.py — START =====
from __future__ import annotations

from typing import Any
import importlib


def _st() -> Any:
    return importlib.import_module("streamlit")


def _safe_set_page_config(*, initial_sidebar_state: str) -> None:
    st = _st()
    try:
        st.set_page_config(initial_sidebar_state=initial_sidebar_state)
    except Exception:
        pass


def show_sidebar() -> None:
    """Show sidebar for admins."""
    st = _st()
    _safe_set_page_config(initial_sidebar_state="expanded")
    st.markdown(
        "<style>section[data-testid='stSidebar']{display:block!important;}</style>",
        unsafe_allow_html=True,
    )


def hide_sidebar() -> None:
    """Hide sidebar for students (toggle too)."""
    st = _st()
    _safe_set_page_config(initial_sidebar_state="collapsed")
    st.markdown(
        "<style>"
        "section[data-testid='stSidebar']{display:none!important;}"
        "div[data-testid='collapsedControl']{display:none!important;}"
        "</style>",
        unsafe_allow_html=True,
    )


def ensure_admin_sidebar() -> None:
    """학생은 숨김, 관리자는 펼침. _admin_ok or admin_mode."""
    st = _st()
    ss = getattr(st, "session_state", {})
    if bool(ss.get("_admin_ok")) or bool(ss.get("admin_mode")):
        show_sidebar()
    else:
        hide_sidebar()


def render_minimal_admin_sidebar(back_page: str = "app.py") -> None:
    """관리자용 최소 사이드바: 어드민 프롬프트 / ← 이전."""
    st = _st()
    # 기본 멀티페이지 네비 숨김
    st.markdown(
        "<style>nav[data-testid='stSidebarNav']{display:none!important;}</style>",
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.write("### 관리자 메뉴")
        # 어드민 프롬프트로 이동
        go_admin = st.button("🛠️ 어드민 프롬프트", use_container_width=True)
        # 이전으로
        go_back = st.button("← 이전으로", use_container_width=True)
    # 페이지 전환 (switch_page 지원 시)
    try:
        if go_admin:
            st.switch_page("src/ui/admin_prompts.py")
        if go_back:
            st.switch_page(back_page)
    except Exception:
        # 폴백: 쿼리 파라미터로 힌트 주고 리런
        if go_admin:
            st.experimental_set_query_params(admin="1", goto="admin")
            st.rerun()
        if go_back:
            st.experimental_set_query_params(admin="1", goto="back")
            st.rerun()
# ===== [01] FILE: src/ui/utils/sider.py — END =====
