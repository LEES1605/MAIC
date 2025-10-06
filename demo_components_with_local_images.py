#!/usr/bin/env python3
"""
Linear 컴포넌트 데모 페이지 - 로컬 이미지 사용 버전
모든 Linear 컴포넌트들을 브라우저에서 확인할 수 있는 데모 페이지
"""

import streamlit as st
import sys
from pathlib import Path
import os

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

def get_image_path(filename):
    """로컬 이미지 경로 반환"""
    return f"images/{filename}"

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
    
    # 네비게이션 바 - 강제로 렌더링
    st.markdown("### 네비게이션 바 테스트")
    try:
        linear_navbar(
            brand_name="Linear Components",
            nav_items=[
                {"label": "Product", "href": "#product"},
                {"label": "Solutions", "href": "#solutions"},
                {"label": "Features", "href": "#features"},
                {"label": "Pricing", "href": "#pricing"},
                {"label": "Docs", "href": "#docs"}
            ]
        )
        st.success("✅ 네비게이션 바 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 네비게이션 바 오류: {e}")
    
    # 히어로 섹션 - 로컬 배경 이미지 사용
    st.markdown("### 히어로 섹션 테스트")
    try:
        hero_bg_path = get_image_path("hero_bg.png")
        if os.path.exists(hero_bg_path):
            linear_hero(
                title="Linear 컴포넌트 시스템",
                subtitle="MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리",
                background_image=hero_bg_path,
                cta_button={
                    "text": "시작하기",
                    "variant": "primary",
                    "callback": lambda: st.success("시작하기 클릭됨!")
                },
                features=[
                    "9개 핵심 컴포넌트",
                    "완전 반응형 디자인", 
                    "Linear.app 스타일",
                    "모바일 우선 설계"
                ],
                variant="centered"
            )
            st.success("✅ 히어로 섹션 렌더링 성공!")
        else:
            st.warning("⚠️ 히어로 배경 이미지가 없습니다. 기본 히어로 섹션을 표시합니다.")
            linear_hero(
                title="Linear 컴포넌트 시스템",
                subtitle="MAIC 프로젝트를 위한 완전한 Linear 스타일 컴포넌트 라이브러리",
                cta_button={
                    "text": "시작하기",
                    "variant": "primary",
                    "callback": lambda: st.success("시작하기 클릭됨!")
                },
                features=[
                    "9개 핵심 컴포넌트",
                    "완전 반응형 디자인", 
                    "Linear.app 스타일",
                    "모바일 우선 설계"
                ],
                variant="centered"
            )
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
    
    # 6. 캐러셀 컴포넌트 - 로컬 이미지 사용
    st.markdown("### 6. Linear Carousel")
    
    # 로컬 이미지 데이터
    carousel_items = []
    for i in range(1, 4):
        img_path = get_image_path(f"carousel_{i}.png")
        if os.path.exists(img_path):
            carousel_items.append({
                "image": img_path,
                "title": f"첫 번째 슬라이드" if i == 1 else f"{i}번째 슬라이드",
                "description": f"이것은 {i}번째 캐러셀 슬라이드입니다."
            })
        else:
            # 이미지가 없으면 기본 색상 사용
            colors = ["#5e6ad2", "#7170ff", "#828fff"]
            carousel_items.append({
                "image": f"https://via.placeholder.com/400x200/{colors[i-1][1:]}/ffffff?text=Slide+{i}",
                "title": f"{i}번째 슬라이드",
                "description": f"이것은 {i}번째 캐러셀 슬라이드입니다."
            })
    
    try:
        linear_carousel(
            items=carousel_items,
            key="demo_carousel"
        )
        st.success("✅ 캐러셀 렌더링 성공!")
    except Exception as e:
        st.error(f"❌ 캐러셀 오류: {e}")
    
    linear_divider()
    
    # 7. 이미지 카드 - 로컬 이미지 사용
    st.markdown("### 7. Linear Card with Image")
    
    image_card_col1, image_card_col2, image_card_col3 = st.columns(3)
    
    # 로컬 이미지 사용
    card_data = []
    for i in range(1, 4):
        img_path = get_image_path(f"card_{i}.png")
        if os.path.exists(img_path):
            card_data.append({
                "title": f"첫 번째 이미지" if i == 1 else f"{i}번째 이미지",
                "content": f"이것은 {i}번째 이미지 카드입니다.",
                "image_url": img_path,
                "image_alt": f"{i}번째 이미지"
            })
        else:
            # 이미지가 없으면 기본 색상 사용
            colors = ["#5e6ad2", "#7170ff", "#828fff"]
            card_data.append({
                "title": f"{i}번째 이미지",
                "content": f"이것은 {i}번째 이미지 카드입니다.",
                "image_url": f"https://via.placeholder.com/300x200/{colors[i-1][1:]}/ffffff?text=Image+{i}",
                "image_alt": f"{i}번째 이미지"
            })
    
    try:
        with image_card_col1:
            linear_card_with_image(**card_data[0])
        
        with image_card_col2:
            linear_card_with_image(**card_data[1])
        
        with image_card_col3:
            linear_card_with_image(**card_data[2])
        
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
            img_path = get_image_path(img_file)
            if os.path.exists(img_path):
                st.markdown(f"✅ {img_file}")
            else:
                st.markdown(f"❌ {img_file}")

if __name__ == "__main__":
    main()


