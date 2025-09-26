# [01] START: FILE src/ui/utils/sider.py — official sidebar (single source of truth)
from __future__ import annotations
from typing import Any
try:
    import streamlit as st
except Exception:  # pytest 등 더블 환경 보호
    st = None  # type: ignore

# --- internal: hide Streamlit's default multipage nav -------------------------
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
              div[data-testid="stSidebarNav"] {
                display: none !important; height:0 !important; overflow:hidden !important;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

# --- internal: page switch helpers -------------------------------------------
def _switch_to(target: str) -> bool:
    """Switch to another Streamlit page with fallbacks."""
    if st is None:
        return False
    # 1) 공식 API
    try:
        st.switch_page(target)  # e.g., "pages/10_admin_prompt.py"
        return True
    except Exception:
        pass
    # 2) page_link라도 노출
    try:
        st.sidebar.page_link(target, label="프롬프트 편집기")
        return True
    except Exception:
        pass
    # 3) 최후: 쿼리 파라미터 힌트
    try:
        st.query_params["goto"] = "admin_prompt"
        if hasattr(st, "rerun"):
            st.rerun()
    except Exception:
        pass
    return False

# --- public: admin sidebar utilities -----------------------------------------
def ensure_admin_sidebar() -> None:
    if st is None:
        return
    try:
        st.sidebar.empty()  # 사이드바 컨테이너 초기화
    except Exception:
        pass

def show_sidebar() -> None:
    """레거시 호환 별칭(내부적으로 ensure_admin_sidebar만 호출)."""
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
        # 최소 폴백 메뉴
        st.sidebar.markdown("### 메뉴")
        try:
            st.sidebar.page_link("app.py", label="채팅")
            st.sidebar.page_link("pages/10_admin_prompt.py", label="관리자: 프롬프트")
            st.sidebar.page_link("pages/15_index_status.py", label="관리자: 인덱스 상태")
        except Exception:
            pass

    st.sidebar.divider()
    if st.sidebar.button("로그아웃"):
        try:
            st.session_state.clear()
        finally:
            try:
                st.rerun()
            except Exception:
                pass

__all__ = ["render_sidebar", "ensure_admin_sidebar", "apply_admin_chrome", "show_sidebar"]
# [01] END: FILE src/ui/utils/sider.py
