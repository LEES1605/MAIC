# ============= [01] sider visibility controls — START =======
from __future__ import annotations

from typing import Any
import importlib


def _st() -> Any:
    return importlib.import_module("streamlit")


def _safe_set_page_config(*, initial_sidebar_state: str) -> None:
    """Call st.set_page_config safely; ignore errors if already called."""
    st = _st()
    try:
        st.set_page_config(initial_sidebar_state=initial_sidebar_state)
    except Exception:
        # Streamlit allows this only once per run; we ignore follow-up calls
        pass


def show_sidebar() -> None:
    """Show sidebar and keep the toggle available for admins."""
    st = _st()
    _safe_set_page_config(initial_sidebar_state="expanded")
    st.markdown(
        "<style>"
        "section[data-testid='stSidebar']{display:block !important;}"
        "</style>",
        unsafe_allow_html=True,
    )


def hide_sidebar() -> None:
    """Hide sidebar completely for students (including the toggle)."""
    st = _st()
    _safe_set_page_config(initial_sidebar_state="collapsed")
    st.markdown(
        "<style>"
        "section[data-testid='stSidebar']{display:none !important;}"
        "div[data-testid='collapsedControl']{display:none !important;}"
        "</style>",
        unsafe_allow_html=True,
    )


def ensure_admin_sidebar() -> None:
    """학생은 사이드바 완전 숨김, 관리자는 펼칩니다.
    세션 플래그 '_admin_ok' 또는 'admin_mode' 중 하나라도 True면 관리자 취급합니다.
    """
    st = _st()
    ss = getattr(st, "session_state", {})
    if bool(ss.get("_admin_ok")) or bool(ss.get("admin_mode")):
        show_sidebar()
    else:
        hide_sidebar()
# ================================ [01] sider visibility controls — END ===================
