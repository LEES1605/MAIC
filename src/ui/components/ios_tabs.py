# iOS 스타일 탭 시스템 컴포넌트
from __future__ import annotations
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except Exception:
    st = None


def render_ios_tabs(
    tabs: List[Dict[str, Any]],
    active_tab: Optional[str] = None,
    key: str = "ios_tabs"
) -> str:
    """
    iOS 스타일 탭 시스템 렌더링
    
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
    
    .ios-tab {
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
    }
    
    .ios-tab:hover {
        background: #f2f2f7;
        color: #000000;
    }
    
    .ios-tab.active {
        color: #007aff;
        font-weight: 600;
    }
    
    .ios-tab.active::after {
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
        
        .ios-tab {
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
    
    # 기본 활성 탭 설정
    if active_tab is None:
        active_tab = st.session_state.get(f"{key}_active", tabs[0]["id"]) or tabs[0]["id"]
    
    # 탭 컨테이너 생성
    tab_container = st.container()
    
    with tab_container:
        # 탭 버튼들 렌더링
        cols = st.columns(len(tabs))
        
        for i, tab in enumerate(tabs):
            with cols[i]:
                is_active = tab["id"] == active_tab
                tab_class = "ios-tab active" if is_active else "ios-tab"
                
                # HTML로 탭 버튼 생성
                tab_html = f'''
                <button class="{tab_class}" data-tab-id="{tab["id"]}">
                    <span class="ios-tab-icon">{tab.get("icon", "")}</span>
                    {tab["label"]}
                </button>
                '''
                
                st.markdown(tab_html, unsafe_allow_html=True)
        
        # JavaScript로 탭 변경 처리 (Streamlit 호환)
        st.markdown(f"""
        <script>
        // 탭 변경 이벤트 리스너
        window.addEventListener('tab_change', function(event) {{
            const tabId = event.detail;
            
            // Streamlit 세션 상태 업데이트
            const event = new CustomEvent('streamlit:setComponentValue', {{
                detail: {{key: '{key}_active', value: tabId}}
            }});
            window.dispatchEvent(event);
            
            // 페이지 새로고침
            window.location.reload();
        }});
        
        // 탭 버튼 클릭 이벤트 추가
        document.addEventListener('DOMContentLoaded', function() {{
            const tabButtons = document.querySelectorAll('.ios-tab');
            tabButtons.forEach(button => {{
                button.addEventListener('click', function() {{
                    const tabId = this.getAttribute('data-tab-id');
                    if (tabId) {{
                        const event = new CustomEvent('tab_change', {{detail: tabId}});
                        window.dispatchEvent(event);
                    }}
                }});
            }});
        }});
        </script>
        """, unsafe_allow_html=True)
    
    # 탭 변경 감지
    if "tab_change" in st.session_state:
        active_tab = st.session_state["tab_change"]
        st.session_state[f"{key}_active"] = active_tab
    
    # 세션 상태에 현재 탭 저장
    st.session_state[f"{key}_active"] = active_tab
    
    return active_tab or tabs[0]["id"]


def create_admin_tabs() -> List[Dict[str, Any]]:
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


__all__ = ["render_ios_tabs", "create_admin_tabs"]
