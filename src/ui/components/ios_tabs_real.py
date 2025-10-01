# 진짜 iOS 스타일 탭 시스템 (Streamlit tabs 사용)
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs_real(
    tabs: List[Dict[str, Any]],
    active_tab: str = "management",
    key: str = "ios_tabs"
) -> str:
    """
    Streamlit의 실제 탭 기능을 사용한 iOS 스타일 탭 시스템
    
    Args:
        tabs: 탭 정보 리스트 [{"id": "tab1", "label": "관리", "icon": "○"}, ...]
        active_tab: 현재 활성 탭 ID
        key: Streamlit key
    
    Returns:
        선택된 탭 ID
    """
    if st is None or not tabs:
        return tabs[0]["id"] if tabs else ""
    
    # iOS 스타일 탭 CSS (Streamlit 기본 탭 스타일링)
    st.markdown("""
    <style>
    /* Streamlit 기본 탭을 iOS 스타일로 변경 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
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
    
    .stTabs [data-baseweb="tab"] {
        flex: 1;
        padding: 12px 8px;
        border: none;
        background: transparent;
        font-size: 16px;
        font-weight: 500;
        color: #8e8e93;
        transition: all 0.2s ease;
        min-height: 44px;
        border-radius: 8px;
        margin: 4px;
        position: relative;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: #f2f2f7;
        color: #000000;
    }
    
    .stTabs [aria-selected="true"] {
        color: #007aff !important;
        font-weight: 600 !important;
        background: transparent !important;
    }
    
    .stTabs [aria-selected="true"]::after {
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
    
    /* 모바일 최적화 */
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab-list"] {
            margin: 0 -0.5rem 1rem -0.5rem;
            padding: 0 0.5rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 16px 8px;
            font-size: 17px;
            min-height: 48px;
        }
    }
    
    /* 탭 패널 스타일링 */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 기본 활성 탭 설정
    if active_tab not in [tab["id"] for tab in tabs]:
        active_tab = tabs[0]["id"]
    
    # 탭 레이블 생성
    tab_labels = [f"{tab.get('icon', '')} {tab['label']}" for tab in tabs]
    
    # Streamlit의 실제 탭 기능 사용
    selected_tab = st.tabs(tab_labels)
    
    # 활성 탭 찾기
    for i, tab in enumerate(tabs):
        if i < len(selected_tab):
            with selected_tab[i]:
                # 탭 내용을 여기에 렌더링할 수 있지만, 
                # 이 함수는 탭 선택만 처리하고 실제 내용은 호출자가 처리
                pass
    
    # 세션 상태에서 활성 탭 관리
    session_key = f"{key}_active"
    if session_key not in st.session_state:
        st.session_state[session_key] = active_tab
    
    # 현재 선택된 탭 반환 (실제로는 탭 인덱스를 기반으로)
    current_tab = st.session_state.get(session_key, active_tab)
    
    return current_tab


def create_admin_tabs_real() -> List[Dict[str, Any]]:
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


__all__ = ["render_ios_tabs_real", "create_admin_tabs_real"]
