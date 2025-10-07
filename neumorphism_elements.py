"""
streamlit-elements를 이용한 Neumorphism UI 구현
"""
import streamlit as st
from streamlit_elements import elements, mui, html

# 페이지 설정
st.set_page_config(
    page_title="MAIC - Neumorphism UI",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Neumorphism 스타일 정의
NEUMORPHISM_STYLES = {
    "background": {
        "background": "linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)",
        "minHeight": "100vh",
        "fontFamily": "'Poppins', sans-serif",
        "color": "#c1c3e0"
    },
    "card": {
        "background": "rgba(44, 47, 72, 0.9)",
        "backdropFilter": "blur(20px)",
        "borderRadius": "20px",
        "boxShadow": "8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1)",
        "padding": "20px",
        "margin": "20px",
        "color": "#c1c3e0"
    },
    "button": {
        "background": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        "border": "none",
        "borderRadius": "20px",
        "color": "white",
        "fontWeight": "600",
        "padding": "12px 24px",
        "boxShadow": "8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1)",
        "transition": "all 0.3s ease",
        "cursor": "pointer",
        "&:hover": {
            "transform": "translateY(-2px)",
            "boxShadow": "12px 12px 24px rgba(0, 0, 0, 0.4), -12px -12px 24px rgba(255, 255, 255, 0.15)"
        }
    },
    "input": {
        "background": "rgba(44, 47, 72, 0.8)",
        "border": "none",
        "borderRadius": "20px",
        "color": "#c1c3e0",
        "padding": "12px 20px",
        "boxShadow": "inset 8px 8px 16px rgba(0, 0, 0, 0.3), inset -8px -8px 16px rgba(255, 255, 255, 0.1)",
        "outline": "none"
    }
}

def render_neumorphism_app():
    """Neumorphism 스타일의 MAIC 앱 렌더링"""
    
    with elements("neumorphism_maic_app"):
        # 전체 배경 설정
        mui.Box(
            sx=NEUMORPHISM_STYLES["background"]
        )
        
        # Google Fonts 로드는 CSS에서 처리
        
        # 네비게이션 바
        render_navbar()
        
        # 히어로 섹션
        render_hero_section()
        
        # 모드 선택 섹션
        render_mode_selector()
        
        # 입력 섹션
        render_input_section()
        
        # 푸터
        render_footer()

def render_navbar():
    """네비게이션 바 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Box(
            mui.Typography("LEES AI Teacher", variant="h4", sx={"color": "#c1c3e0", "fontWeight": "700"}),
            mui.Box(
                mui.Box(
                    mui.Box(sx={"width": "12px", "height": "12px", "background": "#10b981", "borderRadius": "50%", "animation": "pulse 2s infinite"}),
                    mui.Typography("준비완료", sx={"color": "#c1c3e0", "fontWeight": "600", "marginLeft": "8px"}),
                    sx={"display": "flex", "alignItems": "center", "gap": "8px"}
                ),
                mui.Button(
                    "관리자 로그인",
                    sx=NEUMORPHISM_STYLES["button"]
                ),
                sx={"display": "flex", "alignItems": "center", "gap": "20px"}
            ),
            sx={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}
        )

def render_hero_section():
    """히어로 섹션 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "AI 기반 영어 학습 도우미",
            variant="h2",
            sx={"color": "#c1c3e0", "fontWeight": "700", "textAlign": "center", "marginBottom": "10px"}
        )
        mui.Typography(
            "문법, 독해, 작문을 위한 맞춤형 AI 튜터",
            variant="h6",
            sx={"color": "#c1c3e0", "textAlign": "center", "opacity": 0.8}
        )

def render_mode_selector():
    """모드 선택 섹션 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "질문 모드 선택",
            variant="h5",
            sx={"color": "#c1c3e0", "fontWeight": "600", "textAlign": "center", "marginBottom": "20px"}
        )
        
        mui.Box(
            mui.Button("문법", sx=NEUMORPHISM_STYLES["button"]),
            mui.Button("독해", sx=NEUMORPHISM_STYLES["button"]),
            mui.Button("작문", sx=NEUMORPHISM_STYLES["button"]),
            sx={"display": "flex", "gap": "15px", "justifyContent": "center", "flexWrap": "wrap"}
        )

def render_input_section():
    """입력 섹션 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "질문을 입력하세요",
            variant="h6",
            sx={"color": "#c1c3e0", "fontWeight": "600", "marginBottom": "15px"}
        )
        
        mui.Box(
            mui.TextField(
                placeholder="여기에 질문을 입력하세요...",
                variant="outlined",
                multiline=True,
                rows=3,
                sx=NEUMORPHISM_STYLES["input"]
            ),
            mui.Button(
                "질문하기",
                sx=NEUMORPHISM_STYLES["button"]
            ),
            sx={"display": "flex", "flexDirection": "column", "gap": "15px"}
        )

def render_footer():
    """푸터 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "© 2024 MAIC - AI English Learning Assistant",
            sx={"color": "#c1c3e0", "textAlign": "center", "opacity": 0.7}
        )

# CSS 애니메이션 및 Google Fonts 추가
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

/* Streamlit 기본 스타일 숨기기 */
[data-testid="stSidebar"] {
    display: none !important;
}

[data-testid="stApp"] {
    background: linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%) !important;
}
</style>
""", unsafe_allow_html=True)

# 메인 실행
if __name__ == "__main__":
    render_neumorphism_app()
