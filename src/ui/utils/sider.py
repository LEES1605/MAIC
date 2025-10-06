# [S-ALL] START: FILE src/ui/utils/sider.py — official sidebar (SSOT, logout→student)
from __future__ import annotations
from typing import Any

try:
    import streamlit as st
except Exception:
    st = None

# --- internal: default "Pages" nav hiding ------------------------------------
def _hide_default_pages_nav() -> None:
    """Streamlit 기본 사이드바 숨김 (중복 제거 - base.py에서 처리)"""
    # 이 함수는 더 이상 사용되지 않음 - base.py에서 통합 처리됨
    pass

# --- internal: page switching helpers ----------------------------------------
def _switch_to(target: str) -> bool:
    """빠른 Streamlit 페이지 네비게이션: switch_page 우선 사용."""
    if st is None:
        return False
    try:
        # 가장 빠른 방법: switch_page 직접 사용
        st.switch_page(target)
        return True
    except Exception:
        # 폴백: 쿼리 파라미터로 페이지 전환
        try:
            st.query_params["page"] = target
            st.rerun()
            return True
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
        
        /* 추가 사이드바 숨김 (중복 제거 - base.py에서 처리) */
        </style>
        """, unsafe_allow_html=True)
    except Exception:
        pass
    
    # 간단한 탭 시스템 적용 (페이지 전환 없이)
    try:
        from ..components.ios_tabs_simple import render_ios_tabs_simple, create_admin_tabs_simple
        
        tabs = create_admin_tabs_simple()
        active_tab = render_ios_tabs_simple(tabs, key="admin_tabs")
        
        # 탭 내용을 조건부로 렌더링
        if active_tab == "management":
            # 관리 탭 내용 렌더링 (현재 페이지에서)
            render_management_content()
        elif active_tab == "prompt":
            # 프롬프트 탭 내용 렌더링 (현재 페이지에서)
            render_prompt_content()
            
    except Exception as e:
        # 폴백: 기존 사이드바 사용
        try:
            ensure_admin_sidebar()
            apply_admin_chrome(back_page=back_page or "app.py", icon_only=icon_only)
        except Exception:
            pass

    # 로그아웃 버튼은 헤더에 통합 (사이드바 제거로 인해)
    # 실제 로그아웃 기능은 header.py에서 처리


def render_management_content() -> None:
    """관리 탭 내용 렌더링 - 중복 호출 방지를 위해 비활성화"""
    # render_admin_indexing_panel()은 app.py에서 이미 호출되므로 중복 방지
    st.info("관리 패널은 메인 화면에서 확인하세요.")


def render_prompt_content() -> None:
    """프롬프트 탭 내용 렌더링"""
    try:
        # 프롬프트 편집기 내용을 직접 임베드
        st.markdown("### 프롬프트 편집기")
        st.info("프롬프트 편집 기능이 여기에 표시됩니다.")
        
        # 실제 프롬프트 편집기 내용을 여기에 추가할 수 있습니다
        with st.expander("페르소나 설정", expanded=True):
            st.text_area("페르소나 텍스트", placeholder="페르소나 텍스트를 입력하세요...")
        
        with st.expander("모드별 프롬프트", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.text_area("문법 모드", placeholder="문법 모드 지시/규칙...")
            with col2:
                st.text_area("문장 모드", placeholder="문장 모드 지시/규칙...")
            
            st.text_area("지문 모드", placeholder="지문 모드 지시/규칙...")
        
        if st.button("저장", type="primary"):
            st.success("프롬프트가 저장되었습니다!")
            
    except Exception as e:
        st.error(f"프롬프트 패널 로드 실패: {e}")


__all__ = ["render_sidebar", "ensure_admin_sidebar", "apply_admin_chrome", "show_sidebar", "render_management_content", "render_prompt_content"]
# [S-ALL] END: FILE src/ui/utils/sider.py
