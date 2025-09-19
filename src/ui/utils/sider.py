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
        # set_page_config는 1회만 허용 → 후속 호출 무시
        pass


def _hide_native_sidebar_nav() -> None:
    """Streamlit 기본 멀티페이지 네비 전부 숨김(CSS 다중 셀렉터)."""
    st = _st()
    st.markdown(
        "<style>"
        "nav[data-testid='stSidebarNav']{display:none!important;}"
        "div[data-testid='stSidebarNav']{display:none!important;}"
        "section[data-testid='stSidebar'] [data-testid='stSidebarNav']{display:none!important;}"
        "section[data-testid='stSidebar'] ul[role='list']{display:none!important;}"
        "</style>",
        unsafe_allow_html=True,
    )


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


def render_minimal_admin_sidebar(
    *,
    back_page: str = "app.py",
    icon_only: bool = True,
) -> None:
    """관리자용 최소 사이드바(기본 네비 숨김 + 2버튼)."""
    st = _st()
    ss = getattr(st, "session_state", {})
    if not (bool(ss.get("_admin_ok")) or bool(ss.get("admin_mode"))):
        return  # 학생은 렌더하지 않음

    _hide_native_sidebar_nav()
    label_admin = "🛠️" if icon_only else "🛠️ 어드민 프롬프트"
    label_back = "⌫" if icon_only else "← 이전으로"

    with st.sidebar:
        c1, c2 = st.columns(2)
        with c1:
            go_admin = st.button(label_admin, use_container_width=True, key="nav_admin")
        with c2:
            go_back = st.button(label_back, use_container_width=True, key="nav_back")

    try:
        if go_admin:
            st.switch_page("src/ui/admin_prompts.py")
        if go_back:
            st.switch_page(back_page)
    except Exception:
        # 폴백: 쿼리 파라미터 세팅 후 리런
        try:
            st.query_params["admin"] = "1"
        except Exception:
            pass
        if go_admin:
            try:
                st.query_params["goto"] = "admin"
            except Exception:
                pass
            st.rerun()
        if go_back:
            try:
                st.query_params["goto"] = "back"
            except Exception:
                pass
            st.rerun()


def apply_admin_chrome(*, back_page: str = "app.py", icon_only: bool = True) -> None:
    """관리자 화면에서 즉시 최소 사이드바를 보이도록 일괄 적용."""
    ensure_admin_sidebar()
    render_minimal_admin_sidebar(back_page=back_page, icon_only=icon_only)
# ===== [01] FILE: src/ui/utils/sider.py — END =====
