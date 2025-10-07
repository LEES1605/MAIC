"""
streamlit-elements를 이용한 Neumorphism UI 구현 (완전 수정 버전)
"""
import streamlit as st
from streamlit_elements import elements, mui

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
        "padding": "15px 20px",
        "color": "#c1c3e0",
        "boxShadow": "inset 8px 8px 16px rgba(0, 0, 0, 0.3), inset -8px -8px 16px rgba(255, 255, 255, 0.1)",
        "&::placeholder": {
            "color": "#8b8fa3"
        }
    }
}

def render_neumorphism_app():
    """Neumorphism UI 앱 렌더링"""
    
    # CSS 스타일 주입 (st.markdown 사용)
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    /* Streamlit 기본 스타일 숨기기 */
    .stApp > div:first-child {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* 커스텀 스크롤바 */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(44, 47, 72, 0.3);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #5b5cf0, #7c3aed);
    }
    
    /* 펄스 애니메이션 */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .pulse-dot {
        animation: pulse 2s infinite;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with elements("neumorphism_maic_app"):
        # 전체 배경 설정
        mui.Box(
            sx=NEUMORPHISM_STYLES["background"]
        )
        
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
                    sx={
                        "width": "12px",
                        "height": "12px",
                        "background": "#10b981",
                        "borderRadius": "50%",
                        "marginRight": "8px",
                        "animation": "pulse 2s infinite"
                    }
                ),
                mui.Typography("준비완료", sx={"color": "#10b981", "fontSize": "14px", "fontWeight": "500"}),
                sx={"display": "flex", "alignItems": "center", "marginLeft": "auto"}
            ),
            mui.Button(
                "관리자 로그인",
                sx=NEUMORPHISM_STYLES["button"],
                onClick=lambda: st.success("관리자 로그인 클릭!")
            ),
            sx={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "20px"}
        )

def render_hero_section():
    """히어로 섹션 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "AI 영어 학습 어시스턴트",
            variant="h2",
            sx={"color": "#c1c3e0", "textAlign": "center", "marginBottom": "20px", "fontWeight": "700"}
        )
        mui.Typography(
            "Neumorphism UI로 구현된 현대적인 영어 학습 플랫폼",
            variant="h6",
            sx={"color": "#8b8fa3", "textAlign": "center", "opacity": 0.8}
        )

def render_mode_selector():
    """모드 선택 섹션 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "질문 모드 선택",
            variant="h5",
            sx={"color": "#c1c3e0", "marginBottom": "20px", "fontWeight": "600"}
        )
        
        mui.Box(
            mui.Button("문법", sx=NEUMORPHISM_STYLES["button"]),
            mui.Button("독해", sx=NEUMORPHISM_STYLES["button"]),
            mui.Button("작문", sx=NEUMORPHISM_STYLES["button"]),
            sx={"display": "flex", "gap": "15px", "justifyContent": "center"}
        )

def render_input_section():
    """입력 섹션 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "질문을 입력하세요",
            variant="h6",
            sx={"color": "#c1c3e0", "marginBottom": "15px", "fontWeight": "500"}
        )
        
        mui.Box(
            mui.TextField(
                placeholder="여기에 질문을 입력하세요...",
                variant="outlined",
                sx=NEUMORPHISM_STYLES["input"]
            ),
            mui.Button(
                "질문하기",
                sx=NEUMORPHISM_STYLES["button"],
                onClick=lambda: st.success("질문이 전송되었습니다!")
            ),
            sx={"display": "flex", "gap": "15px", "alignItems": "center"}
        )

def render_footer():
    """푸터 렌더링"""
    with mui.Box(sx=NEUMORPHISM_STYLES["card"]):
        mui.Typography(
            "© 2024 MAIC - AI English Learning Assistant",
            sx={"color": "#8b8fa3", "textAlign": "center", "opacity": 0.6, "padding": "20px"}
        )

# 메인 실행
if __name__ == "__main__":
    render_neumorphism_app()
