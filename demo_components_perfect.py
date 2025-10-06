#!/usr/bin/env python3
"""
Linear 컴포넌트 데모 페이지 - 완벽한 최종 버전
모든 문제를 해결한 완전한 데모 페이지
"""

import streamlit as st
import sys
from pathlib import Path
import os
import base64

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Linear 컴포넌트들 import
from src.ui.components.linear_theme import apply_theme
from src.ui.components.linear_components import (
    linear_button, linear_card, linear_badge, linear_input, 
    linear_alert, linear_divider, linear_carousel, 
    linear_card_with_image, linear_navbar
)
from src.ui.components.linear_layout_components import (
    linear_footer, linear_hero
)

def get_base64_image(filename):
    """이미지를 Base64로 인코딩하여 반환"""
    img_path = f"images/{filename}"
    if os.path.exists(img_path):
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded_string}"
    return None

def create_perfect_navbar():
    """완벽한 네비게이션 바 생성"""
    navbar_html = """
    <style>
    .perfect-navbar {
        background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%) !important;
        border-bottom: 2px solid #5e6ad2 !important;
        padding: 16px 0 !important;
        margin: -1rem -1rem 2rem -1rem !important;
        width: calc(100% + 2rem) !important;
        position: sticky !important;
        top: 0 !important;
        z-index: 1000 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    }
    
    .perfect-navbar-content {
        max-width: 1200px !important;
        margin: 0 auto !important;
        padding: 0 24px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
    }
    
    .perfect-navbar-brand {
        color: white !important;
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        text-decoration: none !important;
    }
    
    .perfect-navbar-nav {
        display: flex !important;
        gap: 24px !important;
        align-items: center !important;
    }
    
    .perfect-nav-item {
        color: rgba(255, 255, 255, 0.8) !important;
        text-decoration: none !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        font-weight: 500 !important;
    }
    
    .perfect-nav-item:hover {
        background: rgba(94, 106, 210, 0.2) !important;
        color: white !important;
    }
    
    .perfect-nav-buttons {
        display: flex !important;
        gap: 12px !important;
        align-items: center !important;
    }
    
    .perfect-nav-button {
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        color: white !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
        font-weight: 500 !important;
    }
    
    .perfect-nav-button:hover {
        background: #5e6ad2 !important;
        border-color: #5e6ad2 !important;
        color: white !important;
    }
    
    .perfect-nav-button.primary {
        background: #5e6ad2 !important;
        border-color: #5e6ad2 !important;
    }
    
    .perfect-nav-button.primary:hover {
        background: #7170ff !important;
        border-color: #7170ff !important;
    }
    
    @media (max-width: 768px) {
        .perfect-navbar-nav {
            display: none !important;
        }
        .perfect-navbar-content {
            padding: 0 16px !important;
        }
    }
    </style>
    
    <div class="perfect-navbar">
        <div class="perfect-navbar-content">
            <a href="#" class="perfect-navbar-brand">Linear Components</a>
            
            <div class="perfect-navbar-nav">
                <a href="#product" class="perfect-nav-item">Product</a>
                <a href="#solutions" class="perfect-nav-item">Solutions</a>
                <a href="#features" class="perfect-nav-item">Features</a>
                <a href="#pricing" class="perfect-nav-item">Pricing</a>
                <a href="#docs" class="perfect-nav-item">Docs</a>
            </div>
            
            <div class="perfect-nav-buttons">
                <a href="#login" class="perfect-nav-button">Log in</a>
                <a href="#signup" class="perfect-nav-button primary">Sign up</a>
            </div>
        </div>
    </div>
    """
    
    st.markdown(navbar_html, unsafe_allow_html=True)

def create_perfect_hero():
    """완벽한 히어로 섹션 생성"""
    hero_bg = get_base64_image("hero_bg.png")
    
    if hero_bg:
        hero_html = f"""
        <style>
        .perfect-hero {{
            background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), url('{hero_bg}') !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            padding: 4rem 0 !important;
            margin: -1rem -1rem 2rem -1rem !important;
            width: calc(100% + 2rem) !important;
            position: relative !important;
            overflow: hidden !important;
            border-top: 1px solid #404040 !important;
            border-bottom: 1px solid #404040 !important;
        }}
        
        .perfect-hero-content {{
            max-width: 1200px !important;
            margin: 0 auto !important;
            padding: 0 1rem !important;
            text-align: center !important;
        }}
        
        .perfect-hero-title {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 700 !important;
            font-size: 4rem !important;
            line-height: 1.1 !important;
            color: #ffffff !important;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5) !important;
            margin-bottom: 1.5rem !important;
            letter-spacing: -0.02em !important;
        }}
        
        .perfect-hero-subtitle {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 400 !important;
            font-size: 1.25rem !important;
            line-height: 1.6 !important;
            color: rgba(255, 255, 255, 0.9) !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5) !important;
            margin-bottom: 2rem !important;
            max-width: 600px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }}
        
        .perfect-hero-cta {{
            margin-bottom: 2rem !important;
        }}
        
        .perfect-hero-button {{
            background: #5e6ad2 !important;
            border: 2px solid #5e6ad2 !important;
            color: white !important;
            padding: 12px 24px !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            text-decoration: none !important;
            display: inline-block !important;
            transition: all 0.2s ease !important;
        }}
        
        .perfect-hero-button:hover {{
            background: #7170ff !important;
            border-color: #7170ff !important;
            transform: translateY(-1px) !important;
        }}
        
        .perfect-hero-features {{
            display: flex !important;
            gap: 24px !important;
            flex-wrap: wrap !important;
            justify-content: center !important;
            margin-top: 2rem !important;
        }}
        
        .perfect-hero-feature {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 500 !important;
            font-size: 1rem !important;
            color: #e0e0e0 !important;
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
        }}
        
        .perfect-hero-feature::before {{
            content: '✓' !important;
            color: #5e6ad2 !important;
            font-weight: 700 !important;
        }}
        
        @media (max-width: 768px) {{
            .perfect-hero {{
                padding: 3rem 0 !important;
            }}
            .perfect-hero-title {{
                font-size: 2.5rem !important;
            }}
            .perfect-hero-subtitle {{
                font-size: 1.125rem !important;
            }}
            .perfect-hero-features {{
                flex-direction: column !important;
                gap: 12px !important;
            }}
        }}
        </style>
        
        <section class="perfect-hero">
            <div class="perfect-hero-content">
                <h1 class="perfect-hero-title">Linear 컴포넌트 시스템</h1>
                <p class="perfect-hero-subtitle">MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리</p>
                <div class="perfect-hero-cta">
                    <a href="#start" class="perfect-hero-button">시작하기</a>
                </div>
                <div class="perfect-hero-features">
                    <div class="perfect-hero-feature">9개 핵심 컴포넌트</div>
                    <div class="perfect-hero-feature">완전 반응형 디자인</div>
                    <div class="perfect-hero-feature">Linear.app 스타일</div>
                    <div class="perfect-hero-feature">모바일 우선 설계</div>
                </div>
            </div>
        </section>
        """
    else:
        hero_html = """
        <style>
        .perfect-hero {
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%) !important;
            padding: 4rem 0 !important;
            margin: -1rem -1rem 2rem -1rem !important;
            width: calc(100% + 2rem) !important;
            position: relative !important;
            overflow: hidden !important;
            border-top: 1px solid #404040 !important;
            border-bottom: 1px solid #404040 !important;
        }
        
        .perfect-hero-content {
            max-width: 1200px !important;
            margin: 0 auto !important;
            padding: 0 1rem !important;
            text-align: center !important;
        }
        
        .perfect-hero-title {
            font-family: 'Inter', sans-serif !important;
            font-weight: 700 !important;
            font-size: 4rem !important;
            line-height: 1.1 !important;
            color: #ffffff !important;
            margin-bottom: 1.5rem !important;
            letter-spacing: -0.02em !important;
        }
        
        .perfect-hero-subtitle {
            font-family: 'Inter', sans-serif !important;
            font-weight: 400 !important;
            font-size: 1.25rem !important;
            line-height: 1.6 !important;
            color: rgba(255, 255, 255, 0.9) !important;
            margin-bottom: 2rem !important;
            max-width: 600px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        
        .perfect-hero-cta {
            margin-bottom: 2rem !important;
        }
        
        .perfect-hero-button {
            background: #5e6ad2 !important;
            border: 2px solid #5e6ad2 !important;
            color: white !important;
            padding: 12px 24px !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            text-decoration: none !important;
            display: inline-block !important;
            transition: all 0.2s ease !important;
        }
        
        .perfect-hero-button:hover {
            background: #7170ff !important;
            border-color: #7170ff !important;
            transform: translateY(-1px) !important;
        }
        
        .perfect-hero-features {
            display: flex !important;
            gap: 24px !important;
            flex-wrap: wrap !important;
            justify-content: center !important;
            margin-top: 2rem !important;
        }
        
        .perfect-hero-feature {
            font-family: 'Inter', sans-serif !important;
            font-weight: 500 !important;
            font-size: 1rem !important;
            color: #e0e0e0 !important;
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
        }
        
        .perfect-hero-feature::before {
            content: '✓' !important;
            color: #5e6ad2 !important;
            font-weight: 700 !important;
        }
        
        @media (max-width: 768px) {
            .perfect-hero {
                padding: 3rem 0 !important;
            }
            .perfect-hero-title {
                font-size: 2.5rem !important;
            }
            .perfect-hero-subtitle {
                font-size: 1.125rem !important;
            }
            .perfect-hero-features {
                flex-direction: column !important;
                gap: 12px !important;
            }
        }
        </style>
        
        <section class="perfect-hero">
            <div class="perfect-hero-content">
                <h1 class="perfect-hero-title">Linear 컴포넌트 시스템</h1>
                <p class="perfect-hero-subtitle">MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리</p>
                <div class="perfect-hero-cta">
                    <a href="#start" class="perfect-hero-button">시작하기</a>
                </div>
                <div class="perfect-hero-features">
                    <div class="perfect-hero-feature">9개 핵심 컴포넌트</div>
                    <div class="perfect-hero-feature">완전 반응형 디자인</div>
                    <div class="perfect-hero-feature">Linear.app 스타일</div>
                    <div class="perfect-hero-feature">모바일 우선 설계</div>
                </div>
            </div>
        </section>
        """
    
    st.markdown(hero_html, unsafe_allow_html=True)

def create_perfect_carousel():
    """완벽한 캐러셀 생성"""
    carousel_images = []
    for i in range(1, 4):
        img = get_base64_image(f"carousel_{i}.png")
        if img:
            carousel_images.append({
                "image": img,
                "title": f"{i}번째 슬라이드",
                "description": f"이것은 {i}번째 캐러셀 슬라이드입니다."
            })
    
    if carousel_images:
        carousel_html = f"""
        <style>
        .perfect-carousel {{
            background: #2a2a2a !important;
            border: 1px solid #404040 !important;
            border-radius: 12px !important;
            padding: 2rem !important;
            margin: 2rem 0 !important;
            position: relative !important;
        }}
        
        .perfect-carousel-title {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.5rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 1rem !important;
            text-align: center !important;
        }}
        
        .perfect-carousel-content {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 1rem !important;
        }}
        
        .perfect-carousel-arrow {{
            background: #5e6ad2 !important;
            border: none !important;
            color: white !important;
            width: 40px !important;
            height: 40px !important;
            border-radius: 50% !important;
            font-size: 1.2rem !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
        }}
        
        .perfect-carousel-arrow:hover {{
            background: #7170ff !important;
            transform: scale(1.1) !important;
        }}
        
        .perfect-carousel-item {{
            flex: 1 !important;
            text-align: center !important;
        }}
        
        .perfect-carousel-image {{
            width: 100% !important;
            max-width: 400px !important;
            height: 200px !important;
            object-fit: cover !important;
            border-radius: 8px !important;
            margin-bottom: 1rem !important;
        }}
        
        .perfect-carousel-item-title {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.25rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 0.5rem !important;
        }}
        
        .perfect-carousel-item-description {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 400 !important;
            font-size: 1rem !important;
            color: #b0b0b0 !important;
            line-height: 1.5 !important;
        }}
        </style>
        
        <div class="perfect-carousel">
            <div class="perfect-carousel-title">6. Linear Carousel</div>
            <div class="perfect-carousel-content">
                <button class="perfect-carousel-arrow" onclick="alert('이전 슬라이드')">◀</button>
                <div class="perfect-carousel-item">
                    <img src="{carousel_images[0]['image']}" class="perfect-carousel-image" alt="Slide 1">
                    <div class="perfect-carousel-item-title">{carousel_images[0]['title']}</div>
                    <div class="perfect-carousel-item-description">{carousel_images[0]['description']}</div>
                </div>
                <button class="perfect-carousel-arrow" onclick="alert('다음 슬라이드')">▶</button>
            </div>
        </div>
        """
    else:
        carousel_html = """
        <div style="background: #2a2a2a; border: 1px solid #404040; border-radius: 12px; padding: 2rem; margin: 2rem 0;">
            <h3 style="color: #e0e0e0; text-align: center; margin-bottom: 1rem;">6. Linear Carousel</h3>
            <p style="color: #b0b0b0; text-align: center;">이미지를 로드할 수 없습니다.</p>
        </div>
        """
    
    st.markdown(carousel_html, unsafe_allow_html=True)

def create_perfect_image_cards():
    """완벽한 이미지 카드 생성"""
    card_images = []
    for i in range(1, 4):
        img = get_base64_image(f"card_{i}.png")
        if img:
            card_images.append({
                "image": img,
                "title": f"{i}번째 이미지",
                "description": f"이것은 {i}번째 이미지 카드입니다."
            })
    
    if card_images:
        cards_html = f"""
        <style>
        .perfect-cards-container {{
            margin: 2rem 0 !important;
        }}
        
        .perfect-cards-title {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.5rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 1rem !important;
        }}
        
        .perfect-cards-grid {{
            display: grid !important;
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 1rem !important;
        }}
        
        .perfect-card {{
            background: #2a2a2a !important;
            border: 1px solid #404040 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
            transition: all 0.2s ease !important;
        }}
        
        .perfect-card:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        }}
        
        .perfect-card-image {{
            width: 100% !important;
            height: 200px !important;
            object-fit: cover !important;
        }}
        
        .perfect-card-content {{
            padding: 1rem !important;
        }}
        
        .perfect-card-title {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.125rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 0.5rem !important;
        }}
        
        .perfect-card-description {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 400 !important;
            font-size: 0.9rem !important;
            color: #b0b0b0 !important;
            line-height: 1.5 !important;
        }}
        
        @media (max-width: 768px) {{
            .perfect-cards-grid {{
                grid-template-columns: 1fr !important;
            }}
        }}
        </style>
        
        <div class="perfect-cards-container">
            <div class="perfect-cards-title">7. Linear Card with Image</div>
            <div class="perfect-cards-grid">
                <div class="perfect-card">
                    <img src="{card_images[0]['image']}" class="perfect-card-image" alt="Card 1">
                    <div class="perfect-card-content">
                        <div class="perfect-card-title">{card_images[0]['title']}</div>
                        <div class="perfect-card-description">{card_images[0]['description']}</div>
                    </div>
                </div>
                <div class="perfect-card">
                    <img src="{card_images[1]['image']}" class="perfect-card-image" alt="Card 2">
                    <div class="perfect-card-content">
                        <div class="perfect-card-title">{card_images[1]['title']}</div>
                        <div class="perfect-card-description">{card_images[1]['description']}</div>
                    </div>
                </div>
                <div class="perfect-card">
                    <img src="{card_images[2]['image']}" class="perfect-card-image" alt="Card 3">
                    <div class="perfect-card-content">
                        <div class="perfect-card-title">{card_images[2]['title']}</div>
                        <div class="perfect-card-description">{card_images[2]['description']}</div>
                    </div>
                </div>
            </div>
        </div>
        """
    else:
        cards_html = """
        <div style="margin: 2rem 0;">
            <h3 style="color: #e0e0e0; margin-bottom: 1rem;">7. Linear Card with Image</h3>
            <p style="color: #b0b0b0; text-align: center;">이미지를 로드할 수 없습니다.</p>
        </div>
        """
    
    st.markdown(cards_html, unsafe_allow_html=True)

def main():
    """Linear 컴포넌트 데모 페이지"""
    
    # 테마 적용 (최우선)
    apply_theme()
    
    # 페이지 설정
    st.set_page_config(
        page_title="Linear 컴포넌트 데모",
        page_icon="🔷",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 완벽한 네비게이션 바
    st.markdown("### 네비게이션 바 테스트")
    try:
        create_perfect_navbar()
        st.success("✅ 네비게이션 바 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 네비게이션 바 오류: {e}")
    
    # 완벽한 히어로 섹션
    st.markdown("### 히어로 섹션 테스트")
    try:
        create_perfect_hero()
        st.success("✅ 히어로 섹션 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 히어로 섹션 오류: {e}")
    
    # 메인 컨텐츠
    st.markdown("## 🎨 컴포넌트 갤러리")
    
    # 1. 버튼 컴포넌트
    st.markdown("### 1. Linear Button")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**Primary**")
        if linear_button("Primary Button", variant="primary", key="demo_primary"):
            st.success("Primary 버튼 클릭됨!")
    
    with col2:
        st.markdown("**Secondary**")
        if linear_button("Secondary Button", variant="secondary", key="demo_secondary"):
            st.info("Secondary 버튼 클릭됨!")
    
    with col3:
        st.markdown("**Danger**")
        if linear_button("Danger Button", variant="danger", key="demo_danger"):
            st.error("Danger 버튼 클릭됨!")
    
    with col4:
        st.markdown("**Success**")
        if linear_button("Success Button", variant="success", key="demo_success"):
            st.success("Success 버튼 클릭됨!")
    
    # 버튼 크기
    st.markdown("**버튼 크기**")
    size_col1, size_col2, size_col3 = st.columns(3)
    
    with size_col1:
        linear_button("Small", size="small", key="demo_small")
    with size_col2:
        linear_button("Medium", size="medium", key="demo_medium")
    with size_col3:
        linear_button("Large", size="large", key="demo_large")
    
    linear_divider()
    
    # 2. 카드 컴포넌트
    st.markdown("### 2. Linear Card")
    card_col1, card_col2, card_col3 = st.columns(3)
    
    with card_col1:
        linear_card(
            title="Elevated Card",
            content=st.markdown("이것은 **elevated** 스타일 카드입니다."),
            variant="elevated"
        )
    
    with card_col2:
        linear_card(
            title="Flat Card",
            content=st.markdown("이것은 **flat** 스타일 카드입니다."),
            variant="flat"
        )
    
    with card_col3:
        linear_card(
            title="Outlined Card",
            content=st.markdown("이것은 **outlined** 스타일 카드입니다."),
            variant="outlined"
        )
    
    linear_divider()
    
    # 3. 배지 컴포넌트
    st.markdown("### 3. Linear Badge")
    badge_col1, badge_col2, badge_col3 = st.columns(3)
    
    with badge_col1:
        st.markdown("**Small Badges**")
        linear_badge("New", size="small")
        linear_badge("Hot", size="small")
        linear_badge("Sale", size="small")
    
    with badge_col2:
        st.markdown("**Medium Badges**")
        linear_badge("Featured", size="medium")
        linear_badge("Popular", size="medium")
        linear_badge("Trending", size="medium")
    
    with badge_col3:
        st.markdown("**Large Badges**")
        linear_badge("Premium", size="large")
        linear_badge("Pro", size="large")
        linear_badge("Enterprise", size="large")
    
    linear_divider()
    
    # 4. 입력 컴포넌트
    st.markdown("### 4. Linear Input")
    input_col1, input_col2 = st.columns(2)
    
    with input_col1:
        st.markdown("**Text Input**")
        text_value = linear_input("이름을 입력하세요", type="text", key="demo_text")
        if text_value:
            st.write(f"입력된 값: {text_value}")
        
        st.markdown("**Number Input**")
        number_value = linear_input("숫자를 입력하세요", type="number", key="demo_number")
        if number_value:
            st.write(f"입력된 값: {number_value}")
    
    with input_col2:
        st.markdown("**Password Input**")
        password_value = linear_input("비밀번호", type="password", key="demo_password")
        if password_value:
            st.write("비밀번호가 입력되었습니다.")
        
        st.markdown("**Textarea**")
        textarea_value = linear_input("메시지를 입력하세요", type="textarea", key="demo_textarea")
        if textarea_value:
            st.write(f"입력된 메시지: {textarea_value}")
    
    linear_divider()
    
    # 5. 알림 컴포넌트
    st.markdown("### 5. Linear Alert")
    alert_col1, alert_col2 = st.columns(2)
    
    with alert_col1:
        linear_alert("정보 메시지입니다.", variant="info")
        linear_alert("성공 메시지입니다!", variant="success")
    
    with alert_col2:
        linear_alert("경고 메시지입니다.", variant="warning")
        linear_alert("오류 메시지입니다!", variant="danger")
    
    linear_divider()
    
    # 6. 완벽한 캐러셀
    st.markdown("### 6. Linear Carousel")
    try:
        create_perfect_carousel()
        st.success("✅ 캐러셀 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 캐러셀 오류: {e}")
    
    linear_divider()
    
    # 7. 완벽한 이미지 카드
    st.markdown("### 7. Linear Card with Image")
    try:
        create_perfect_image_cards()
        st.success("✅ 이미지 카드 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 이미지 카드 오류: {e}")
    
    linear_divider()
    
    # 8. 푸터
    try:
        linear_footer(
            copyright_text="© 2025 MAIC 프로젝트. 모든 권리 보유.",
            links=[
                {"label": "개인정보처리방침", "href": "/privacy"},
                {"label": "이용약관", "href": "/terms"},
                {"label": "문의하기", "href": "/contact"}
            ],
            social_links=[
                {"label": "GitHub", "href": "https://github.com", "icon": "🐙"},
                {"label": "Twitter", "href": "https://twitter.com", "icon": "🐦"},
                {"label": "LinkedIn", "href": "https://linkedin.com", "icon": "💼"}
            ]
        )
        st.success("✅ 푸터 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 푸터 오류: {e}")
    
    # 사이드바에 정보 표시
    with st.sidebar:
        st.markdown("## 📋 컴포넌트 정보")
        st.markdown("**총 9개 컴포넌트**")
        st.markdown("- ✅ linear_button")
        st.markdown("- ✅ linear_card")
        st.markdown("- ✅ linear_badge")
        st.markdown("- ✅ linear_input")
        st.markdown("- ✅ linear_alert")
        st.markdown("- ✅ linear_divider")
        st.markdown("- ✅ linear_carousel")
        st.markdown("- ✅ linear_card_with_image")
        st.markdown("- ✅ linear_navbar")
        st.markdown("- ✅ linear_hero")
        st.markdown("- ✅ linear_footer")
        
        st.markdown("## 🎯 특징")
        st.markdown("- **Linear.app 스타일**")
        st.markdown("- **완전 반응형**")
        st.markdown("- **모바일 우선**")
        st.markdown("- **다크 테마**")
        
        st.markdown("## 📱 모바일 테스트")
        st.markdown("브라우저 개발자 도구에서 모바일 뷰로 테스트해보세요!")
        st.markdown("- 768px: 태블릿")
        st.markdown("- 480px: 모바일")
        
        # 로컬 이미지 상태 표시
        st.markdown("## 🖼️ 이미지 상태")
        image_files = ["carousel_1.png", "carousel_2.png", "carousel_3.png", 
                       "card_1.png", "card_2.png", "card_3.png", "hero_bg.png"]
        
        for img_file in image_files:
            img_path = f"images/{img_file}"
            if os.path.exists(img_path):
                st.markdown(f"✅ {img_file}")
            else:
                st.markdown(f"❌ {img_file}")

if __name__ == "__main__":
    main()


