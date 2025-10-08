# Linear 컴포넌트 데모 페이지 (수정된 버전)
from __future__ import annotations
import streamlit as st
from .linear_components_fixed import (
    linear_button, linear_card, linear_badge, linear_input, 
    linear_alert, linear_divider, linear_carousel, 
    linear_card_with_image, linear_navbar, linear_chip, 
    linear_gradient_button, linear_floating_card, 
    linear_floating_button, linear_floating_chip, 
    linear_circular_progress, linear_modern_background,
    linear_modern_input_pill
)
from .linear_layout_components_fixed import linear_footer, linear_hero
from .linear_theme import apply_theme
from .background_styles import apply_background_styles

def render_component_demo():
    """Linear 컴포넌트 데모 페이지 렌더링"""
    if st is None:
        return
    
    # 테마 및 배경 적용
    apply_theme()
    linear_modern_background()
    
    # IFrame 컴포넌트 사용 (다른 방법)
    st.markdown("## 🎨 Neumorphism 컴포넌트 시스템 (IFrame)")
    
    # 방법 1: 직접 HTML 삽입
    with open("static/neumorphism_components.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    st.components.v1.html(html_content, height=800, scrolling=True)
    
    st.markdown("---")
    st.markdown("## 📱 기존 Streamlit 컴포넌트들")
    
    # 더 강력한 배경 적용
    st.markdown("""
    <style>
    /* 최강 배경 적용 */
    html, body, div[data-testid="stApp"], .stApp, .stApp > div, .main, .block-container {
        background: 
            radial-gradient(1200px 600px at 10% -10%, #232b57, transparent 60%),
            radial-gradient(800px 480px at 90% 20%, #1e254f, transparent 55%),
            linear-gradient(160deg, #0d1028, #0a0d24 70%) !important;
        color: #e6ebff !important;
        font-family: 'Poppins', sans-serif !important;
        min-height: 100vh !important;
    }
    
    /* 모든 컨테이너 투명화 */
    .stApp > div, .main, .block-container {
        background: transparent !important;
    }
    
    /* 버튼 스타일 */
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #7b61ff, #55c1ff) !important;
        color: white !important;
        border: none !important;
        border-radius: 28px !important;
        padding: 12px 24px !important;
        box-shadow: 0 8px 32px rgba(123, 97, 255, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 12px 40px rgba(123, 97, 255, 0.5) !important;
    }
    </style>
    
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    
    <script>
    // JavaScript로 강제 적용
    function forceBackground() {
        document.body.style.background = 'linear-gradient(160deg, #0d1028, #0a0d24)';
        document.documentElement.style.background = 'linear-gradient(160deg, #0d1028, #0a0d24)';
        
        const stApp = document.querySelector('[data-testid="stApp"]');
        if (stApp) {
            stApp.style.background = 'linear-gradient(160deg, #0d1028, #0a0d24)';
            stApp.style.color = '#e6ebff';
        }
        
        console.log('배경 강제 적용 완료!');
    }
    
    forceBackground();
    setInterval(forceBackground, 500);
    </script>
    """, unsafe_allow_html=True)
    
    # 아까 성공했던 JavaScript 방법 적용
    st.markdown("""
    <script>
    // 아까 Console에서 성공했던 방법
    function applySuccessfulStyles() {
        // Streamlit 앱 요소 찾기
        const stApp = document.querySelector('[data-testid="stApp"]');
        if (stApp) {
            // 배경 강제 적용
            stApp.style.background = 'linear-gradient(160deg, #0d1028, #0a0d24)';
            stApp.style.color = '#e6ebff';
            
            // 모든 버튼에 스타일 적용
            const buttons = stApp.querySelectorAll('button');
            buttons.forEach(btn => {
                btn.style.background = 'linear-gradient(135deg, #7b61ff, #55c1ff)';
                btn.style.color = 'white';
                btn.style.border = 'none';
                btn.style.borderRadius = '28px';
                btn.style.padding = '12px 24px';
                btn.style.boxShadow = '0 8px 32px rgba(123, 97, 255, 0.4)';
                btn.style.transition = 'all 0.3s ease';
                
                // 버튼 내부 모든 요소들 제거
                const innerElements = btn.querySelectorAll('*');
                innerElements.forEach(element => {
                    element.style.background = 'transparent';
                    element.style.backgroundColor = 'transparent';
                    element.style.border = 'none';
                    element.style.boxShadow = 'none';
                    element.style.borderRadius = '0';
                    element.style.margin = '0';
                    element.style.padding = '0';
                });
            });
            
            // 모든 입력 필드에 스타일 적용
            const inputs = stApp.querySelectorAll('input');
            inputs.forEach(input => {
                input.style.background = 'linear-gradient(145deg, #151a3c, #0f1331)';
                input.style.color = '#e6ebff';
                input.style.border = '1px solid rgba(255, 255, 255, 0.1)';
                input.style.borderRadius = '28px';
                input.style.padding = '12px 16px';
            });
            
            // 모든 컨테이너에 스타일 적용
            const containers = stApp.querySelectorAll('.stContainer, [data-testid="stContainer"]');
            containers.forEach(container => {
                container.style.background = 'linear-gradient(145deg, #171c41, #0f1332)';
                container.style.border = '1px solid rgba(255, 255, 255, 0.1)';
                container.style.borderRadius = '24px';
                container.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.4)';
                container.style.padding = '20px';
                container.style.margin = '16px 0';
            });
            
            console.log('Streamlit 요소에 직접 스타일 적용 완료!');
        } else {
            console.log('Streamlit 앱 요소를 찾을 수 없습니다.');
        }
    }
    
    // 즉시 실행
    applySuccessfulStyles();
    
    // 페이지 로드 완료 후에도 실행
    window.addEventListener('load', applySuccessfulStyles);
    
    // DOM 변경 감지하여 새로 추가되는 요소에도 적용
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                setTimeout(applySuccessfulStyles, 100);
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // 주기적으로 실행
    setInterval(applySuccessfulStyles, 1000);
    </script>
    """, unsafe_allow_html=True)
    
    # 네비게이션 바
    nav_items = [
        {"label": "홈", "href": "/", "active": True},
        {"label": "컴포넌트", "href": "/components", "active": False},
        {"label": "문서", "href": "/docs", "active": False},
        {"label": "예제", "href": "/examples", "active": False}
    ]
    
    linear_navbar(
        brand_name="Linear Components",
        nav_items=nav_items,
        key="demo_navbar"
    )
    
    # 페이지 제목
    st.title("🎨 Linear 컴포넌트 시스템 데모")
    st.markdown("---")
    
    # 1. 새로운 떠있는 컴포넌트들
    st.header("✨ 새로운 떠있는 컴포넌트들")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🎈 떠있는 버튼")
        linear_floating_button("Get started", variant="primary", key="float_btn_1")
        linear_floating_button("Learn more", variant="secondary", key="float_btn_2")
        linear_floating_button("Gradient", variant="gradient", key="float_btn_3")
    
    with col2:
        st.subheader("🏷️ 떠있는 칩")
        linear_floating_chip("문법", variant="primary", key="float_chip_1")
        linear_floating_chip("독해", variant="secondary", key="float_chip_2")
        linear_floating_chip("작문", variant="accent", key="float_chip_3")
    
    with col3:
        st.subheader("⭕ 원형 진행바")
        linear_circular_progress(0.75, label="진행률", key="progress_1")
        linear_circular_progress(0.50, label="완료", key="progress_2")
        linear_circular_progress(0.25, label="대기", key="progress_3")
    
    st.markdown("---")
    
    # 2. 알림 컴포넌트
    st.header("🔔 알림 컴포넌트")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        linear_alert("성공 메시지", variant="success", key="alert_success")
    
    with col2:
        linear_alert("정보 메시지", variant="info", key="alert_info")
    
    with col3:
        linear_alert("경고 메시지", variant="warning", key="alert_warning")
    
    with col4:
        linear_alert("오류 메시지", variant="error", key="alert_error")
    
    st.markdown("---")
    
    # 3. 캐러셀 컴포넌트
    st.header("🎠 캐러셀 컴포넌트")
    
    # 캐러셀 플레이스홀더
    st.markdown("**캐러셀 플레이스홀더:**")
    st.markdown("이미지 1 | 이미지 2 | 이미지 3")
    
    # 캐러셀 네비게이션 버튼들
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.button("◀", key="carousel_prev")
    
    with col2:
        st.button("●", key="carousel_dot_1")
    
    with col3:
        st.button("●", key="carousel_dot_2")
    
    with col4:
        st.button("●", key="carousel_dot_3")
    
    with col5:
        st.button("▶", key="carousel_next")
    
    st.markdown("---")
    
    # 4. 레이아웃 컴포넌트
    st.header("🏗️ 레이아웃 컴포넌트")
    
    # 히어로 섹션
    linear_hero(
        title="Linear 컴포넌트 시스템",
        subtitle="모던하고 아름다운 UI 컴포넌트를 만나보세요",
        button_text="시작하기",
        key="demo_hero"
    )
    
    st.markdown("---")
    
    # 5. 모던 입력 필드
    st.header("💊 모던 입력 필드")
    
    user_input, button_clicked = linear_modern_input_pill(
        placeholder="이메일을 입력하세요",
        button_text="시작하기",
        key="modern_input"
    )
    
    if button_clicked:
        st.success(f"입력된 이메일: {user_input}")
    
    st.markdown("---")
    
    # 6. Neumorphism 카드들
    st.header("🎴 Neumorphism 카드들")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container():
            st.markdown("### 🎵 음악 플레이어")
            st.markdown("**재생 중:** Beautiful Day")
            st.markdown("**진행률:** 72%")
            st.markdown("**다음 곡:** Summer Vibes")
        
        with st.container():
            st.markdown("### 🖼️ Creative Assets")
            st.markdown("자동 톤 밸런싱과 일관된 브랜드 스타일링으로 비주얼을 업로드하세요.")
            st.markdown("**업로드:** 1,200+ 개")
    
    with col2:
        with st.container():
            st.markdown("### ⭐ 별점 평가")
            st.markdown("**평점:** 4.5/5.0")
            st.markdown("**리뷰:** 1,200+ 개")
            st.markdown("**만족도:** 95%")
        
        with st.container():
            st.markdown("### 🎨 Customize Your Website")
            st.markdown("토큰화된 디자인 컨트롤로 색상, 타이포그래피, 레이아웃을 변경하세요.")
            st.markdown("**템플릿:** 50+ 개")
    
    with col3:
        with st.container():
            st.markdown("### 🔍 검색 기능")
            st.markdown("**검색어:** 최근 인기")
            st.markdown("**결과:** 1,500+ 개")
            st.markdown("**필터:** 지역별")
        
        with st.container():
            st.markdown("### 🌍 Choose Your Region")
            st.markdown("글로벌 오디언스를 위한 현지화된 UI 블록을 제공하세요.")
            st.markdown("**지역:** 15+ 개")
    
    st.markdown("---")
    
    # 7. 푸터
    linear_footer(
        copyright_text="© 2024 Linear Components. All rights reserved.",
        key="demo_footer"
    )