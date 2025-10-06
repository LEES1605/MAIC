#!/usr/bin/env python3
"""
Linear 컴포넌트 데모 페이지 - Streamlit 내장 컴포넌트 사용
네비게이션 바 문제를 Streamlit 내장 컴포넌트로 완전 해결
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

def create_streamlit_native_navbar():
    """Streamlit 내장 컴포넌트로 네비게이션 바 생성"""
    
    # 네비게이션 바 CSS
    navbar_css = """
    <style>
    .streamlit-navbar {
        background: rgba(20, 20, 25, 0.95) !important;
        backdrop-filter: blur(20px) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 12px 0 !important;
        margin: -1rem -1rem 2rem -1rem !important;
        width: calc(100% + 2rem) !important;
        position: sticky !important;
        top: 0 !important;
        z-index: 1000 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
    }
    .streamlit-navbar .stButton > button {
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        color: rgba(255, 255, 255, 0.9) !important;
        padding: 8px 16px !important;
        border-radius: 6px !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        white-space: nowrap !important;
    }
    .streamlit-navbar .stButton > button:hover {
        background: rgba(94, 106, 210, 0.2) !important;
        color: white !important;
    }
    .streamlit-navbar .stButton > button:focus {
        box-shadow: none !important;
    }
    .streamlit-navbar .navbar-brand {
        color: white !important;
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        text-decoration: none !important;
    }
    .streamlit-navbar .navbar-menu {
        display: flex !important;
        align-items: center !important;
        gap: 32px !important;
        flex: 1 !important;
        justify-content: center !important;
    }
    .streamlit-navbar .navbar-buttons {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
    }
    .streamlit-navbar .navbar-buttons .stButton > button.primary {
        background: #5e6ad2 !important;
        border: 1px solid #5e6ad2 !important;
        color: white !important;
    }
    .streamlit-navbar .navbar-buttons .stButton > button.primary:hover {
        background: #7170ff !important;
        border-color: #7170ff !important;
    }
    </style>
    """
    
    st.markdown(navbar_css, unsafe_allow_html=True)
    
    # 네비게이션 바 컨테이너
    with st.container():
        st.markdown('<div class="streamlit-navbar">', unsafe_allow_html=True)
        
        # 네비게이션 바 내용
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            st.markdown('<div class="navbar-brand">L Linear Components</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="navbar-menu">', unsafe_allow_html=True)
            menu_col1, menu_col2, menu_col3, menu_col4, menu_col5 = st.columns(5)
            
            with menu_col1:
                if st.button("Product", key="nav_product"):
                    st.info("Product 클릭됨!")
            
            with menu_col2:
                if st.button("Solutions", key="nav_solutions"):
                    st.info("Solutions 클릭됨!")
            
            with menu_col3:
                if st.button("Features", key="nav_features"):
                    st.info("Features 클릭됨!")
            
            with menu_col4:
                if st.button("Pricing", key="nav_pricing"):
                    st.info("Pricing 클릭됨!")
            
            with menu_col5:
                if st.button("Docs", key="nav_docs"):
                    st.info("Docs 클릭됨!")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="navbar-buttons">', unsafe_allow_html=True)
            button_col1, button_col2 = st.columns(2)
            
            with button_col1:
                if st.button("Log in", key="nav_login"):
                    st.info("Log in 클릭됨!")
            
            with button_col2:
                if st.button("Sign up", key="nav_signup", type="primary"):
                    st.success("Sign up 클릭됨!")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def create_streamlit_native_hero():
    """Streamlit 내장 컴포넌트로 히어로 섹션 생성"""
    hero_bg = get_base64_image("hero_bg.png")
    
    if hero_bg:
        hero_css = f"""
        <style>
        .streamlit-hero {{
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
        .streamlit-hero .hero-content {{
            max-width: 1200px !important;
            margin: 0 auto !important;
            padding: 0 1rem !important;
            text-align: center !important;
        }}
        .streamlit-hero h1 {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 700 !important;
            font-size: 4rem !important;
            line-height: 1.1 !important;
            color: #ffffff !important;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5) !important;
            margin-bottom: 1.5rem !important;
            letter-spacing: -0.02em !important;
        }}
        .streamlit-hero p {{
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
        .streamlit-hero .hero-button {{
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
        .streamlit-hero .hero-features {{
            display: flex !important;
            gap: 24px !important;
            flex-wrap: wrap !important;
            justify-content: center !important;
            margin-top: 2rem !important;
        }}
        .streamlit-hero .hero-feature {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 500 !important;
            font-size: 1rem !important;
            color: #e0e0e0 !important;
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
        }}
        </style>
        """
    else:
        hero_css = """
        <style>
        .streamlit-hero {
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%) !important;
            padding: 4rem 0 !important;
            margin: -1rem -1rem 2rem -1rem !important;
            width: calc(100% + 2rem) !important;
            position: relative !important;
            overflow: hidden !important;
            border-top: 1px solid #404040 !important;
            border-bottom: 1px solid #404040 !important;
        }
        .streamlit-hero .hero-content {
            max-width: 1200px !important;
            margin: 0 auto !important;
            padding: 0 1rem !important;
            text-align: center !important;
        }
        .streamlit-hero h1 {
            font-family: 'Inter', sans-serif !important;
            font-weight: 700 !important;
            font-size: 4rem !important;
            line-height: 1.1 !important;
            color: #ffffff !important;
            margin-bottom: 1.5rem !important;
            letter-spacing: -0.02em !important;
        }
        .streamlit-hero p {
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
        .streamlit-hero .hero-button {
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
        .streamlit-hero .hero-features {
            display: flex !important;
            gap: 24px !important;
            flex-wrap: wrap !important;
            justify-content: center !important;
            margin-top: 2rem !important;
        }
        .streamlit-hero .hero-feature {
            font-family: 'Inter', sans-serif !important;
            font-weight: 500 !important;
            font-size: 1rem !important;
            color: #e0e0e0 !important;
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
        }
        </style>
        """
    
    st.markdown(hero_css, unsafe_allow_html=True)
    
    # 히어로 섹션 컨테이너
    with st.container():
        st.markdown('<div class="streamlit-hero">', unsafe_allow_html=True)
        st.markdown('<div class="hero-content">', unsafe_allow_html=True)
        
        # 제목
        st.markdown('<h1>Linear 컴포넌트 시스템</h1>', unsafe_allow_html=True)
        
        # 부제목
        st.markdown('<p>MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리</p>', unsafe_allow_html=True)
        
        # 버튼
        if st.button("시작하기", key="hero_start", type="primary"):
            st.success("시작하기 클릭됨!")
        
        # 특징 목록
        st.markdown('<div class="hero-features">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="hero-feature">✓ 9개 핵심 컴포넌트</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="hero-feature">✓ 완전 반응형 디자인</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="hero-feature">✓ Linear.app 스타일</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="hero-feature">✓ 모바일 우선 설계</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

def create_streamlit_native_carousel():
    """Streamlit 내장 컴포넌트로 캐러셀 생성"""
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
        carousel_css = f"""
        <style>
        .streamlit-carousel {{
            background: #2a2a2a !important;
            border: 1px solid #404040 !important;
            border-radius: 12px !important;
            padding: 2rem !important;
            margin: 2rem 0 !important;
            position: relative !important;
        }}
        .streamlit-carousel h3 {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.5rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 1rem !important;
            text-align: center !important;
        }}
        .streamlit-carousel .carousel-content {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 1rem !important;
        }}
        .streamlit-carousel .carousel-image {{
            flex: 1 !important;
            text-align: center !important;
        }}
        .streamlit-carousel .carousel-image img {{
            width: 100% !important;
            max-width: 400px !important;
            height: 200px !important;
            object-fit: cover !important;
            border-radius: 8px !important;
            margin-bottom: 1rem !important;
        }}
        .streamlit-carousel .carousel-title {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.25rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 0.5rem !important;
        }}
        .streamlit-carousel .carousel-description {{
            font-family: 'Inter', sans-serif !important;
            font-weight: 400 !important;
            font-size: 1rem !important;
            color: #b0b0b0 !important;
            line-height: 1.5 !important;
        }}
        .streamlit-carousel .carousel-nav {{
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
        .streamlit-carousel .carousel-nav:hover {{
            background: #7170ff !important;
        }}
        </style>
        """
        
        st.markdown(carousel_css, unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="streamlit-carousel">', unsafe_allow_html=True)
            st.markdown('<h3>6. Linear Carousel</h3>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("◀", key="carousel_prev"):
                    st.info("이전 슬라이드")
            
            with col2:
                st.markdown('<div class="carousel-content">', unsafe_allow_html=True)
                st.markdown('<div class="carousel-image">', unsafe_allow_html=True)
                st.image(carousel_images[0]['image'], width=400)
                st.markdown(f'<div class="carousel-title">{carousel_images[0]["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="carousel-description">{carousel_images[0]["description"]}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                if st.button("▶", key="carousel_next"):
                    st.info("다음 슬라이드")
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown("### 6. Linear Carousel")
        st.info("이미지를 로드할 수 없습니다.")

def create_streamlit_native_image_cards():
    """Streamlit 내장 컴포넌트로 이미지 카드 생성"""
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
        cards_css = """
        <style>
        .streamlit-image-cards {
            margin: 2rem 0 !important;
        }
        .streamlit-image-cards h3 {
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.5rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 1rem !important;
        }
        .streamlit-image-cards .cards-grid {
            display: grid !important;
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 1rem !important;
        }
        .streamlit-image-cards .card {
            background: #2a2a2a !important;
            border: 1px solid #404040 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
            transition: all 0.2s ease !important;
        }
        .streamlit-image-cards .card img {
            width: 100% !important;
            height: 200px !important;
            object-fit: cover !important;
        }
        .streamlit-image-cards .card-content {
            padding: 1rem !important;
        }
        .streamlit-image-cards .card-title {
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.125rem !important;
            color: #e0e0e0 !important;
            margin-bottom: 0.5rem !important;
        }
        .streamlit-image-cards .card-description {
            font-family: 'Inter', sans-serif !important;
            font-weight: 400 !important;
            font-size: 0.9rem !important;
            color: #b0b0b0 !important;
            line-height: 1.5 !important;
        }
        </style>
        """
        
        st.markdown(cards_css, unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="streamlit-image-cards">', unsafe_allow_html=True)
            st.markdown('<h3>7. Linear Card with Image</h3>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.image(card_images[0]['image'], width=300)
                st.markdown('<div class="card-content">', unsafe_allow_html=True)
                st.markdown(f'<div class="card-title">{card_images[0]["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="card-description">{card_images[0]["description"]}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.image(card_images[1]['image'], width=300)
                st.markdown('<div class="card-content">', unsafe_allow_html=True)
                st.markdown(f'<div class="card-title">{card_images[1]["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="card-description">{card_images[1]["description"]}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.image(card_images[2]['image'], width=300)
                st.markdown('<div class="card-content">', unsafe_allow_html=True)
                st.markdown(f'<div class="card-title">{card_images[2]["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="card-description">{card_images[2]["description"]}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown("### 7. Linear Card with Image")
        st.info("이미지를 로드할 수 없습니다.")

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
    
    # Streamlit 내장 컴포넌트로 네비게이션 바
    st.markdown("### 네비게이션 바 테스트")
    try:
        create_streamlit_native_navbar()
        st.success("✅ 네비게이션 바 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 네비게이션 바 오류: {e}")
    
    # Streamlit 내장 컴포넌트로 히어로 섹션
    st.markdown("### 히어로 섹션 테스트")
    try:
        create_streamlit_native_hero()
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
    
    # 6. Streamlit 내장 컴포넌트로 캐러셀
    st.markdown("### 6. Linear Carousel")
    try:
        create_streamlit_native_carousel()
        st.success("✅ 캐러셀 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 캐러셀 오류: {e}")
    
    linear_divider()
    
    # 7. Streamlit 내장 컴포넌트로 이미지 카드
    st.markdown("### 7. Linear Card with Image")
    try:
        create_streamlit_native_image_cards()
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


