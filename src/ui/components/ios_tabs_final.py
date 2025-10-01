# 최종 iOS 스타일 탭 시스템 (HTML/CSS + JavaScript)
from __future__ import annotations
from typing import Any, Dict, List

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs_final(
    tabs: List[Dict[str, Any]],
    active_tab: str = "management",
    key: str = "ios_tabs"
) -> str:
    """
    HTML/CSS/JavaScript를 사용한 진짜 iOS 스타일 탭 시스템
    
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
    
    # iOS 스타일 탭 HTML/CSS/JavaScript
    tab_html = f"""
    <style>
    .ios-tabs-container {{
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
    }}
    
    .ios-tab {{
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
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
        text-decoration: none;
    }}
    
    .ios-tab:hover {{
        background: #f2f2f7;
        color: #000000;
    }}
    
    .ios-tab.active {{
        color: #007aff;
        font-weight: 600;
    }}
    
    .ios-tab.active::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 32px;
        height: 3px;
        background: #007aff;
        border-radius: 2px;
    }}
    
    .ios-tab-icon {{
        margin-right: 6px;
        font-size: 18px;
    }}
    
    /* 모바일 최적화 */
    @media (max-width: 768px) {{
        .ios-tabs-container {{
            margin: 0 -0.5rem 1rem -0.5rem;
            padding: 0 0.5rem;
        }}
        
        .ios-tab {{
            padding: 16px 8px;
            font-size: 17px;
            min-height: 48px;
        }}
        
        .ios-tab-icon {{
            font-size: 20px;
        }}
    }}
    </style>
    
    <div class="ios-tabs-container">
    """
    
    for tab in tabs:
        is_active = tab["id"] == current_tab
        tab_class = "ios-tab active" if is_active else "ios-tab"
        
        tab_html += f'''
        <a href="#" class="{tab_class}" onclick="
            // 탭 변경을 위한 JavaScript
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = window.location.href;
            
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = '{key}_tab_change';
            input.value = '{tab["id"]}';
            form.appendChild(input);
            
            document.body.appendChild(form);
            form.submit();
            
            return false;
        ">
            <span class="ios-tab-icon">{tab.get("icon", "")}</span>
            {tab["label"]}
        </a>
        '''
    
    tab_html += "</div>"
    
    # 탭 변경 감지
    tab_change_key = f"{key}_tab_change"
    if tab_change_key in st.session_state:
        new_tab = st.session_state[tab_change_key]
        st.session_state[session_key] = new_tab
        current_tab = new_tab
        # 세션 상태 정리
        if tab_change_key in st.session_state:
            del st.session_state[tab_change_key]
        st.rerun()
    
    # HTML 렌더링
    st.markdown(tab_html, unsafe_allow_html=True)
    
    return current_tab


def create_admin_tabs_final() -> List[Dict[str, Any]]:
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


__all__ = ["render_ios_tabs_final", "create_admin_tabs_final"]
