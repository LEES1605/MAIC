# 통합된 iOS 스타일 탭 시스템 (브라우저 탭처럼)
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs_unified(
    tabs: List[Dict[str, Any]],
    active_tab: str = "management",
    key: str = "ios_tabs"
) -> str:
    """
    통합된 iOS 스타일 탭 시스템 (브라우저 탭처럼)
    
    Args:
        tabs: 탭 정보 리스트 [{"id": "tab1", "label": "관리", "icon": "○"}, ...]
        active_tab: 현재 활성 탭 ID
        key: Streamlit key
    
    Returns:
        선택된 탭 ID
    """
    if st is None or not tabs:
        return tabs[0]["id"] if tabs else ""
    
    # 통합된 탭바 CSS (브라우저 탭 스타일)
    st.markdown("""
    <style>
    .unified-tabs-container {
        background: #ffffff;
        border-bottom: 1px solid #e5e5e7;
        margin: 0 -1rem 1rem -1rem;
        padding: 0 1rem;
        position: sticky;
        top: 0;
        z-index: 100;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        display: flex;
        align-items: center;
        min-height: 48px;
    }
    
    .unified-tab {
        flex: 1;
        padding: 12px 16px;
        border: none;
        background: transparent;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 16px;
        font-weight: 500;
        color: #8e8e93;
        position: relative;
        min-height: 44px;
        border-radius: 8px 8px 0 0;
        margin: 0 2px;
        text-align: center;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
    }
    
    .unified-tab:hover {
        background: #f2f2f7;
        color: #000000;
    }
    
    .unified-tab.active {
        color: #007aff;
        font-weight: 600;
        background: #ffffff;
        border-bottom: 3px solid #007aff;
        box-shadow: 0 -2px 8px rgba(0,122,255,0.1);
    }
    
    .unified-tab-icon {
        font-size: 18px;
        color: inherit;
    }
    
    .unified-tab.active .unified-tab-icon {
        color: #007aff;
    }
    
    /* 모바일 최적화 */
    @media (max-width: 768px) {
        .unified-tabs-container {
            margin: 0 -0.5rem 1rem -0.5rem;
            padding: 0 0.5rem;
            min-height: 52px;
        }
        
        .unified-tab {
            padding: 16px 12px;
            font-size: 17px;
            min-height: 48px;
        }
        
        .unified-tab-icon {
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
    
    # 통합된 탭바 HTML 생성
    tabs_html = '<div class="unified-tabs-container">'
    
    for tab in tabs:
        is_active = tab["id"] == current_tab
        tab_class = "unified-tab active" if is_active else "unified-tab"
        
        tabs_html += f'''
        <button class="{tab_class}" onclick="
            // 즉시 탭 변경 (빠른 응답)
            const form = document.createElement('form');
            form.method = 'POST';
            form.style.display = 'none';
            
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = '{key}_tab_change';
            input.value = '{tab["id"]}';
            form.appendChild(input);
            
            document.body.appendChild(form);
            form.submit();
            
            return false;
        ">
            <span class="unified-tab-icon">{tab.get("icon", "")}</span>
            {tab["label"]}
        </button>
        '''
    
    tabs_html += '</div>'
    
    # 탭 변경 감지 (빠른 처리)
    tab_change_key = f"{key}_tab_change"
    if tab_change_key in st.session_state:
        new_tab = st.session_state[tab_change_key]
        st.session_state[session_key] = new_tab
        current_tab = new_tab
        # 세션 상태 정리
        if tab_change_key in st.session_state:
            del st.session_state[tab_change_key]
        # 즉시 페이지 새로고침
        st.rerun()
    
    # HTML 렌더링
    st.markdown(tabs_html, unsafe_allow_html=True)
    
    return current_tab


def create_admin_tabs_unified() -> List[Dict[str, Any]]:
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


__all__ = ["render_ios_tabs_unified", "create_admin_tabs_unified"]
