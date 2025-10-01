# Linear 레이아웃 컴포넌트 - Footer, Hero
from __future__ import annotations
from typing import List, Dict, Any, Optional
import streamlit as st


def linear_footer(
    copyright_text: str,
    links: Optional[List[Dict[str, str]]] = None,
    social_links: Optional[List[Dict[str, str]]] = None,
    variant: str = "default",
    key: Optional[str] = None
) -> None:
    """
    Linear 스타일 푸터 컴포넌트
    
    Args:
        copyright_text: 저작권 텍스트
        links: 링크 리스트 [{"label": "개인정보처리방침", "href": "/privacy"}]
        social_links: 소셜 링크 리스트 [{"label": "GitHub", "href": "https://github.com", "icon": "🐙"}]
        variant: "default", "minimal", "extended"
        key: Streamlit key
    """
    if st is None:
        return
    
    footer_key = key or "linear_footer"
    
    # 푸터 CSS
    footer_css = f"""
    <style>
    .linear-footer {{
        background: var(--linear-bg-secondary) !important;
        border-top: 1px solid var(--linear-border-primary) !important;
        padding: 2rem 0 !important;
        margin: 2rem -1rem -1rem -1rem !important;
        width: calc(100% + 2rem) !important;
    }}
    
    .linear-footer-container {{
        max-width: 1200px !important;
        margin: 0 auto !important;
        padding: 0 1rem !important;
    }}
    
    .linear-footer-content {{
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        flex-wrap: wrap !important;
        gap: 1rem !important;
    }}
    
    .linear-footer-copyright {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-normal) !important;
        font-size: var(--linear-font-size-sm) !important;
        color: var(--linear-text-tertiary) !important;
    }}
    
    .linear-footer-links {{
        display: flex !important;
        gap: 24px !important;
        list-style: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    .linear-footer-link {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-normal) !important;
        font-size: var(--linear-font-size-sm) !important;
        color: var(--linear-text-tertiary) !important;
        text-decoration: none !important;
        transition: color 0.2s ease !important;
    }}
    
    .linear-footer-link:hover {{
        color: var(--linear-text-primary) !important;
    }}
    
    .linear-footer-social {{
        display: flex !important;
        gap: 16px !important;
    }}
    
    .linear-footer-social-link {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-normal) !important;
        font-size: var(--linear-font-size-regular) !important;
        color: var(--linear-text-tertiary) !important;
        text-decoration: none !important;
        transition: color 0.2s ease !important;
    }}
    
    .linear-footer-social-link:hover {{
        color: var(--linear-text-primary) !important;
    }}
    
    @media (max-width: 768px) {{
        .linear-footer-content {{
            flex-direction: column !important;
            text-align: center !important;
        }}
        .linear-footer-links {{
            flex-direction: column !important;
            gap: 12px !important;
        }}
    }}
    </style>
    """
    
    st.markdown(footer_css, unsafe_allow_html=True)
    
    # 푸터 렌더링
    st.markdown('<footer class="linear-footer">', unsafe_allow_html=True)
    st.markdown('<div class="linear-footer-container">', unsafe_allow_html=True)
    st.markdown('<div class="linear-footer-content">', unsafe_allow_html=True)
    
    # 저작권
    st.markdown(f'<div class="linear-footer-copyright">{copyright_text}</div>', unsafe_allow_html=True)
    
    # 링크들
    if links:
        st.markdown('<ul class="linear-footer-links">', unsafe_allow_html=True)
        for link in links:
            st.markdown(f'<li><a href="{link["href"]}" class="linear-footer-link">{link["label"]}</a></li>', unsafe_allow_html=True)
        st.markdown('</ul>', unsafe_allow_html=True)
    
    # 소셜 링크들
    if social_links:
        st.markdown('<div class="linear-footer-social">', unsafe_allow_html=True)
        for social in social_links:
            icon = social.get("icon", "")
            st.markdown(f'<a href="{social["href"]}" class="linear-footer-social-link">{icon} {social["label"]}</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</footer>', unsafe_allow_html=True)


def linear_hero(
    title: str,
    subtitle: Optional[str] = None,
    background_image: Optional[str] = None,
    cta_button: Optional[Dict[str, Any]] = None,
    features: Optional[List[str]] = None,
    variant: str = "default",
    key: Optional[str] = None
) -> None:
    """
    Linear 스타일 히어로 섹션 컴포넌트
    
    Args:
        title: 메인 제목
        subtitle: 부제목 (선택사항)
        background_image: 배경 이미지 URL (선택사항)
        cta_button: CTA 버튼 {"text": "시작하기", "href": "/start", "variant": "primary"}
        features: 특징 리스트 ["특징 1", "특징 2", "특징 3"]
        variant: "default", "centered", "minimal"
        key: Streamlit key
    """
    if st is None:
        return
    
    hero_key = key or "linear_hero"
    
    # 히어로 CSS
    hero_css = f"""
    <style>
    .linear-hero {{
        background: {'url(' + background_image + ')' if background_image else 'linear-gradient(135deg, var(--linear-bg-secondary) 0%, var(--linear-bg-tertiary) 100%)'} !important;
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        padding: 4rem 0 !important;
        margin: -1rem -1rem 2rem -1rem !important;
        width: calc(100% + 2rem) !important;
        position: relative !important;
        overflow: hidden !important;
        border-top: 0.25px solid #ffffff !important;
        border-bottom: 0.25px solid #ffffff !important;
    }}
    
    .linear-hero::before {{
        content: '' !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        background: {'rgba(26, 26, 26, 0.8)' if background_image else 'transparent'} !important;
        z-index: 1 !important;
    }}
    
    .linear-hero-container {{
        max-width: 1200px !important;
        margin: 0 auto !important;
        padding: 0 1rem !important;
        position: relative !important;
        z-index: 2 !important;
    }}
    
    .linear-hero-content {{
        text-align: {'center' if variant == 'centered' else 'left'} !important;
        max-width: {'800px' if variant == 'centered' else '600px'} !important;
        margin: {'0 auto' if variant == 'centered' else '0'} !important;
    }}
    
    .linear-hero-title {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-bold) !important;
        font-size: {'3.5rem' if variant == 'minimal' else '4rem'} !important;
        line-height: 1.1 !important;
        color: var(--linear-text-primary) !important;
        margin-bottom: 1.5rem !important;
        letter-spacing: -0.02em !important;
    }}
    
    .linear-hero-subtitle {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-normal) !important;
        font-size: var(--linear-font-size-xl) !important;
        line-height: 1.6 !important;
        color: var(--linear-text-secondary) !important;
        margin-bottom: 2rem !important;
        max-width: 600px !important;
    }}
    
    .linear-hero-cta {{
        margin-bottom: 2rem !important;
    }}
    
    .linear-hero-features {{
        display: flex !important;
        gap: 24px !important;
        flex-wrap: wrap !important;
        margin-top: 2rem !important;
    }}
    
    .linear-hero-feature {{
        font-family: var(--linear-font-primary) !important;
        font-weight: var(--linear-font-weight-medium) !important;
        font-size: var(--linear-font-size-regular) !important;
        color: var(--linear-text-primary) !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }}
    
    .linear-hero-feature::before {{
        content: '✓' !important;
        color: var(--linear-brand) !important;
        font-weight: var(--linear-font-weight-semibold) !important;
    }}
    
    @media (max-width: 768px) {{
        .linear-hero-title {{
            font-size: 2.5rem !important;
        }}
        .linear-hero-subtitle {{
            font-size: var(--linear-font-size-lg) !important;
        }}
        .linear-hero-features {{
            flex-direction: column !important;
            gap: 12px !important;
        }}
    }}
    </style>
    """
    
    st.markdown(hero_css, unsafe_allow_html=True)
    
    # 히어로 렌더링
    st.markdown('<section class="linear-hero">', unsafe_allow_html=True)
    st.markdown('<div class="linear-hero-container">', unsafe_allow_html=True)
    st.markdown('<div class="linear-hero-content">', unsafe_allow_html=True)
    
    # 제목
    st.markdown(f'<h1 class="linear-hero-title">{title}</h1>', unsafe_allow_html=True)
    
    # 부제목
    if subtitle:
        st.markdown(f'<p class="linear-hero-subtitle">{subtitle}</p>', unsafe_allow_html=True)
    
    # CTA 버튼
    if cta_button:
        st.markdown('<div class="linear-hero-cta">', unsafe_allow_html=True)
        cta_key = f"hero_cta_{hero_key}"
        from src.ui.components.linear_components import linear_button
        if linear_button(
            cta_button["text"], 
            variant=cta_button.get("variant", "primary"),
            size="large",
            key=cta_key
        ):
            if "callback" in cta_button:
                cta_button["callback"]()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 특징들
    if features:
        st.markdown('<div class="linear-hero-features">', unsafe_allow_html=True)
        for feature in features:
            st.markdown(f'<div class="linear-hero-feature">{feature}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</section>', unsafe_allow_html=True)
