# 배경 및 전체 레이아웃 스타일 컴포넌트
from __future__ import annotations
import streamlit as st

def get_background_styles_css() -> str:
    """배경 및 전체 레이아웃 스타일 CSS"""
    return """
    <style>
    /* 전체 앱 배경 그라디언트 */
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%) !important;
        min-height: 100vh !important;
    }
    
    /* 메인 컨테이너 배경 */
    .main .block-container {
        background: transparent !important;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* 전체 페이지 배경 */
    .main {
        background: transparent !important;
    }
    
    /* 스크롤바 스타일링 */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
    }
    </style>
    """

def apply_background_styles() -> None:
    """배경 스타일 적용"""
    if st is None:
        return
    
    try:
        st.markdown(get_background_styles_css(), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"배경 스타일 적용 오류: {e}")


