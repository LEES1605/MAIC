# 간단하고 안정적인 탭 시스템 (페이지 전환 없이)
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs_simple(
    tabs: List[Dict[str, Any]],
    active_tab: str = "management",
    key: str = "ios_tabs"
) -> str:
    """
    간단하고 안정적인 탭 시스템 (페이지 전환 없이)
    
    Args:
        tabs: 탭 정보 리스트 [{"id": "tab1", "label": "관리", "icon": "○"}, ...]
        active_tab: 현재 활성 탭 ID
        key: Streamlit key
    
    Returns:
        선택된 탭 ID
    """
    if st is None or not tabs:
        return tabs[0]["id"] if tabs else ""
    
    # 세션 상태에서 활성 탭 관리
    session_key = f"{key}_active"
    if session_key not in st.session_state:
        st.session_state[session_key] = active_tab
    
    current_tab = st.session_state[session_key]
    
    # iOS 스타일 탭 시스템 구현 (Streamlit 네이티브)
    st.markdown("""
    <style>
    .ios-tabs-wrapper {
        margin: -1rem -1rem 1rem -1rem;
        padding: 0 1rem;
        background: #ffffff;
        border-bottom: 1px solid #e5e5e7;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .stButton > button {
        border-radius: 0 !important;
        border: none !important;
        box-shadow: none !important;
        font-weight: 500 !important;
        font-size: 16px !important;
        padding: 12px 16px !important;
        margin: 0 !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button[kind="primary"] {
        background: rgba(0, 122, 255, 0.05) !important;
        color: #007aff !important;
        border-bottom: 3px solid #007aff !important;
    }
    
    .stButton > button[kind="secondary"] {
        background: transparent !important;
        color: #8e8e93 !important;
        border-bottom: 3px solid transparent !important;
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: rgba(0, 0, 0, 0.05) !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: rgba(0, 122, 255, 0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # iOS 스타일 탭 버튼들
    with st.container():
        st.markdown('<div class="ios-tabs-wrapper">', unsafe_allow_html=True)
        
        cols = st.columns(len(tabs))
        
        for i, tab in enumerate(tabs):
            with cols[i]:
                is_active = tab["id"] == current_tab
                
                if st.button(
                    tab['label'],
                    key=f"{key}_{tab['id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary"
                ):
                    # 탭 변경 시 즉시 세션 상태 업데이트
                    st.session_state[session_key] = tab["id"]
                    # 즉시 새로고침
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    return current_tab


def create_admin_tabs_simple() -> List[Dict[str, Any]]:
    """관리자 모드용 탭 설정"""
    return [
        {
            "id": "management",
            "label": "관리",
            "icon": ""
        },
        {
            "id": "prompt",
            "label": "프롬프트", 
            "icon": ""
        }
    ]


__all__ = ["render_ios_tabs_simple", "create_admin_tabs_simple"]