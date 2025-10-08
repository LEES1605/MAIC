# Linear 레이아웃 컴포넌트들 (수정된 버전)
from __future__ import annotations
import streamlit as st
from typing import Any, Dict, List, Optional, Union


def linear_hero(
    title: str = "Welcome",
    subtitle: str = "",
    **kwargs
) -> None:
    """
    Linear 스타일 히어로 섹션 컴포넌트
    
    Args:
        title: 메인 제목
        subtitle: 부제목
        **kwargs: 추가 인자
    """
    if st is None:
        return
    
    # 히어로 섹션 스타일 CSS 적용
    hero_css = """
    <style>
    .linear-hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%) !important;
        padding: 60px 20px !important;
        text-align: center !important;
        border-radius: 16px !important;
        margin: 20px 0 !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    .linear-hero::before {
        content: '' !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%) !important;
        z-index: 1 !important;
    }
    
    .linear-hero-content {
        position: relative !important;
        z-index: 2 !important;
    }
    
    .linear-hero-title {
        font-family: var(--linear-font) !important;
        font-weight: 700 !important;
        font-size: 3rem !important;
        line-height: 1.2 !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        margin-bottom: 16px !important;
    }
    
    .linear-hero-subtitle {
        font-family: var(--linear-font) !important;
        font-weight: 400 !important;
        font-size: 1.25rem !important;
        color: var(--linear-text-secondary) !important;
        margin-bottom: 0 !important;
    }
    
    @media (max-width: 768px) {
        .linear-hero-title {
            font-size: 2rem !important;
        }
        
        .linear-hero-subtitle {
            font-size: 1rem !important;
        }
    }
    </style>
    """
    
    st.markdown(hero_css, unsafe_allow_html=True)
    
    # 히어로 섹션 렌더링
    st.markdown("""
    <div class="linear-hero">
        <div class="linear-hero-content">
            <h1 class="linear-hero-title">{}</h1>
            <p class="linear-hero-subtitle">{}</p>
        </div>
    </div>
    """.format(title, subtitle), unsafe_allow_html=True)


def linear_footer(
    copyright_text: str = "© 2024 Linear App",
    **kwargs
) -> None:
    """
    Linear 스타일 푸터 컴포넌트
    
    Args:
        copyright_text: 저작권 텍스트
        **kwargs: 추가 인자
    """
    if st is None:
        return
    
    # 푸터 스타일 CSS 적용
    footer_css = """
    <style>
    .linear-footer {
        background: var(--linear-bg-primary) !important;
        border-top: 1px solid var(--linear-border) !important;
        padding: 20px 0 !important;
        margin-top: 40px !important;
        text-align: center !important;
    }
    
    .linear-footer-text {
        font-family: var(--linear-font) !important;
        font-size: 0.875rem !important;
        color: var(--linear-text-tertiary) !important;
        margin: 0 !important;
    }
    </style>
    """
    
    st.markdown(footer_css, unsafe_allow_html=True)
    st.markdown(f'<div class="linear-footer"><p class="linear-footer-text">{copyright_text}</p></div>', unsafe_allow_html=True)



