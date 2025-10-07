# 모드 선택 UI 컴포넌트
from __future__ import annotations
import streamlit as st
from typing import Optional

def get_mode_selector_css() -> str:
    """모드 선택 칩 스타일 CSS - 강력한 선택자 사용"""
    return """
    <style>
    .mode-chips {
        display: flex;
        gap: 8px;
        justify-content: center;
        margin: 1rem 0;
        flex-wrap: wrap;
    }
    
    .mode-section-title {
        text-align: center;
        font-family: var(--linear-font);
        font-size: 1rem;
        font-weight: 600;
        color: var(--linear-text-primary);
        margin-bottom: 0.5rem;
    }
    
    /* Streamlit 버튼 강제 스타일링 */
    div[data-testid="column"] button[kind="secondary"] {
        padding: 8px 16px !important;
        border-radius: 20px !important;
        border: 1px solid var(--linear-border) !important;
        background: var(--linear-bg-secondary) !important;
        color: var(--linear-text-secondary) !important;
        font-family: var(--linear-font) !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        text-align: center !important;
        min-width: 60px !important;
        box-shadow: none !important;
    }
    
    div[data-testid="column"] button[kind="secondary"]:hover {
        background: var(--linear-bg-tertiary) !important;
        border-color: var(--linear-border-hover) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
    
    /* 선택된 버튼 스타일 (세션 상태 기반) */
    div[data-testid="column"] button[kind="secondary"]:focus {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-color: transparent !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* 모든 버튼에 기본 스타일 적용 */
    .stButton > button {
        padding: 8px 16px !important;
        border-radius: 20px !important;
        border: 1px solid var(--linear-border) !important;
        background: var(--linear-bg-secondary) !important;
        color: var(--linear-text-secondary) !important;
        font-family: var(--linear-font) !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        text-align: center !important;
        min-width: 60px !important;
        box-shadow: none !important;
    }
    
    .stButton > button:hover {
        background: var(--linear-bg-tertiary) !important;
        border-color: var(--linear-border-hover) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
    </style>
    """

def render_mode_selector() -> Optional[str]:
    """모드 선택 UI 렌더링 - Linear 컴포넌트 사용"""
    if st is None:
        return None
    
    try:
        # Linear 컴포넌트 import
        from .linear_components import linear_chip
        
        # 현재 선택된 모드 가져오기
        current_mode = st.session_state.get("__mode", "")
        
        # 모드 선택 UI
        st.markdown('<div class="mode-section-title">질문 모드</div>', unsafe_allow_html=True)
        
        # 칩 컨테이너
        st.markdown('<div class="mode-chips">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 문법 모드 칩 - Linear 컴포넌트 사용
            if linear_chip(
                "문법", 
                key="mode_grammar", 
                selected=(current_mode == "grammar"),
                help="문법 관련 질문"
            ):
                st.session_state["__mode"] = "grammar"
                st.rerun()
        
        with col2:
            # 독해 모드 칩 - Linear 컴포넌트 사용
            if linear_chip(
                "독해", 
                key="mode_reading", 
                selected=(current_mode == "reading"),
                help="독해 관련 질문"
            ):
                st.session_state["__mode"] = "reading"
                st.rerun()
        
        with col3:
            # 작문 모드 칩 - Linear 컴포넌트 사용
            if linear_chip(
                "작문", 
                key="mode_writing", 
                selected=(current_mode == "writing"),
                help="작문 관련 질문"
            ):
                st.session_state["__mode"] = "writing"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        return current_mode
    except Exception as e:
        st.error(f"모드 선택 UI 오류: {e}")
        return None
