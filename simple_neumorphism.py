# 간단한 Neumorphism 앱
import streamlit as st

def main():
    st.set_page_config(
        page_title="MAIC - Neumorphism",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # 강력한 CSS 주입
    css = """
    <style>
    /* Streamlit 기본 스타일 완전 제거 */
    .stApp {
        background: #2c2f48 !important;
        color: #c1c3e0 !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* 사이드바 완전 숨기기 */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* 메인 컨테이너 전체 너비 */
    .main .block-container {
        max-width: 100% !important;
        padding: 2rem !important;
        background: transparent !important;
    }
    
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
    
    /* CSS 변수 */
    :root {
        --bg-color: #2c2f48;
        --text-color: #c1c3e0;
        --light-shadow: rgba(255, 255, 255, 0.08);
        --dark-shadow: rgba(0, 0, 0, 0.3);
        --gradient-start: #8a63f3;
        --gradient-end: #63b0f3;
    }
    
    /* 제목 스타일 */
    .neumorphic-title {
        font-size: 3rem !important;
        font-weight: 700 !important;
        color: #e0e0e0 !important;
        text-align: center !important;
        margin: 2rem 0 !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    }
    
    /* 설명 스타일 */
    .neumorphic-description {
        font-size: 1.2rem !important;
        color: #c1c3e0 !important;
        text-align: center !important;
        margin: 2rem 0 !important;
        max-width: 600px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        line-height: 1.6 !important;
    }
    
    /* 컨테이너 스타일 */
    .neumorphic-container {
        padding: 2rem !important;
        border-radius: 30px !important;
        background: #2c2f48 !important;
        box-shadow: -8px -8px 16px rgba(255, 255, 255, 0.08),
                    8px 8px 16px rgba(0, 0, 0, 0.3) !important;
        margin: 2rem 0 !important;
        text-align: center !important;
    }
    
    /* 카드 제목 */
    .neumorphic-card-title {
        font-size: 1.5rem !important;
        font-weight: 600 !important;
        color: #e0e0e0 !important;
        margin-bottom: 1rem !important;
    }
    
    /* 카드 설명 */
    .neumorphic-card-description {
        color: #c1c3e0 !important;
        margin-bottom: 1.5rem !important;
        line-height: 1.6 !important;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        padding: 15px 30px !important;
        border: none !important;
        border-radius: 15px !important;
        background: linear-gradient(90deg, #8a63f3, #63b0f3) !important;
        color: white !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        box-shadow: -5px -5px 10px rgba(255, 255, 255, 0.08),
                    5px 5px 10px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.3s ease !important;
        margin: 10px !important;
    }
    
    .stButton > button:hover {
        transform: scale(0.98) !important;
        box-shadow: -3px -3px 6px rgba(255, 255, 255, 0.08),
                    3px 3px 6px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 입력 필드 스타일 */
    .stTextInput > div > div > input {
        padding: 15px 20px !important;
        border: none !important;
        border-radius: 15px !important;
        background: #2c2f48 !important;
        color: #c1c3e0 !important;
        font-size: 1rem !important;
        box-shadow: inset -5px -5px 10px rgba(255, 255, 255, 0.08),
                    inset 5px 5px 10px rgba(0, 0, 0, 0.3) !important;
        margin: 10px !important;
    }
    
    .stTextInput > div > div > input:focus {
        box-shadow: inset -3px -3px 6px rgba(255, 255, 255, 0.08),
                    inset 3px 3px 6px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 컬럼 스타일 */
    .stColumn {
        padding: 1rem !important;
    }
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    
    # 제목
    st.markdown('<h1 class="neumorphic-title">LEES AI Teacher</h1>', unsafe_allow_html=True)
    st.markdown('<p class="neumorphic-description">AI 영어 학습의 새로운 경험<br>문법, 독해, 작문을 한 번에!</p>', unsafe_allow_html=True)
    
    # 카드들
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="neumorphic-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="neumorphic-card-title">문법 학습</h3>', unsafe_allow_html=True)
        st.markdown('<p class="neumorphic-card-description">AI가 당신의 문법 실력을 체크하고 개선해드립니다.</p>', unsafe_allow_html=True)
        if st.button("시작하기", key="grammar"):
            st.success("문법 학습을 시작합니다!")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="neumorphic-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="neumorphic-card-title">독해 연습</h3>', unsafe_allow_html=True)
        st.markdown('<p class="neumorphic-card-description">다양한 텍스트로 독해 실력을 향상시켜보세요.</p>', unsafe_allow_html=True)
        if st.button("시작하기", key="reading"):
            st.success("독해 연습을 시작합니다!")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="neumorphic-container">', unsafe_allow_html=True)
        st.markdown('<h3 class="neumorphic-card-title">작문 연습</h3>', unsafe_allow_html=True)
        st.markdown('<p class="neumorphic-card-description">AI와 함께 영어 작문 실력을 키워보세요.</p>', unsafe_allow_html=True)
        if st.button("시작하기", key="writing"):
            st.success("작문 연습을 시작합니다!")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 질문 섹션
    st.markdown('<div class="neumorphic-container">', unsafe_allow_html=True)
    st.markdown('<h3 class="neumorphic-card-title">질문하기</h3>', unsafe_allow_html=True)
    
    question = st.text_input("질문을 입력하세요...", key="question")
    
    if st.button("질문하기", key="ask"):
        if question:
            st.success(f"질문: {question}\\n\\nAI가 답변을 준비하고 있습니다...")
        else:
            st.warning("질문을 입력해주세요!")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 푸터
    st.markdown('<div style="text-align: center; margin-top: 3rem; padding: 2rem; color: #8a8a8a;">', unsafe_allow_html=True)
    st.markdown('<p>&copy; 2024 LEES AI Teacher. All rights reserved.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
