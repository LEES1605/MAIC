# Linear 컴포넌트 데모 페이지
from __future__ import annotations
import streamlit as st
from .linear_components import (
    linear_button, linear_card, linear_badge, linear_input, 
    linear_alert, linear_divider, linear_carousel, 
    linear_card_with_image, linear_navbar, linear_chip, 
    linear_gradient_button
)
from .linear_layout_components import linear_footer, linear_hero
from .linear_theme import apply_theme
from .background_styles import apply_background_styles

def render_component_demo():
    """Linear 컴포넌트 데모 페이지 렌더링"""
    if st is None:
        return
    
    # 테마 및 배경 적용
    apply_theme()
    apply_background_styles()
    
    # 페이지 제목
    st.title("🎨 Linear 컴포넌트 시스템 데모")
    st.markdown("---")
    
    # 1. 버튼 컴포넌트들
    st.header("🔘 버튼 컴포넌트들")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("기본 버튼")
        if linear_button("Primary", variant="primary", key="demo_btn1"):
            st.success("Primary 버튼 클릭됨!")
        
        if linear_button("Secondary", variant="secondary", key="demo_btn2"):
            st.info("Secondary 버튼 클릭됨!")
        
        if linear_button("Danger", variant="danger", key="demo_btn3"):
            st.error("Danger 버튼 클릭됨!")
    
    with col2:
        st.subheader("그라디언트 버튼")
        if linear_gradient_button("Primary Gradient", gradient="primary", key="demo_grad1"):
            st.success("Primary 그라디언트 버튼 클릭됨!")
        
        if linear_gradient_button("Secondary Gradient", gradient="secondary", key="demo_grad2"):
            st.info("Secondary 그라디언트 버튼 클릭됨!")
        
        if linear_gradient_button("Tertiary Gradient", gradient="tertiary", key="demo_grad3"):
            st.warning("Tertiary 그라디언트 버튼 클릭됨!")
    
    with col3:
        st.subheader("크기별 버튼")
        if linear_button("Small", size="small", key="demo_size1"):
            st.success("Small 버튼 클릭됨!")
        
        if linear_button("Medium", size="medium", key="demo_size2"):
            st.info("Medium 버튼 클릭됨!")
        
        if linear_button("Large", size="large", key="demo_size3"):
            st.warning("Large 버튼 클릭됨!")
    
    linear_divider()
    
    # 2. 칩 컴포넌트
    st.header("🏷️ 칩 컴포넌트")
    
    st.subheader("모드 선택 칩")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if linear_chip("문법", key="demo_chip1", selected=True):
            st.success("문법 칩 선택됨!")
    
    with col2:
        if linear_chip("독해", key="demo_chip2", selected=False):
            st.info("독해 칩 선택됨!")
    
    with col3:
        if linear_chip("작문", key="demo_chip3", selected=False):
            st.warning("작문 칩 선택됨!")
    
    linear_divider()
    
    # 3. 카드 컴포넌트들
    st.header("📋 카드 컴포넌트들")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("기본 카드")
        linear_card(
            title="기본 카드",
            content=st.markdown("이것은 기본 카드입니다."),
            variant="default"
        )
        
        linear_card(
            title="Elevated 카드",
            content=st.markdown("이것은 Elevated 카드입니다."),
            variant="elevated"
        )
    
    with col2:
        st.subheader("이미지 카드")
        linear_card_with_image(
            title="이미지 카드",
            content=st.markdown("이미지가 포함된 카드입니다."),
            image_url="https://via.placeholder.com/300x200/667eea/ffffff?text=Demo+Image"
        )
    
    linear_divider()
    
    # 4. 배지 컴포넌트
    st.header("🏷️ 배지 컴포넌트")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        linear_badge("Primary", variant="primary")
    with col2:
        linear_badge("Secondary", variant="secondary")
    with col3:
        linear_badge("Success", variant="success")
    with col4:
        linear_badge("Warning", variant="warning")
    
    linear_divider()
    
    # 5. 입력 컴포넌트
    st.header("📝 입력 컴포넌트")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("텍스트 입력")
        text_value = linear_input("이름", placeholder="이름을 입력하세요...", key="demo_input1")
        if text_value:
            st.write(f"입력된 값: {text_value}")
    
    with col2:
        st.subheader("숫자 입력")
        number_value = linear_input("나이", placeholder="나이를 입력하세요...", key="demo_input2")
        if number_value:
            st.write(f"입력된 값: {number_value}")
    
    linear_divider()
    
    # 6. 알림 컴포넌트
    st.header("🔔 알림 컴포넌트")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        linear_alert("성공 메시지", variant="success")
    with col2:
        linear_alert("정보 메시지", variant="info")
    with col3:
        linear_alert("경고 메시지", variant="warning")
    with col4:
        linear_alert("오류 메시지", variant="error")
    
    linear_divider()
    
    # 7. 캐러셀 컴포넌트
    st.header("🎠 캐러셀 컴포넌트")
    
    carousel_items = [
        "첫 번째 항목",
        "두 번째 항목", 
        "세 번째 항목",
        "네 번째 항목"
    ]
    
    linear_carousel(carousel_items)
    
    linear_divider()
    
    # 8. 레이아웃 컴포넌트
    st.header("🏗️ 레이아웃 컴포넌트")
    
    st.subheader("히어로 섹션")
    linear_hero(
        title="Linear 컴포넌트 시스템",
        subtitle="모던하고 세련된 UI 컴포넌트들"
    )
    
    st.subheader("네비게이션 바")
    linear_navbar(
        brand_name="Linear Demo",
        menu_items=["홈", "컴포넌트", "문서", "설정"]
    )
    
    # 9. 컴포넌트 정보
    st.header("📊 컴포넌트 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("사용 가능한 컴포넌트")
        components = [
            "linear_button - 버튼",
            "linear_card - 카드",
            "linear_badge - 배지",
            "linear_input - 입력 필드",
            "linear_alert - 알림",
            "linear_divider - 구분선",
            "linear_carousel - 캐러셀",
            "linear_chip - 칩",
            "linear_gradient_button - 그라디언트 버튼"
        ]
        
        for component in components:
            st.write(f"• {component}")
    
    with col2:
        st.subheader("레이아웃 컴포넌트")
        layout_components = [
            "linear_hero - 히어로 섹션",
            "linear_navbar - 네비게이션 바",
            "linear_footer - 푸터"
        ]
        
        for component in layout_components:
            st.write(f"• {component}")
    
    # 푸터
    linear_footer(copyright_text="© 2024 Linear 컴포넌트 시스템 데모")

