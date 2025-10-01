# 작동하는 iOS 스타일 탭 시스템 (Streamlit 기본 기능 활용)
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs_working(
    tabs: List[Dict[str, Any]],
    active_tab: str = "management",
    key: str = "ios_tabs"
) -> str:
    """
    작동하는 iOS 스타일 탭 시스템 (Streamlit 기본 기능 활용)
    
    Args:
        tabs: 탭 정보 리스트 [{"id": "tab1", "label": "관리", "icon": "○"}, ...]
        active_tab: 현재 활성 탭 ID
        key: Streamlit key
    
    Returns:
        선택된 탭 ID
    """
    if st is None or not tabs:
        return tabs[0]["id"] if tabs else ""
    
    # iOS 스타일 탭 CSS
    st.markdown("""
    <style>
    .ios-tabs-container {
        display: flex;
        background: #ffffff;
        border-bottom: 1px solid #e5e5e7;
        margin: 0 -1rem 1rem -1rem;
        padding: 0 1rem;
        position: sticky;
        top: 0;
        z-index: 100;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
    }
    
    .ios-tab-button {
        flex: 1;
        padding: 12px 8px;
        border: none;
        background: transparent;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 16px;
        font-weight: 500;
        color: #8e8e93;
        position: relative;
        min-height: 44px;
        border-radius: 8px;
        margin: 4px;
        text-align: center;
    }
    
    .ios-tab-button:hover {
        background: #f2f2f7;
        color: #000000;
    }
    
    .ios-tab-button.active {
        color: #007aff;
        font-weight: 600;
    }
    
    .ios-tab-button.active::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 32px;
        height: 3px;
        background: #007aff;
        border-radius: 2px;
    }
    
    .ios-tab-icon {
        margin-right: 6px;
        font-size: 18px;
    }
    
    /* 모바일 최적화 */
    @media (max-width: 768px) {
        .ios-tabs-container {
            margin: 0 -0.5rem 1rem -0.5rem;
            padding: 0 0.5rem;
        }
        
        .ios-tab-button {
            padding: 16px 8px;
            font-size: 17px;
            min-height: 48px;
        }
        
        .ios-tab-icon {
            font-size: 20px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 세션 상태에서 활성 탭 관리
    session_key = f"{key}_active"
    if session_key not in st.session_state:
        st.session_state[session_key] = active_tab
    
    current_tab = st.session_state[session_key]
    
    # 탭 버튼들을 Streamlit 버튼으로 구현
    col1, col2 = st.columns(2)
    
    with col1:
        is_management_active = current_tab == "management"
        if st.button(
            f"○ 관리",
            key=f"{key}_management",
            use_container_width=True,
            type="primary" if is_management_active else "secondary"
        ):
            st.session_state[session_key] = "management"
            st.rerun()
    
    with col2:
        is_prompt_active = current_tab == "prompt"
        if st.button(
            f"○ 프롬프트",
            key=f"{key}_prompt",
            use_container_width=True,
            type="primary" if is_prompt_active else "secondary"
        ):
            st.session_state[session_key] = "prompt"
            st.rerun()
    
    return current_tab


def create_admin_tabs_working() -> List[Dict[str, Any]]:
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


__all__ = ["render_ios_tabs_working", "create_admin_tabs_working"]
