# [S-ALL] START: FILE src/ui/utils/sider.py — official sidebar (SSOT, logout→student)
from __future__ import annotations
from typing import Any

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore

# --- internal: default "Pages" nav hiding ------------------------------------
def _hide_default_pages_nav() -> None:
    if st is None:
        return
    try:
        st.markdown(
            """
            <style>
              [data-testid="stSidebarNav"],
              section[data-testid="stSidebarNav"],
              nav[data-testid="stSidebarNav"],
              div[data-testid="stSidebarNav"]{
                display:none!important; height:0!important; overflow:hidden!important;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

# --- internal: page switching helpers ----------------------------------------
def _switch_to(target: str) -> bool:
    """Streamlit 페이지 네비게이션: switch_page → page_link → query params 순 폴백."""
    if st is None:
        return False
    try:
        st.switch_page(target)  # e.g., "app.py" / "pages/10_admin_prompt.py"
        return True
    except Exception:
        pass
    try:
        st.sidebar.page_link(target, label="열기")
        return True
    except Exception:
        pass
    try:
        st.query_params["goto"] = "home"
        if hasattr(st, "rerun"):
            st.rerun()
    except Exception:
        pass
    return False

def _logout_to_student() -> None:
    """관리자 세션 해제 → 학생 화면으로 강제 이동."""
    if st is None:
        return
    try:
        ss = st.session_state
        # 관리자 플래그/흔적 제거
        for k in ("admin_mode", "_admin_ok", "_ADMIN_TOGGLE_TS", "is_admin"):
            try:
                ss.pop(k, None)
            except Exception:
                pass
        # 쿼리파라미터로도 확실히 학생 모드 고정 (app.py의 토글 로직과 정합) :contentReference[oaicite:4]{index=4}
        try:
            st.query_params["admin"] = "0"
            st.query_params["goto"] = "home"
        except Exception:
            # 구버전 폴백
            try:
                st.experimental_set_query_params(admin="0", goto="home")  # type: ignore[attr-defined]
            except Exception:
                pass
        # 홈으로 이동 시도 후, 최후엔 rerun
        _switch_to("app.py")
        try:
            st.rerun()
        except Exception:
            try:
                st.experimental_rerun()  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        pass

# --- public: admin sidebar util ------------------------------------------------
def ensure_admin_sidebar() -> None:
    if st is None:
        return
    try:
        st.sidebar.empty()
    except Exception:
        pass

def show_sidebar() -> None:
    ensure_admin_sidebar()

def apply_admin_chrome(*, back_page: str = "app.py", icon_only: bool = True) -> None:
    """관리자용 미니 사이드바(툴 버튼 포함)."""
    if st is None:
        return
    with st.sidebar:
        st.markdown("### 🛠️ Admin")
        if st.button("🏠 오케스트레이터", use_container_width=True):
            _switch_to(back_page)
        if st.button("🧰 프롬프트 편집기", use_container_width=True):
            _switch_to("pages/10_admin_prompt.py")

def render_sidebar(*, back_page: str | None = "app.py", icon_only: bool = False) -> None:
    """
    📌 '진짜' 사이드바의 공식 진입점.
    - 기본 Pages 네비를 완전 숨김
    - 기존 유틸(ensure_admin_sidebar/apply_admin_chrome)로 렌더
    - 실패 시 안전한 최소 메뉴로 폴백
    """
    if st is None:
        return
    _hide_default_pages_nav()

    try:
        ensure_admin_sidebar()
    except Exception:
        pass
    try:
        apply_admin_chrome(back_page=back_page or "app.py", icon_only=icon_only)
    except Exception:
        st.sidebar.markdown("### 메뉴")
        try:
            st.sidebar.page_link("app.py", label="채팅")
            st.sidebar.page_link("pages/10_admin_prompt.py", label="관리자: 프롬프트")
            st.sidebar.page_link("pages/15_index_status.py", label="관리자: 인덱스 상태")
        except Exception:
            pass

    st.sidebar.divider()
    if st.sidebar.button("로그아웃", type="secondary", use_container_width=True):
        _logout_to_student()

__all__ = ["render_sidebar", "ensure_admin_sidebar", "apply_admin_chrome", "show_sidebar"]
# [S-ALL] END: FILE src/ui/utils/sider.py
