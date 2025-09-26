# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib
from typing import Any

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore


def _switch_to(target: str) -> bool:
    """Streamlit 페이지 네비게이션: switch_page → page_link → query params 순 폴백."""
    if st is None:
        return False
    # 1) 공식 네비 API
    try:
        st.switch_page(target)  # e.g., "pages/10_admin_prompt.py"
        return True
    except Exception:
        pass
    # 2) 링크라도 노출
    try:
        st.sidebar.page_link(target, label="프롬프트 편집기")
        return True
    except Exception:
        pass
    # 3) 폴백: 쿼리파라미터로 힌트 남김(최후)
    try:
        st.query_params["goto"] = "admin_prompt"
        st.rerun()
    except Exception:
        pass
    return False


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
            # ✅ pages/ 등록된 래퍼로 이동 (항상 성공)
            _switch_to("pages/10_admin_prompt.py")

# [S1] START: official sidebar wrapper (append at end of src/ui/utils/sider.py)
from __future__ import annotations
import streamlit as st

def _hide_default_pages_nav() -> None:
    """Streamlit 기본 'Pages' 네비를 확실히 숨긴다(버전별 testid 변형 포함)."""
    try:
        st.markdown(
            """
            <style>
              [data-testid="stSidebarNav"],
              section[data-testid="stSidebarNav"],
              nav[data-testid="stSidebarNav"],
              div[data-testid="stSidebarNav"] {
                display: none !important; height: 0 !important; overflow: hidden !important;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

def render_sidebar(*, back_page: str | None = "app.py", icon_only: bool = False) -> None:
    """
    📌 이 함수가 '진짜' 사이드바의 공식 진입점이다.
    - 기본 Pages 네비를 완전히 숨기고
    - 기존 유틸(ensure_admin_sidebar/apply_admin_chrome 등)이 있으면 위에 덧씌운다.
    - 유틸이 없다면 최소 메뉴를 안전하게 렌더한다.
    """
    _hide_default_pages_nav()

    # 1) 기존 유틸이 있으면 그대로 활용
    try:
        ensure_admin_sidebar()  # noqa: F821
    except Exception:
        pass
    try:
        # 기존 구현: admin 버튼/네비를 그려주는 함수(이미 코드베이스에 존재)
        apply_admin_chrome(back_page=back_page, icon_only=icon_only)  # noqa: F821
        return
    except Exception:
        # 2) 폴백: 최소 메뉴
        st.sidebar.markdown("### 메뉴")
        try:
            # 멀티페이지 구조라면 page_link가 가장 자연스럽다.
            st.sidebar.page_link("app.py", label="채팅")
            st.sidebar.page_link("pages/10_admin_prompt.py", label="관리자: 프롬프트")
            st.sidebar.page_link("pages/15_index_status.py", label="관리자: 인덱스 상태")
        except Exception:
            # page_link 미지원 환경에선 아무 것도 강제하지 않는다.
            pass

    st.sidebar.divider()
    if st.sidebar.button("로그아웃"):
        try:
            st.session_state.clear()
        except Exception:
            pass
        try:
            st.rerun()
        except Exception:
            pass
# [S1] END
