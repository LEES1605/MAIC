# 순수 Neumorphism 앱
import streamlit as st

def main():
    st.set_page_config(
        page_title="MAIC - Neumorphism",
        page_icon="🎓",
        layout="wide"
    )
    
    # 강력한 CSS 주입
    css = """
    <style>
    /* Streamlit 완전 제거 */
    .stApp {
        background: #2c2f48 !important;
        color: #c1c3e0 !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* 모든 Streamlit 요소 숨기기 */
    .stApp > div:first-child,
    section[data-testid="stSidebar"],
    .stApp > div > div:first-child {
        display: none !important;
    }
    
    /* 메인 컨테이너 */
    .main .block-container {
        max-width: 1280px !important;
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
    
    /* Neumorphism 카드 */
    .neumorphic-card {
        padding: 25px;
        border-radius: 30px;
        background-color: var(--bg-color);
        box-shadow: -8px -8px 16px var(--light-shadow),
                     8px 8px 16px var(--dark-shadow);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        margin: 20px 0;
    }
    
    /* 버튼 스타일 */
    .neumorphic-button {
        padding: 15px 30px;
        border: none;
        border-radius: 15px;
        background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
        color: white;
        font-size: 1rem;
        cursor: pointer;
        box-shadow: -5px -5px 10px var(--light-shadow),
                    5px 5px 10px var(--dark-shadow);
        transition: transform 0.2s ease;
        margin: 10px;
    }
    
    .neumorphic-button:hover {
        transform: scale(0.98);
    }
    
    /* 입력 필드 */
    .neumorphic-input {
        padding: 15px 20px;
        border: none;
        border-radius: 15px;
        background-color: var(--bg-color);
        color: var(--text-color);
        font-size: 1rem;
        box-shadow: inset -5px -5px 10px var(--light-shadow),
                    inset 5px 5px 10px var(--dark-shadow);
        margin: 10px;
        width: 300px;
    }
    
    /* 제목 */
    .neumorphic-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #e0e0e0;
        text-align: center;
        margin: 20px 0;
    }
    
    /* 설명 */
    .neumorphic-description {
        font-size: 1.1rem;
        color: var(--text-color);
        text-align: center;
        margin: 20px 0;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)
    
    # Neumorphism UI
    st.markdown('<h1 class="neumorphic-title">LEES AI Teacher</h1>', unsafe_allow_html=True)
    st.markdown('<p class="neumorphic-description">AI 영어 학습의 새로운 경험<br>문법, 독해, 작문을 한 번에!</p>', unsafe_allow_html=True)
    
    # 카드들
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('''
        <div class="neumorphic-card">
            <h3>문법 학습</h3>
            <p>AI가 당신의 문법 실력을 체크하고 개선해드립니다.</p>
            <button class="neumorphic-button" onclick="alert('문법 학습 시작!')">시작하기</button>
        </div>
        ''', unsafe_allow_html=True)
    
    with col2:
        st.markdown('''
        <div class="neumorphic-card">
            <h3>독해 연습</h3>
            <p>다양한 텍스트로 독해 실력을 향상시켜보세요.</p>
            <button class="neumorphic-button" onclick="alert('독해 연습 시작!')">시작하기</button>
        </div>
        ''', unsafe_allow_html=True)
    
    # 입력 섹션
    st.markdown('''
    <div class="neumorphic-card">
        <h3>질문하기</h3>
        <input type="text" class="neumorphic-input" placeholder="질문을 입력하세요..." id="question-input">
        <br>
        <button class="neumorphic-button" onclick="askQuestion()">질문하기</button>
    </div>
    ''', unsafe_allow_html=True)
    
    # JavaScript
    js = """
    <script>
    function askQuestion() {
        const input = document.getElementById('question-input');
        const question = input.value.trim();
        if (question) {
            alert('질문: ' + question + '\\n\\nAI가 답변을 준비하고 있습니다...');
            input.value = '';
        }
    }
    
    document.getElementById('question-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            askQuestion();
        }
    });
    </script>
    """
    
    st.markdown(js, unsafe_allow_html=True)

if __name__ == "__main__":
    main()


