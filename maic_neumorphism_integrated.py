"""
MAIC 기능과 연결된 Neumorphism UI
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
    page_title="MAIC - Neumorphism UI",
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
    padding: 0 !important;
    max-width: 100% !important;
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

/* Neumorphism 스타일 */
.neumorphic-card {
    background: rgba(44, 47, 72, 0.9);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1);
    padding: 20px;
    margin: 20px 0;
    color: #c1c3e0;
}

.neumorphic-button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border: none;
    border-radius: 20px;
    color: white;
    font-weight: 600;
    padding: 12px 24px;
    box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1);
    transition: all 0.3s ease;
    cursor: pointer;
    font-family: 'Poppins', sans-serif;
}

.neumorphic-button:hover {
    transform: translateY(-2px);
    box-shadow: 12px 12px 24px rgba(0, 0, 0, 0.4), -12px -12px 24px rgba(255, 255, 255, 0.15);
}

.neumorphic-button.active {
    background: linear-gradient(135deg, #818cf8, #a78bfa);
    box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.4), -8px -8px 16px rgba(255, 255, 255, 0.2);
}

.neumorphic-input {
    background: rgba(44, 47, 72, 0.8);
    border: none;
    border-radius: 20px;
    padding: 15px 20px;
    color: #c1c3e0;
    box-shadow: inset 8px 8px 16px rgba(0, 0, 0, 0.3), inset -8px -8px 16px rgba(255, 255, 255, 0.1);
    font-family: 'Poppins', sans-serif;
    width: 100%;
}

.neumorphic-input::placeholder {
    color: #8b8fa3;
}

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
}
</style>
""", unsafe_allow_html=True)

# MAIC 모드 라우터 초기화
@st.cache_resource
def get_mode_router():
    return ModeRouter()

mode_router = get_mode_router()

# HTML 컴포넌트로 UI 렌더링
st.components.v1.html(f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MAIC - Neumorphism UI</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <!-- 네비게이션 바 -->
    <div class="neumorphic-card">
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 20px;">
            <h1 style="color: #c1c3e0; font-weight: 700; font-size: 2rem;">LEES AI Teacher</h1>
            <div style="display: flex; align-items: center; margin-left: auto;">
                <div class="pulse-dot" style="width: 12px; height: 12px; background: #10b981; border-radius: 50%; margin-right: 8px;"></div>
                <span style="color: #10b981; font-size: 14px; font-weight: 500;">준비완료</span>
            </div>
            <button class="neumorphic-button" onclick="adminLogin()">관리자 로그인</button>
        </div>
    </div>
    
    <!-- 히어로 섹션 -->
    <div class="neumorphic-card">
        <h2 style="color: #c1c3e0; text-align: center; margin-bottom: 20px; font-weight: 700; font-size: 2.5rem;">
            AI 영어 학습 어시스턴트
        </h2>
        <p style="color: #8b8fa3; text-align: center; opacity: 0.8; font-size: 1.2rem;">
            Neumorphism UI로 구현된 현대적인 영어 학습 플랫폼
        </p>
    </div>
    
    <!-- 모드 선택 섹션 -->
    <div class="neumorphic-card">
        <h3 style="color: #c1c3e0; margin-bottom: 20px; font-weight: 600; font-size: 1.5rem;">
            학습 모드 선택
        </h3>
        <div style="display: flex; gap: 15px; justify-content: center; margin: 20px 0;">
            <button class="neumorphic-button" onclick="selectMode('grammar', this)">문법 학습</button>
            <button class="neumorphic-button" onclick="selectMode('sentence', this)">문장 분석</button>
            <button class="neumorphic-button" onclick="selectMode('passage', this)">지문 설명</button>
        </div>
    </div>
    
    <!-- 입력 섹션 -->
    <div class="neumorphic-card">
        <h3 style="color: #c1c3e0; margin-bottom: 15px; font-weight: 500; font-size: 1.3rem;">
            질문을 입력하세요
        </h3>
        <div style="display: flex; gap: 15px; align-items: center; margin: 20px 0;">
            <input type="text" id="questionInput" class="neumorphic-input" placeholder="여기에 질문을 입력하세요...">
            <button class="neumorphic-button" onclick="submitQuestion()">질문하기</button>
        </div>
    </div>
    
    <!-- 응답 섹션 -->
    <div class="neumorphic-card">
        <h3 style="color: #c1c3e0; margin-bottom: 15px; font-weight: 500; font-size: 1.3rem;">
            AI 응답
        </h3>
        <div id="responseArea" class="response-area">
            아직 질문이 없습니다. 위에서 질문을 입력해보세요!
        </div>
    </div>
    
    <!-- 푸터 -->
    <div style="text-align: center; color: #8b8fa3; opacity: 0.6; padding: 20px;">
        © 2024 MAIC - AI English Learning Assistant
    </div>
    
    <script>
        let currentMode = null;
        
        function adminLogin() {{
            alert('관리자 로그인 기능이 구현되었습니다!');
        }}
        
        function selectMode(mode, button) {{
            // 모든 버튼에서 active 클래스 제거
            document.querySelectorAll('.neumorphic-button').forEach(btn => {{
                btn.classList.remove('active');
            }});
            // 클릭된 버튼에 active 클래스 추가
            button.classList.add('active');
            currentMode = mode;
            console.log('Selected mode:', mode);
        }}
        
        function submitQuestion() {{
            const question = document.getElementById('questionInput').value;
            if (!question.trim()) {{
                alert('질문을 입력해주세요!');
                return;
            }}
            if (!currentMode) {{
                alert('학습 모드를 먼저 선택해주세요!');
                return;
            }}
            
            // Streamlit에 데이터 전송
            window.parent.postMessage({{
                type: 'submit_question',
                mode: currentMode,
                question: question
            }}, '*');
            
            // 로딩 표시
            document.getElementById('responseArea').innerHTML = 'AI가 답변을 생성하고 있습니다...';
        }}
        
        // Streamlit에서 응답 받기
        window.addEventListener('message', function(event) {{
            if (event.data.type === 'response') {{
                document.getElementById('responseArea').innerHTML = event.data.response;
            }}
        }});
    </script>
</body>
</html>
""", height=800, scrolling=True)

# Streamlit에서 질문 처리
if st.session_state.get('question_data'):
    mode = st.session_state.question_data.get('mode')
    question = st.session_state.question_data.get('question')
    
    if mode and question:
        try:
            # MAIC 모드 라우터로 프롬프트 생성
            mode_enum = Mode.from_str(mode)
            bundle = mode_router.render_prompt(
                mode=mode_enum,
                question=question
            )
            
            # 응답 생성 (실제로는 LLM 호출)
            response = f"""
**모드**: {bundle.mode.value}
**라벨**: {bundle.source_label}

**생성된 프롬프트**:
{bundle.prompt}

**섹션 순서**:
{chr(10).join(f"{i+1}. {section}" for i, section in enumerate(bundle.sections))}

**컨텍스트 조각 수**: {len(bundle.context_fragments)}
"""
            
            st.session_state.response = response
            st.session_state.question_data = None  # 처리 완료
            
        except Exception as e:
            st.session_state.response = f"오류가 발생했습니다: {str(e)}"
            st.session_state.question_data = None

# JavaScript와 통신을 위한 메시지 처리
st.markdown("""
<script>
// Streamlit에서 HTML로 메시지 전송
if (window.parent !== window) {
    window.parent.postMessage({
        type: 'response',
        response: `{st.session_state.response}`
    }, '*');
}
</script>
""", unsafe_allow_html=True)

