# [S-ALL] START: FILE src/ui/utils/sider.py — official sidebar (SSOT, logout→student)
from __future__ import annotations
from typing import Any

try:
    import streamlit as st
except Exception:
    st = None

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
                st.experimental_set_query_params(admin="0", goto="home")
            except Exception:
                pass
        # 홈으로 이동 시도 후, 최후엔 rerun
        _switch_to("app.py")
        try:
            st.rerun()
        except Exception:
            try:
                st.experimental_rerun()
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
    📌 iOS 스타일 탭 시스템으로 변경.
    - 사이드바 제거하고 상단 탭으로 대체
    - 모바일 우선 디자인 적용
    """
    if st is None:
        return
    
    # 기본 Pages 네비 숨김
    _hide_default_pages_nav()
    
    # 사이드바 완전 숨김 (더 강력한 CSS)
    try:
        st.markdown("""
        <style>
        /* Streamlit 사이드바 완전 제거 */
        .css-1d391kg { display: none !important; }
        .css-1v0mbdj { display: none !important; }
        [data-testid="stSidebar"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        .css-1cypcdb { display: none !important; }
        .css-1d391kg { display: none !important; }
        
        /* 메인 컨테이너 전체 너비 사용 */
        .main .block-container { 
            max-width: 100% !important; 
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* 사이드바 공간 제거 */
        .stApp > div:first-child {
            padding-left: 0 !important;
        }
        
        /* 추가 사이드바 숨김 */
        div[data-testid="stSidebar"] { display: none !important; }
        .stSidebar { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
    except Exception:
        pass
    
    # iOS 스타일 탭 시스템 적용 (작동하는 버전)
    try:
        from ..components.ios_tabs_working import render_ios_tabs_working, create_admin_tabs_working
        
        tabs = create_admin_tabs_working()
        active_tab = render_ios_tabs_working(tabs, key="admin_tabs")
        
        # 탭에 따른 페이지 라우팅
        if active_tab == "management":
            # 관리 탭 - 오케스트레이터로 이동
            if back_page != "app.py":
                _switch_to("app.py")
        elif active_tab == "prompt":
            # 프롬프트 탭 - 프롬프트 편집기로 이동
            _switch_to("pages/10_admin_prompt.py")
            
    except Exception as e:
        # 폴백: 기존 사이드바 사용
        try:
            ensure_admin_sidebar()
            apply_admin_chrome(back_page=back_page or "app.py", icon_only=icon_only)
        except Exception:
            pass

    # 로그아웃 버튼은 헤더에 통합 (사이드바 제거로 인해)
    # 실제 로그아웃 기능은 header.py에서 처리

__all__ = ["render_sidebar", "ensure_admin_sidebar", "apply_admin_chrome", "show_sidebar"]
# [S-ALL] END: FILE src/ui/utils/sider.py
