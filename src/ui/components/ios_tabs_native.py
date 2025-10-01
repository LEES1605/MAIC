# Streamlit 네이티브 컴포넌트만 사용하는 탭 시스템
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs_native(
    tabs: List[Dict[str, Any]],
    active_tab: str = "management",
    key: str = "ios_tabs"
) -> str:
    """
    Streamlit 네이티브 컴포넌트만 사용하는 탭 시스템
    
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
    
    # 간단한 CSS로 탭바 스타일링
    st.markdown("""
    <style>
    .native-tabs {
        display: flex;
        background: #ffffff;
        border-bottom: 1px solid #e5e5e7;
        margin: -1rem -1rem 1rem -1rem;
        padding: 0 1rem;
        gap: 0;
    }
    .native-tab {
        flex: 1;
        padding: 12px 16px;
        text-align: center;
        border: none;
        background: transparent;
        cursor: pointer;
        font-size: 16px;
        font-weight: 500;
        color: #8e8e93;
        transition: all 0.2s ease;
    }
    .native-tab:hover {
        background: #f2f2f7;
        color: #000000;
    }
    .native-tab.active {
        color: #007aff;
        font-weight: 600;
        border-bottom: 3px solid #007aff;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 탭 버튼들을 Streamlit 버튼으로 구현
    cols = st.columns(len(tabs))
    
    for i, tab in enumerate(tabs):
        with cols[i]:
            is_active = tab["id"] == current_tab
            button_type = "primary" if is_active else "secondary"
            
            if st.button(
                f"{tab.get('icon', '')} {tab['label']}",
                key=f"{key}_{tab['id']}",
                use_container_width=True,
                type=button_type
            ):
                st.session_state[session_key] = tab["id"]
                st.rerun()
    
    return current_tab


def create_admin_tabs_native() -> List[Dict[str, Any]]:
    """관리자 모드용 탭 설정"""
    return [
        {
            "id": "management",
            "label": "관리",
            "icon": "○"
        },
        {
            "id": "prompt",
            "label": "프롬프트", 
            "icon": "○"
        }
    ]


__all__ = ["render_ios_tabs_native", "create_admin_tabs_native"]
