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
    
    # 탭 버튼들을 Streamlit 버튼으로 구현 (간단한 스타일)
    st.markdown("""
    <style>
    .simple-tabs {
        display: flex;
        background: #ffffff;
        border-bottom: 1px solid #e5e5e7;
        margin: -1rem -1rem 1rem -1rem;
        padding: 0 1rem;
        gap: 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 탭 버튼들을 Streamlit 버튼으로 구현
    cols = st.columns(len(tabs))
    
    for i, tab in enumerate(tabs):
        with cols[i]:
            is_active = tab["id"] == current_tab
            
            if st.button(
                f"{tab.get('icon', '')} {tab['label']}",
                key=f"{key}_{tab['id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                # 탭 변경 시 즉시 세션 상태 업데이트
                st.session_state[session_key] = tab["id"]
                # 즉시 새로고침
                st.rerun()
    
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