from __future__ import annotations

from typing import Any
import importlib


def _st() -> Any:
    return importlib.import_module("streamlit")


def show_sidebar() -> None:
    st = _st()
    st.set_page_config(initial_sidebar_state="expanded")
    st.markdown(
        "<style>section[data-testid='stSidebar'] "
        "{display: block !important;}</style>",
        unsafe_allow_html=True,
    )


def hide_sidebar() -> None:
    st = _st()
    st.set_page_config(initial_sidebar_state="collapsed")
    st.markdown(
        "<style>"
        "section[data-testid='stSidebar']{display:none !important;}"
        "div[data-testid='collapsedControl']{display:none !important;}"
        "</style>",
        unsafe_allow_html=True,
    )


def ensure_admin_sidebar() -> None:
    """세션 플래그('_admin_ok')에 따라 사이드바 노출 정책 적용."""
    st = _st()
    if st.session_state.get("_admin_ok"):
        show_sidebar()
    else:
        hide_sidebar()
