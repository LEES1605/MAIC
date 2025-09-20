# ===== [01] FILE: src/ui/utils/sider.py — START =====
from __future__ import annotations

from typing import Any, Dict
import importlib
from contextlib import suppress


# ──────────────────────────────── constants ─────────────────────────────────────
ADMIN_PAGE: str = "pages/90_admin_prompt.py"
DEFAULT_BACK_PAGE: str = "app.py"


# ──────────────────────────────── streamlit loader ─────────────────────────────
def _st() -> Any:
    """Lazy import to avoid hard dependency during non-UI tests."""
    return importlib.import_module("streamlit")


# ──────────────────────────────── page config helpers ──────────────────────────
def _safe_set_page_config(*, initial_sidebar_state: str) -> None:
    st = _st()
    try:
        st.set_page_config(initial_sidebar_state=initial_sidebar_state)
    except Exception:
        # set_page_config는 1회만 허용 → 후속 호출은 무시
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


# ──────────────────────────────── state & nav helpers ──────────────────────────
def _set_query_params(params: Dict[str, str]) -> None:
    """st.query_params 우선, 없으면 experimental_set_query_params로 폴백."""
    st = _st()
    try:
        if hasattr(st, "query_params"):
            for k, v in params.items():
                st.query_params[k] = v  # type: ignore[index]
        elif hasattr(st, "experimental_set_query_params"):
            st.experimental_set_query_params(**params)  # type: ignore[attr-defined]
    except Exception:
        # 쿼리 세팅 실패는 치명적이지 않으므로 무시(세션 토글이 더 중요)
        pass


def _set_admin_state(enable: bool) -> None:
    """세션 상태를 명시적으로 토글."""
    st = _st()
    ss = getattr(st, "session_state", {})
    try:
        if enable:
            ss["admin_mode"] = True
            ss["_admin_ok"] = True
        else:
            ss["admin_mode"] = False
            ss.pop("_admin_ok", None)
    except Exception:
        # 세션 접근 실패 시에도 이어서 진행
        pass


def _nav_to_admin() -> None:
    """관리자 프롬프트로 이동: 세션/쿼리 선반영 → (가능하면) 페이지 전환 → rerun."""
    st = _st()
    _set_admin_state(True)
    _set_query_params({"admin": "1", "goto": "admin"})
    with suppress(Exception):
        st.switch_page(ADMIN_PAGE)
    st.rerun()


def _nav_to_back(back_page: str) -> None:
    """프롬프트(일반 화면)로 복귀: 세션/쿼리 선반영 → (가능하면) 페이지 전환 → rerun."""
    st = _st()
    _set_admin_state(False)
    _set_query_params({"admin": "0", "goto": "back"})
    with suppress(Exception):
        st.switch_page(back_page)
    st.rerun()


# ──────────────────────────────── public: minimal admin sider ─────────────────
def render_minimal_admin_sidebar(
    *,
    back_page: str = DEFAULT_BACK_PAGE,
    icon_only: bool = True,
) -> None:
    """관리자용 최소 사이드바(기본 네비 숨김 + 2버튼).
    버튼 클릭 시:
      - 항상 먼저 세션/쿼리를 토글 (admin=1/0, goto=admin/back)
      - 가능한 경우 페이지 전환(switch_page)
      - 마지막에 항상 st.rerun()으로 상태를 즉시 반영
    """
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

    # 버튼 클릭 처리: 토글 → 전환 → rerun (항상)
    if go_admin:
        _nav_to_admin()
    elif go_back:
        _nav_to_back(back_page)


def apply_admin_chrome(*, back_page: str = DEFAULT_BACK_PAGE, icon_only: bool = True) -> None:
    """관리자 화면에서 즉시 최소 사이드바를 보이도록 일괄 적용."""
    ensure_admin_sidebar()
    render_minimal_admin_sidebar(back_page=back_page, icon_only=icon_only)
# ===== [01] FILE: src/ui/utils/sider.py — END =====
