"""
작동하는 Neumorphism UI (순수 HTML 방식)
"""
import streamlit as st

st.set_page_config(
    page_title="MAIC - Working Neumorphism",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
</style>
""", unsafe_allow_html=True)

# HTML 컴포넌트로 전체 UI 렌더링
st.components.v1.html("""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MAIC - Neumorphism UI</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%);
            font-family: 'Poppins', sans-serif;
            color: #c1c3e0;
            min-height: 100vh;
            padding: 20px;
        }
        
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
        
        .navbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            margin-left: auto;
        }
        
        .pulse-dot {
            width: 12px;
            height: 12px;
            background: #10b981;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        .status-text {
            color: #10b981;
            font-size: 14px;
            font-weight: 500;
        }
        
        .admin-login-btn {
            background: linear-gradient(90deg, #6366f1, #8b5cf6);
            border: none;
            border-radius: 20px;
            color: white;
            padding: 10px 20px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .admin-login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
        }
        
        .mode-selector {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin: 20px 0;
        }
        
        .mode-btn {
            background: rgba(44, 47, 72, 0.8);
            border: none;
            border-radius: 20px;
            color: #c1c3e0;
            padding: 12px 24px;
            box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.3), -8px -8px 16px rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
            cursor: pointer;
            font-family: 'Poppins', sans-serif;
        }
        
        .mode-btn:hover {
            transform: translateY(-2px);
            box-shadow: 12px 12px 24px rgba(0, 0, 0, 0.4), -12px -12px 24px rgba(255, 255, 255, 0.15);
        }
        
        .mode-btn.active {
            background: linear-gradient(135deg, #818cf8, #a78bfa);
            color: white;
            box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.4), -8px -8px 16px rgba(255, 255, 255, 0.2);
        }
        
        .input-section {
            display: flex;
            gap: 15px;
            align-items: center;
            margin: 20px 0;
        }
        
        .footer {
            text-align: center;
            color: #8b8fa3;
            opacity: 0.6;
            padding: 20px;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <!-- 네비게이션 바 -->
    <div class="neumorphic-card">
        <div class="navbar">
            <h1 style="color: #c1c3e0; font-weight: 700; font-size: 2rem;">LEES AI Teacher</h1>
            <div class="status-indicator">
                <div class="pulse-dot"></div>
                <span class="status-text">준비완료</span>
            </div>
            <button class="admin-login-btn" onclick="adminLogin()">관리자 로그인</button>
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
            질문 모드 선택
        </h3>
        <div class="mode-selector">
            <button class="mode-btn" onclick="selectMode(this)">문법</button>
            <button class="mode-btn" onclick="selectMode(this)">독해</button>
            <button class="mode-btn" onclick="selectMode(this)">작문</button>
        </div>
    </div>
    
    <!-- 입력 섹션 -->
    <div class="neumorphic-card">
        <h3 style="color: #c1c3e0; margin-bottom: 15px; font-weight: 500; font-size: 1.3rem;">
            질문을 입력하세요
        </h3>
        <div class="input-section">
            <input type="text" class="neumorphic-input" placeholder="여기에 질문을 입력하세요...">
            <button class="neumorphic-button" onclick="submitQuestion()">질문하기</button>
        </div>
    </div>
    
    <!-- 대화 기록 -->
    <div class="neumorphic-card">
        <h3 style="color: #c1c3e0; margin-bottom: 15px; font-weight: 500; font-size: 1.3rem;">
            대화 기록
        </h3>
        <p style="color: #8b8fa3; text-align: center; opacity: 0.8;">
            아직 대화가 없습니다. 위에서 질문을 입력해보세요!
        </p>
    </div>
    
    <!-- 푸터 -->
    <div class="footer">
        © 2024 MAIC - AI English Learning Assistant
    </div>
    
    <script>
        function adminLogin() {
            alert('관리자 로그인 기능이 구현되었습니다!');
        }
        
        function selectMode(button) {
            // 모든 버튼에서 active 클래스 제거
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            // 클릭된 버튼에 active 클래스 추가
            button.classList.add('active');
        }
        
        function submitQuestion() {
            alert('질문이 전송되었습니다!');
        }
    </script>
</body>
</html>
""", height=800, scrolling=True)
