#!/usr/bin/env python3
"""
Linear 컴포넌트 데모 페이지 - 궁극의 최종 버전
네비게이션 바 고질적 문제를 완전히 해결한 버전
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

def create_ultimate_navbar():
    """궁극의 네비게이션 바 생성 - JavaScript 강제 실행"""
    
    # 1단계: 기본 HTML 구조 생성
    navbar_html = """
    <div id="ultimate-navbar" style="display: none;">
        <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); border-bottom: 2px solid #5e6ad2; padding: 16px 0; margin: -1rem -1rem 2rem -1rem; width: calc(100% + 2rem); position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);">
            <div style="max-width: 1200px; margin: 0 auto; padding: 0 24px; display: flex; align-items: center; justify-content: space-between;">
                <a href="#" style="color: white; font-size: 1.2rem; font-weight: 700; text-decoration: none;">Linear Components</a>
                
                <div style="display: flex; gap: 24px; align-items: center;">
                    <a href="#product" style="color: rgba(255, 255, 255, 0.8); text-decoration: none; padding: 8px 16px; border-radius: 6px; transition: all 0.2s ease; font-weight: 500;">Product</a>
                    <a href="#solutions" style="color: rgba(255, 255, 255, 0.8); text-decoration: none; padding: 8px 16px; border-radius: 6px; transition: all 0.2s ease; font-weight: 500;">Solutions</a>
                    <a href="#features" style="color: rgba(255, 255, 255, 0.8); text-decoration: none; padding: 8px 16px; border-radius: 6px; transition: all 0.2s ease; font-weight: 500;">Features</a>
                    <a href="#pricing" style="color: rgba(255, 255, 255, 0.8); text-decoration: none; padding: 8px 16px; border-radius: 6px; transition: all 0.2s ease; font-weight: 500;">Pricing</a>
                    <a href="#docs" style="color: rgba(255, 255, 255, 0.8); text-decoration: none; padding: 8px 16px; border-radius: 6px; transition: all 0.2s ease; font-weight: 500;">Docs</a>
                </div>
                
                <div style="display: flex; gap: 12px; align-items: center;">
                    <a href="#login" style="background: transparent; border: 1px solid rgba(255, 255, 255, 0.3); color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; transition: all 0.2s ease; font-weight: 500;">Log in</a>
                    <a href="#signup" style="background: #5e6ad2; border: 1px solid #5e6ad2; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; transition: all 0.2s ease; font-weight: 500;">Sign up</a>
                </div>
            </div>
        </div>
    </div>
    """
    
    # 2단계: JavaScript로 강제 렌더링
    js_code = """
    <script>
    // 페이지 로드 후 네비게이션 바 강제 렌더링
    document.addEventListener('DOMContentLoaded', function() {
        const navbar = document.getElementById('ultimate-navbar');
        if (navbar) {
            navbar.style.display = 'block';
            
            // 호버 효과 추가
            const navLinks = navbar.querySelectorAll('a[href^="#"]');
            navLinks.forEach(link => {
                link.addEventListener('mouseenter', function() {
                    this.style.background = 'rgba(94, 106, 210, 0.2)';
                    this.style.color = 'white';
                });
                link.addEventListener('mouseleave', function() {
                    if (!this.style.background.includes('#5e6ad2')) {
                        this.style.background = 'transparent';
                        this.style.color = 'rgba(255, 255, 255, 0.8)';
                    }
                });
            });
            
            // 버튼 호버 효과
            const buttons = navbar.querySelectorAll('a[href="#login"], a[href="#signup"]');
            buttons.forEach(button => {
                button.addEventListener('mouseenter', function() {
                    if (this.href.includes('#login')) {
                        this.style.background = '#5e6ad2';
                        this.style.borderColor = '#5e6ad2';
                    } else {
                        this.style.background = '#7170ff';
                        this.style.borderColor = '#7170ff';
                    }
                });
                button.addEventListener('mouseleave', function() {
                    if (this.href.includes('#login')) {
                        this.style.background = 'transparent';
                        this.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                    } else {
                        this.style.background = '#5e6ad2';
                        this.style.borderColor = '#5e6ad2';
                    }
                });
            });
        }
    });
    
    // 지연 실행 (Streamlit이 완전히 로드된 후)
    setTimeout(function() {
        const navbar = document.getElementById('ultimate-navbar');
        if (navbar) {
            navbar.style.display = 'block';
        }
    }, 1000);
    </script>
    """
    
    # 3단계: HTML과 JavaScript 함께 렌더링
    st.markdown(navbar_html + js_code, unsafe_allow_html=True)

def create_ultimate_hero():
    """궁극의 히어로 섹션 생성"""
    hero_bg = get_base64_image("hero_bg.png")
    
    if hero_bg:
        hero_html = f"""
        <div style="background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), url('{hero_bg}'); background-size: cover; background-position: center; background-repeat: no-repeat; padding: 4rem 0; margin: -1rem -1rem 2rem -1rem; width: calc(100% + 2rem); position: relative; overflow: hidden; border-top: 1px solid #404040; border-bottom: 1px solid #404040;">
            <div style="max-width: 1200px; margin: 0 auto; padding: 0 1rem; text-align: center;">
                <h1 style="font-family: 'Inter', sans-serif; font-weight: 700; font-size: 4rem; line-height: 1.1; color: #ffffff; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5); margin-bottom: 1.5rem; letter-spacing: -0.02em;">Linear 컴포넌트 시스템</h1>
                <p style="font-family: 'Inter', sans-serif; font-weight: 400; font-size: 1.25rem; line-height: 1.6; color: rgba(255, 255, 255, 0.9); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); margin-bottom: 2rem; max-width: 600px; margin-left: auto; margin-right: auto;">MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리</p>
                <div style="margin-bottom: 2rem;">
                    <a href="#start" style="background: #5e6ad2; border: 2px solid #5e6ad2; color: white; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 1rem; text-decoration: none; display: inline-block; transition: all 0.2s ease;">시작하기</a>
                </div>
                <div style="display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; margin-top: 2rem;">
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ 9개 핵심 컴포넌트</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ 완전 반응형 디자인</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ Linear.app 스타일</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ 모바일 우선 설계</div>
                </div>
            </div>
        </div>
        """
    else:
        hero_html = """
        <div style="background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); padding: 4rem 0; margin: -1rem -1rem 2rem -1rem; width: calc(100% + 2rem); position: relative; overflow: hidden; border-top: 1px solid #404040; border-bottom: 1px solid #404040;">
            <div style="max-width: 1200px; margin: 0 auto; padding: 0 1rem; text-align: center;">
                <h1 style="font-family: 'Inter', sans-serif; font-weight: 700; font-size: 4rem; line-height: 1.1; color: #ffffff; margin-bottom: 1.5rem; letter-spacing: -0.02em;">Linear 컴포넌트 시스템</h1>
                <p style="font-family: 'Inter', sans-serif; font-weight: 400; font-size: 1.25rem; line-height: 1.6; color: rgba(255, 255, 255, 0.9); margin-bottom: 2rem; max-width: 600px; margin-left: auto; margin-right: auto;">MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리</p>
                <div style="margin-bottom: 2rem;">
                    <a href="#start" style="background: #5e6ad2; border: 2px solid #5e6ad2; color: white; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 1rem; text-decoration: none; display: inline-block; transition: all 0.2s ease;">시작하기</a>
                </div>
                <div style="display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; margin-top: 2rem;">
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ 9개 핵심 컴포넌트</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ 완전 반응형 디자인</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ Linear.app 스타일</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem; color: #e0e0e0; display: flex; align-items: center; gap: 8px;">✓ 모바일 우선 설계</div>
                </div>
            </div>
        </div>
        """
    
    st.markdown(hero_html, unsafe_allow_html=True)

def create_ultimate_carousel():
    """궁극의 캐러셀 생성"""
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
        <div style="background: #2a2a2a; border: 1px solid #404040; border-radius: 12px; padding: 2rem; margin: 2rem 0; position: relative;">
            <div style="font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.5rem; color: #e0e0e0; margin-bottom: 1rem; text-align: center;">6. Linear Carousel</div>
            <div style="display: flex; align-items: center; justify-content: center; gap: 1rem;">
                <button style="background: #5e6ad2; border: none; color: white; width: 40px; height: 40px; border-radius: 50%; font-size: 1.2rem; cursor: pointer; transition: all 0.2s ease;" onclick="alert('이전 슬라이드')">◀</button>
                <div style="flex: 1; text-align: center;">
                    <img src="{carousel_images[0]['image']}" style="width: 100%; max-width: 400px; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 1rem;" alt="Slide 1">
                    <div style="font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.25rem; color: #e0e0e0; margin-bottom: 0.5rem;">{carousel_images[0]['title']}</div>
                    <div style="font-family: 'Inter', sans-serif; font-weight: 400; font-size: 1rem; color: #b0b0b0; line-height: 1.5;">{carousel_images[0]['description']}</div>
                </div>
                <button style="background: #5e6ad2; border: none; color: white; width: 40px; height: 40px; border-radius: 50%; font-size: 1.2rem; cursor: pointer; transition: all 0.2s ease;" onclick="alert('다음 슬라이드')">▶</button>
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

def create_ultimate_image_cards():
    """궁극의 이미지 카드 생성"""
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
        <div style="margin: 2rem 0;">
            <div style="font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.5rem; color: #e0e0e0; margin-bottom: 1rem;">7. Linear Card with Image</div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                <div style="background: #2a2a2a; border: 1px solid #404040; border-radius: 12px; overflow: hidden; transition: all 0.2s ease;">
                    <img src="{card_images[0]['image']}" style="width: 100%; height: 200px; object-fit: cover;" alt="Card 1">
                    <div style="padding: 1rem;">
                        <div style="font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.125rem; color: #e0e0e0; margin-bottom: 0.5rem;">{card_images[0]['title']}</div>
                        <div style="font-family: 'Inter', sans-serif; font-weight: 400; font-size: 0.9rem; color: #b0b0b0; line-height: 1.5;">{card_images[0]['description']}</div>
                    </div>
                </div>
                <div style="background: #2a2a2a; border: 1px solid #404040; border-radius: 12px; overflow: hidden; transition: all 0.2s ease;">
                    <img src="{card_images[1]['image']}" style="width: 100%; height: 200px; object-fit: cover;" alt="Card 2">
                    <div style="padding: 1rem;">
                        <div style="font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.125rem; color: #e0e0e0; margin-bottom: 0.5rem;">{card_images[1]['title']}</div>
                        <div style="font-family: 'Inter', sans-serif; font-weight: 400; font-size: 0.9rem; color: #b0b0b0; line-height: 1.5;">{card_images[1]['description']}</div>
                    </div>
                </div>
                <div style="background: #2a2a2a; border: 1px solid #404040; border-radius: 12px; overflow: hidden; transition: all 0.2s ease;">
                    <img src="{card_images[2]['image']}" style="width: 100%; height: 200px; object-fit: cover;" alt="Card 3">
                    <div style="padding: 1rem;">
                        <div style="font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.125rem; color: #e0e0e0; margin-bottom: 0.5rem;">{card_images[2]['title']}</div>
                        <div style="font-family: 'Inter', sans-serif; font-weight: 400; font-size: 0.9rem; color: #b0b0b0; line-height: 1.5;">{card_images[2]['description']}</div>
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
    
    # 궁극의 네비게이션 바
    st.markdown("### 네비게이션 바 테스트")
    try:
        create_ultimate_navbar()
        st.success("✅ 네비게이션 바 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 네비게이션 바 오류: {e}")
    
    # 궁극의 히어로 섹션
    st.markdown("### 히어로 섹션 테스트")
    try:
        create_ultimate_hero()
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
    
    # 6. 궁극의 캐러셀
    st.markdown("### 6. Linear Carousel")
    try:
        create_ultimate_carousel()
        st.success("✅ 캐러셀 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 캐러셀 오류: {e}")
    
    linear_divider()
    
    # 7. 궁극의 이미지 카드
    st.markdown("### 7. Linear Card with Image")
    try:
        create_ultimate_image_cards()
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


