# 최종 Neumorphism 앱
import streamlit as st
import streamlit.components.v1 as components

def main():
    st.set_page_config(
        page_title="MAIC - Neumorphism",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # 사이드바 완전 숨기기
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    .stApp > div:first-child {
        display: none !important;
    }
    
    /* 메인 컨테이너 전체 너비 사용 */
    .main .block-container {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* 스크롤바 숨기기 */
    .stApp {
        overflow-x: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # HTML 컴포넌트로 완전한 Neumorphism UI 렌더링
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LEES AI Teacher</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Poppins', sans-serif;
                background: #2c2f48;
                color: #c1c3e0;
                min-height: 100vh;
                overflow-x: hidden;
            }
            
            .container {
                max-width: 1280px;
                margin: 0 auto;
                padding: 2rem;
            }
            
            .header {
                text-align: center;
                margin-bottom: 3rem;
            }
            
            .title {
                font-size: 3rem;
                font-weight: 700;
                color: #e0e0e0;
                margin-bottom: 1rem;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            
            .subtitle {
                font-size: 1.2rem;
                color: #c1c3e0;
                max-width: 600px;
                margin: 0 auto;
                line-height: 1.6;
            }
            
            .cards-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 2rem;
                margin-bottom: 3rem;
            }
            
            .neumorphic-card {
                padding: 2rem;
                border-radius: 30px;
                background: #2c2f48;
                box-shadow: -8px -8px 16px rgba(255, 255, 255, 0.08),
                            8px 8px 16px rgba(0, 0, 0, 0.3);
                text-align: center;
                transition: transform 0.3s ease;
            }
            
            .neumorphic-card:hover {
                transform: translateY(-5px);
            }
            
            .card-title {
                font-size: 1.5rem;
                font-weight: 600;
                color: #e0e0e0;
                margin-bottom: 1rem;
            }
            
            .card-description {
                color: #c1c3e0;
                margin-bottom: 1.5rem;
                line-height: 1.6;
            }
            
            .neumorphic-button {
                padding: 15px 30px;
                border: none;
                border-radius: 15px;
                background: linear-gradient(90deg, #8a63f3, #63b0f3);
                color: white;
                font-size: 1rem;
                font-weight: 500;
                cursor: pointer;
                box-shadow: -5px -5px 10px rgba(255, 255, 255, 0.08),
                            5px 5px 10px rgba(0, 0, 0, 0.3);
                transition: all 0.3s ease;
            }
            
            .neumorphic-button:hover {
                transform: scale(0.98);
                box-shadow: -3px -3px 6px rgba(255, 255, 255, 0.08),
                            3px 3px 6px rgba(0, 0, 0, 0.3);
            }
            
            .input-section {
                background: #2c2f48;
                padding: 2rem;
                border-radius: 30px;
                box-shadow: -8px -8px 16px rgba(255, 255, 255, 0.08),
                            8px 8px 16px rgba(0, 0, 0, 0.3);
                text-align: center;
                margin-bottom: 2rem;
            }
            
            .input-title {
                font-size: 1.5rem;
                font-weight: 600;
                color: #e0e0e0;
                margin-bottom: 1.5rem;
            }
            
            .neumorphic-input {
                padding: 15px 20px;
                border: none;
                border-radius: 15px;
                background: #2c2f48;
                color: #c1c3e0;
                font-size: 1rem;
                box-shadow: inset -5px -5px 10px rgba(255, 255, 255, 0.08),
                            inset 5px 5px 10px rgba(0, 0, 0, 0.3);
                margin: 10px;
                width: 300px;
                outline: none;
            }
            
            .neumorphic-input:focus {
                box-shadow: inset -3px -3px 6px rgba(255, 255, 255, 0.08),
                            inset 3px 3px 6px rgba(0, 0, 0, 0.3);
            }
            
            .footer {
                text-align: center;
                margin-top: 3rem;
                padding: 2rem;
                color: #8a8a8a;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="title">LEES AI Teacher</h1>
                <p class="subtitle">AI 영어 학습의 새로운 경험<br>문법, 독해, 작문을 한 번에!</p>
            </div>
            
            <div class="cards-grid">
                <div class="neumorphic-card">
                    <h3 class="card-title">문법 학습</h3>
                    <p class="card-description">AI가 당신의 문법 실력을 체크하고 개선해드립니다.</p>
                    <button class="neumorphic-button" onclick="startGrammar()">시작하기</button>
                </div>
                
                <div class="neumorphic-card">
                    <h3 class="card-title">독해 연습</h3>
                    <p class="card-description">다양한 텍스트로 독해 실력을 향상시켜보세요.</p>
                    <button class="neumorphic-button" onclick="startReading()">시작하기</button>
                </div>
                
                <div class="neumorphic-card">
                    <h3 class="card-title">작문 연습</h3>
                    <p class="card-description">AI와 함께 영어 작문 실력을 키워보세요.</p>
                    <button class="neumorphic-button" onclick="startWriting()">시작하기</button>
                </div>
            </div>
            
            <div class="input-section">
                <h3 class="input-title">질문하기</h3>
                <input type="text" class="neumorphic-input" placeholder="질문을 입력하세요..." id="question-input">
                <br>
                <button class="neumorphic-button" onclick="askQuestion()">질문하기</button>
            </div>
            
            <div class="footer">
                <p>&copy; 2024 LEES AI Teacher. All rights reserved.</p>
            </div>
        </div>
        
        <script>
            function startGrammar() {
                alert('문법 학습을 시작합니다!');
            }
            
            function startReading() {
                alert('독해 연습을 시작합니다!');
            }
            
            function startWriting() {
                alert('작문 연습을 시작합니다!');
            }
            
            function askQuestion() {
                const input = document.getElementById('question-input');
                const question = input.value.trim();
                if (question) {
                    alert('질문: ' + question + '\\n\\nAI가 답변을 준비하고 있습니다...');
                    input.value = '';
                } else {
                    alert('질문을 입력해주세요!');
                }
            }
            
            document.getElementById('question-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    askQuestion();
                }
            });
        </script>
    </body>
    </html>
    """
    
    # HTML 컴포넌트로 렌더링
    components.html(html_content, height=800, scrolling=True)

if __name__ == "__main__":
    main()
