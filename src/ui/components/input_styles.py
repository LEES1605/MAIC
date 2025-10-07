# 입력 필드 및 버튼 스타일 컴포넌트
from __future__ import annotations
import streamlit as st

def get_input_styles_css() -> str:
    """입력 필드 및 버튼 스타일 CSS - 강력한 선택자 사용"""
    return """
    <style>
    /* 질문 입력 필드 스타일 - 강력한 선택자 */
    div[data-testid="stTextInput"] input {
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border) !important;
        border-radius: 12px !important;
        color: var(--linear-text-primary) !important;
        font-family: var(--linear-font) !important;
        font-size: 1rem !important;
        padding: 12px 16px !important;
        transition: all 0.2s ease !important;
    }
    
    div[data-testid="stTextInput"] input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
        outline: none !important;
    }
    
    div[data-testid="stTextInput"] input::placeholder {
        color: var(--linear-text-tertiary) !important;
    }
    
    /* 재생 버튼 스타일 - 폼 내부 버튼 */
    div[data-testid="stForm"] button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        border-radius: 12px !important;
        color: white !important;
        font-family: var(--linear-font) !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        padding: 12px 24px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3) !important;
    }
    
    div[data-testid="stForm"] button:hover {
        background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* 질문 라벨 스타일 */
    div[data-testid="stTextInput"] label {
        color: var(--linear-text-primary) !important;
        font-family: var(--linear-font) !important;
        font-weight: 500 !important;
        font-size: 1rem !important;
        margin-bottom: 8px !important;
    }
    
    /* 폼 컨테이너 스타일 */
    div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    
    /* 입력 필드와 버튼 간격 조정 */
    div[data-testid="stForm"] > div {
        display: flex !important;
        flex-direction: column !important;
        gap: 16px !important;
    }
    
    /* 추가: 모든 Streamlit 입력 필드 기본 스타일 */
    .stTextInput > div > div > input {
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border) !important;
        border-radius: 12px !important;
        color: var(--linear-text-primary) !important;
        font-family: var(--linear-font) !important;
        font-size: 1rem !important;
        padding: 12px 16px !important;
        transition: all 0.2s ease !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
        outline: none !important;
    }
    </style>
    """

def apply_input_styles() -> None:
    """입력 필드 스타일 적용 - Linear 컴포넌트 사용"""
    if st is None:
        return
    
    try:
        # Linear 컴포넌트 import
        from .linear_components import linear_gradient_button
        
        # CSS 스타일 적용
        st.markdown(get_input_styles_css(), unsafe_allow_html=True)
        
        # 그라디언트 버튼 스타일도 적용
        st.markdown("""
        <style>
        /* 재생 버튼을 Linear 그라디언트 버튼으로 스타일링 */
        div[data-testid="stForm"] button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            border: none !important;
            border-radius: 12px !important;
            color: white !important;
            font-family: var(--linear-font) !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
            padding: 12px 24px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3) !important;
        }
        
        div[data-testid="stForm"] button:hover {
            background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"입력 필드 스타일 적용 오류: {e}")
