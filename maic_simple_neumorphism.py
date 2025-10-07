"""
MAIC 기능과 연결된 간단한 Neumorphism UI (Streamlit 네이티브)
"""
import streamlit as st
import json
from pathlib import Path
import sys

# MAIC 모듈 import
sys.path.append(str(Path(__file__).parent))
from src.application.modes.router import ModeRouter
from src.application.modes.types import Mode

st.set_page_config(
    page_title="MAIC - Simple Neumorphism",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 세션 상태 초기화
if 'selected_mode' not in st.session_state:
    st.session_state.selected_mode = None
if 'question' not in st.session_state:
    st.session_state.question = ""
if 'response' not in st.session_state:
    st.session_state.response = ""

# CSS 스타일 주입
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

/* 전체 배경 */
.stApp {
    background: linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%) !important;
    font-family: 'Poppins', sans-serif !important;
    color: #c1c3e0 !important;
    min-height: 100vh !important;
}

/* 메인 컨테이너 */
.main .block-container {
    padding: 20px !important;
    max-width: 1200px !important;
}

/* Neumorphism 카드 */
.neumorphic-card {
    background: rgba(44, 47, 72, 0.9);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1);
    padding: 30px;
    margin: 20px 0;
    color: #c1c3e0;
}

/* Neumorphism 버튼 */
.stButton > button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    border: none !important;
    border-radius: 20px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    transition: all 0.3s ease !important;
    font-family: 'Poppins', sans-serif !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 12px 12px 24px rgba(0, 0, 0, 0.4), -12px -12px 24px rgba(255, 255, 255, 0.15) !important;
}

/* 활성 버튼 */
.stButton > button.active {
    background: linear-gradient(135deg, #818cf8, #a78bfa) !important;
    box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.4), -8px -8px 16px rgba(255, 255, 255, 0.2) !important;
}

/* Neumorphism 입력 */
.stTextInput > div > div > input {
    background: rgba(44, 47, 72, 0.8) !important;
    border: none !important;
    border-radius: 20px !important;
    padding: 15px 20px !important;
    color: #c1c3e0 !important;
    box-shadow: inset 8px 8px 16px rgba(0, 0, 0, 0.3), inset -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    font-family: 'Poppins', sans-serif !important;
}

.stTextInput > div > div > input::placeholder {
    color: #8b8fa3 !important;
}

/* 텍스트 색상 */
h1, h2, h3, p, div {
    color: #c1c3e0 !important;
}

/* 펄스 애니메이션 */
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

.pulse-dot {
    animation: pulse 2s infinite;
    width: 12px;
    height: 12px;
    background: #10b981;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
}

/* 응답 영역 */
.response-area {
    background: rgba(44, 47, 72, 0.8);
    border-radius: 20px;
    padding: 20px;
    margin: 20px 0;
    box-shadow: inset 8px 8px 16px rgba(0, 0, 0, 0.3), inset -8px -8px 16px rgba(255, 255, 255, 0.1);
    color: #c1c3e0;
    font-family: 'Poppins', sans-serif;
    white-space: pre-wrap;
    line-height: 1.6;
    min-height: 200px;
}
</style>
""", unsafe_allow_html=True)

# MAIC 모드 라우터 초기화
@st.cache_resource
def get_mode_router():
    return ModeRouter()

mode_router = get_mode_router()

# 네비게이션 바
st.markdown("""
<div class="neumorphic-card">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <h1 style="color: #c1c3e0; font-weight: 700; font-size: 2rem; margin: 0;">LEES AI Teacher</h1>
        <div style="display: flex; align-items: center;">
            <span class="pulse-dot"></span>
            <span style="color: #10b981; font-size: 14px; font-weight: 500;">준비완료</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 히어로 섹션
st.markdown("""
<div class="neumorphic-card">
    <h2 style="color: #c1c3e0; text-align: center; margin-bottom: 20px; font-weight: 700; font-size: 2.5rem;">
        AI 영어 학습 어시스턴트
    </h2>
    <p style="color: #8b8fa3; text-align: center; opacity: 0.8; font-size: 1.2rem;">
        Neumorphism UI로 구현된 현대적인 영어 학습 플랫폼
    </p>
</div>
""", unsafe_allow_html=True)

# 모드 선택 섹션
st.markdown("""
<div class="neumorphic-card">
    <h3 style="color: #c1c3e0; margin-bottom: 20px; font-weight: 600; font-size: 1.5rem;">
        학습 모드 선택
    </h3>
</div>
""", unsafe_allow_html=True)

# 모드 선택 버튼들
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("문법 학습", key="grammar_btn", help="문법 설명 모드"):
        st.session_state.selected_mode = "grammar"
        st.rerun()

with col2:
    if st.button("문장 분석", key="sentence_btn", help="문장 분석 모드"):
        st.session_state.selected_mode = "sentence"
        st.rerun()

with col3:
    if st.button("지문 설명", key="passage_btn", help="지문 설명 모드"):
        st.session_state.selected_mode = "passage"
        st.rerun()

# 선택된 모드 표시
if st.session_state.selected_mode:
    mode_names = {
        "grammar": "문법 학습",
        "sentence": "문장 분석", 
        "passage": "지문 설명"
    }
    st.success(f"✅ 선택된 모드: {mode_names[st.session_state.selected_mode]}")

# 질문 입력 섹션
st.markdown("""
<div class="neumorphic-card">
    <h3 style="color: #c1c3e0; margin-bottom: 15px; font-weight: 500; font-size: 1.3rem;">
        질문을 입력하세요
    </h3>
</div>
""", unsafe_allow_html=True)

# 질문 입력
question = st.text_input(
    "질문을 입력하세요",
    placeholder="여기에 질문을 입력하세요...",
    key="question_input"
)

# 질문 제출 버튼
if st.button("질문하기", key="submit_btn"):
    if not question.strip():
        st.error("질문을 입력해주세요!")
    elif not st.session_state.selected_mode:
        st.error("학습 모드를 먼저 선택해주세요!")
    else:
        try:
            # MAIC 모드 라우터로 프롬프트 생성
            mode_enum = Mode.from_str(st.session_state.selected_mode)
            bundle = mode_router.render_prompt(
                mode=mode_enum,
                question=question
            )
            
            # 응답 생성
            response = f"""**모드**: {bundle.mode.value}
**라벨**: {bundle.source_label}

**생성된 프롬프트**:
{bundle.prompt}

**섹션 순서**:
{chr(10).join(f"{i+1}. {section}" for i, section in enumerate(bundle.sections))}

**컨텍스트 조각 수**: {len(bundle.context_fragments)}"""
            
            st.session_state.response = response
            st.session_state.question = question
            
        except Exception as e:
            st.error(f"오류가 발생했습니다: {str(e)}")

# 응답 섹션
st.markdown("""
<div class="neumorphic-card">
    <h3 style="color: #c1c3e0; margin-bottom: 15px; font-weight: 500; font-size: 1.3rem;">
        AI 응답
    </h3>
</div>
""", unsafe_allow_html=True)

# 응답 표시
if st.session_state.response:
    st.markdown(f"""
    <div class="response-area">
        {st.session_state.response}
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="response-area">
        아직 질문이 없습니다. 위에서 질문을 입력해보세요!
    </div>
    """, unsafe_allow_html=True)

# 푸터
st.markdown("""
<div style="text-align: center; color: #8b8fa3; opacity: 0.6; padding: 20px; margin-top: 40px;">
    © 2024 MAIC - AI English Learning Assistant
</div>
""", unsafe_allow_html=True)
