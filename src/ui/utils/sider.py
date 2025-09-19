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
        # set_page_config는 1회만 허용 → 후속 호출은 무시
        pass


def show_sidebar() -> None:
    """관리자용: 사이드바 펼침."""
    st = _st()
    _safe_set_page_config(initial_sidebar_state="expanded")
    st.markdown(
        "<style>section[data-testid='stSidebar']{display:block!important;}</style>",
        unsafe_allow_html=True,
    )


def hide_sidebar() -> None:
    """학생용: 사이드바 및 토글 완전 숨김."""
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
    """학생은 숨김, 관리자는 펼침. (_admin_ok or admin_mode)"""
    st = _st()
    ss = getattr(st, "session_state", {})
    if bool(ss.get("_admin_ok")) or bool(ss.get("admin_mode")):
        show_sidebar()
    else:
        hide_sidebar()


def render_minimal_admin_sidebar(back_page: str = "app.py") -> None:
    """관리자용 최소 사이드바(기본 네비 전부 숨김 + 2버튼만)."""
    st = _st()
    # 기본 네비 전부 숨김(여러 셀렉터 방어)
    st.markdown(
        "<style>"
        "nav[data-testid='stSidebarNav']{display:none!important;}"
        "div[data-testid='stSidebarNav']{display:none!important;}"
        "section[data-testid='stSidebar'] [data-testid='stSidebarNav']{display:none!important;}"
        "section[data-testid='stSidebar'] ul[role='list']{display:none!important;}"
        "</style>",
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.write("### 관리자 메뉴")
        go_admin = st.button("🛠️ 어드민 프롬프트", use_container_width=True)
        go_back = st.button("← 이전으로", use_container_width=True)

    # 전환: 가능하면 switch_page, 실패 시 쿼리파라미터로 폴백
    try:
        if go_admin:
            st.switch_page("src/ui/admin_prompts.py")
        if go_back:
            st.switch_page(back_page)
    except Exception:
        if go_admin:
            try:
                st.query_params["admin"] = "1"
                st.query_params["goto"] = "admin"
            except Exception:
                pass
            st.rerun()
        if go_back:
            try:
                st.query_params["admin"] = "1"
                st.query_params["goto"] = "back"
            except Exception:
                pass
            st.rerun()
# ===== [01] FILE: src/ui/utils/sider.py — END =====
