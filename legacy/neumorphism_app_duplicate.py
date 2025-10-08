# Neumorphism MAIC 앱
"""
사용자가 제공한 Neumorphism 디자인을 적용한 MAIC 앱
- 공중에 떠있는 버튼 효과
- 글래스모피즘 디자인
- 완전한 HTML/CSS 구현
"""

import streamlit as st
from pathlib import Path


def render_neumorphism_maic_app():
    """(Deprecated) 프로그래매틱 렌더는 사용하지 않음: 정본 HTML만 사용"""
    from .html_app import render_neumorphism_html_file
    render_neumorphism_html_file()


def _inject_neumorphism_styles():
    """Neumorphism CSS 스타일 주입"""
    
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
    
    /* 메인 컨테이너 스타일 */
    .main .block-container {
        max-width: 1280px !important;
        padding: 2rem !important;
        background: transparent !important;
    }
    
    /* 모든 Streamlit 요소 숨기기 */
    .stApp > div:first-child {
        display: none !important;
    }
    
    /* 커스텀 컨테이너만 보이기 */
    .neumorphism-container {
        display: block !important;
    }
    /* Google Fonts - Poppins */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
    
    /* CSS 변수 정의 */
    :root {
        --bg-color: #2c2f48;
        --text-color: #c1c3e0;
        --light-shadow: rgba(255, 255, 255, 0.08);
        --dark-shadow: rgba(0, 0, 0, 0.3);
        --gradient-start: #8a63f3;
        --gradient-end: #63b0f3;
        --star-color: #ffd700;
    }
    
    /* Streamlit 앱 전체 스타일 */
    .stApp {
        background-color: var(--bg-color) !important;
        color: var(--text-color) !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* 사이드바 숨기기 */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* 메인 컨테이너 */
    .main .block-container {
        max-width: 1280px !important;
        padding: 2rem !important;
        background: transparent !important;
    }
    
    /* 헤더 스타일 */
    .maic-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1.5rem;
        margin-bottom: 4rem;
    }
    
    .logo-text {
        font-weight: 700;
        font-size: 1.5rem;
        color: #e0e0e0;
    }
    
    .main-nav {
        display: flex;
        gap: 25px;
        flex-wrap: wrap;
    }
    
    .nav-item {
        font-size: 1rem;
        color: var(--text-color);
        text-decoration: none;
        transition: color 0.3s ease;
        cursor: pointer;
    }
    
    .nav-item:hover {
        color: var(--gradient-start);
    }
    
    .signup-button {
        padding: 10px 20px;
        border: 1px solid var(--text-color);
        border-radius: 10px;
        background: transparent;
        color: var(--text-color);
        font-size: 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .signup-button:hover {
        background-color: var(--gradient-start);
        color: white;
        border-color: var(--gradient-start);
    }
    
    /* 히어로 섹션 */
    .hero-section {
        margin-bottom: 3rem;
        text-align: center;
    }
    
    .hero-title {
        font-weight: 700;
        font-size: 3rem;
        color: #e0e0e0;
        line-height: 1.2;
        margin-bottom: 1rem;
    }
    
    .hero-description {
        font-size: 1rem;
        color: var(--text-color);
        line-height: 1.6;
        max-width: 450px;
        margin: 0 auto 2rem;
    }
    
    /* 이메일 입력 그룹 */
    .email-input-group {
        display: flex;
        align-items: center;
        background-color: var(--bg-color);
        border-radius: 15px;
        padding: 5px;
        box-shadow: inset -5px -5px 10px var(--light-shadow),
                    inset 5px 5px 10px var(--dark-shadow);
        width: 100%;
        max-width: 450px;
        margin: 0 auto 3rem;
    }
    
    .email-input {
        flex-grow: 1;
        border: none;
        background: transparent;
        padding: 15px 20px;
        color: var(--text-color);
        font-size: 0.9rem;
        outline: none;
    }
    
    .email-input::placeholder {
        color: #8f92b2;
    }
    
    .enter-now-button {
        border: none;
        padding: 15px 30px;
        border-radius: 15px;
        color: white;
        font-size: 0.9rem;
        cursor: pointer;
        background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
        box-shadow: -5px -5px 10px var(--light-shadow),
                    5px 5px 10px var(--dark-shadow);
        transition: transform 0.2s ease;
    }
    
    .enter-now-button:active {
        transform: scale(0.98);
    }
    
    /* 소셜 아이콘 */
    .social-icons {
        display: flex;
        gap: 20px;
        justify-content: center;
    }
    
    .social-link {
        color: var(--text-color);
        font-size: 1.3rem;
        text-decoration: none;
        transition: color 0.3s ease;
    }
    
    .social-link:hover {
        color: var(--gradient-end);
    }
    
    /* 위젯 섹션 */
    .widgets-section {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin-top: 3rem;
    }
    
    /* 뉴모피즘 카드 */
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
    }
    
    /* 음악 플레이어 카드 */
    .music-player-card {
        padding: 30px;
    }
    
    .album-cover {
        width: 150px;
        height: 150px;
        border-radius: 50%;
        background-color: var(--bg-color);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin: 0 auto 25px;
        font-size: 2.5rem;
        color: #a8aacc;
        box-shadow: inset -6px -6px 12px var(--light-shadow),
                    inset 6px 6px 12px var(--dark-shadow);
    }
    
    .player-controls {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 20px;
        margin-bottom: 25px;
    }
    
    .player-btn {
        width: 55px;
        height: 55px;
        border: none;
        border-radius: 50%;
        background-color: var(--bg-color);
        color: var(--text-color);
        font-size: 1.2rem;
        cursor: pointer;
        box-shadow: -6px -6px 12px var(--light-shadow),
                     6px 6px 12px var(--dark-shadow);
        transition: all 0.2s ease;
    }
    
    .player-btn:active {
        box-shadow: inset -6px -6px 12px var(--light-shadow),
                    inset 6px 6px 12px var(--dark-shadow);
    }
    
    .player-btn.play-pause {
        width: 70px;
        height: 70px;
        font-size: 1.5rem;
        background: linear-gradient(145deg, var(--gradient-start), var(--gradient-end));
        color: white;
    }
    
    /* 별점 평가 카드 */
    .rating-card h4 {
        font-size: 1.2rem;
        color: #e0e0e0;
        margin-bottom: 10px;
    }
    
    .star-rating {
        color: var(--star-color);
        font-size: 1.4rem;
        margin-bottom: 15px;
    }
    
    .rating-text {
        font-size: 0.9rem;
        color: var(--text-color);
        line-height: 1.4;
    }
    
    /* 검색 입력 필드 */
    .search-input-group {
        display: flex;
        align-items: center;
        padding: 10px 20px;
        border-radius: 25px;
        box-shadow: inset -6px -6px 12px var(--light-shadow),
                    inset 6px 6px 12px var(--dark-shadow);
    }
    
    .search-icon {
        color: var(--text-color);
        margin-right: 10px;
        font-size: 1.1rem;
    }
    
    .search-input {
        flex-grow: 1;
        border: none;
        background: transparent;
        color: var(--text-color);
        font-size: 1rem;
        outline: none;
    }
    
    .search-input::placeholder {
        color: #8f92b2;
    }
    
    /* 반응형 디자인 */
    @media (max-width: 768px) {
        .hero-title {
            font-size: 2.5rem;
        }
        
        .email-input-group {
            flex-direction: column;
            gap: 10px;
            padding: 10px;
        }
        
        .enter-now-button {
            width: 100%;
        }
        
        .widgets-section {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)


def _render_neumorphism_html():
    """Neumorphism HTML 렌더링"""
    
    # Streamlit 컨테이너 숨기기
    st.markdown('<div style="display: none;">', unsafe_allow_html=True)
    
    # Neumorphism HTML 렌더링
    html = """
    <div class="neumorphism-container" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 9999; background: #2c2f48; overflow-y: auto;">
    <div class="main-container">
        <header class="maic-header">
            <div class="logo-container">
                <span class="logo-text">LEES AI Teacher</span>
            </div>
            <nav class="main-nav">
                <a href="#" class="nav-item">Home</a>
                <a href="#" class="nav-item">Profile</a>
                <a href="#" class="nav-item">About</a>
                <a href="#" class="nav-item">Help</a>
            </nav>
            <button class="signup-button">Sign Up</button>
        </header>

        <main>
            <section class="hero-section">
                <div class="hero-title-container">
                    <h1 class="hero-title">AI 영어 학습의<br>새로운 경험</h1>
                </div>
                <div class="hero-description-container">
                    <p class="hero-description">문법, 독해, 작문을 한 번에! AI가 당신의 영어 실력을 한 단계 업그레이드해드립니다.</p>
                </div>
                <div class="email-input-group">
                    <input type="text" placeholder="질문을 입력하세요..." class="email-input" id="question-input">
                    <button class="enter-now-button" onclick="askQuestion()">질문하기</button>
                </div>
                <div class="social-icons">
                    <a href="#" class="social-link">📚</a>
                    <a href="#" class="social-link">✍️</a>
                    <a href="#" class="social-link">🔍</a>
                    <a href="#" class="social-link">💡</a>
                </div>
            </section>

            <section class="widgets-section">
                <div class="music-player-card neumorphic-card">
                    <div class="album-cover">
                        📖
                        <span>문법 학습</span>
                    </div>
                    <div class="player-controls">
                        <button class="player-btn">⏮️</button>
                        <button class="player-btn play-pause">▶️</button>
                        <button class="player-btn">⏭️</button>
                    </div>
                </div>

                <div class="rating-card neumorphic-card">
                    <h4>학습 평가</h4>
                    <div class="star-rating">
                        ⭐⭐⭐⭐⭐
                    </div>
                    <p class="rating-text">오늘의 학습은 어떠셨나요?</p>
                </div>

                <div class="search-input-group neumorphic-card">
                    <span class="search-icon">🔍</span>
                    <input type="text" placeholder="검색" class="search-input">
                </div>
                
                <div class="neumorphic-card">
                    <h4>학습 모드 선택</h4>
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <button class="player-btn" style="width: 60px; height: 40px; font-size: 0.9rem;">문법</button>
                        <button class="player-btn" style="width: 60px; height: 40px; font-size: 0.9rem;">독해</button>
                        <button class="player-btn" style="width: 60px; height: 40px; font-size: 0.9rem;">작문</button>
                    </div>
                </div>
            </section>
        </main>
    </div>
    
    <script>
    function askQuestion() {
        const input = document.getElementById('question-input');
        const question = input.value.trim();
        if (question) {
            alert('질문: ' + question + '\\n\\nAI가 답변을 준비하고 있습니다...');
            input.value = '';
        }
    }
    
    // Enter 키로 질문하기
    document.getElementById('question-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            askQuestion();
        }
    });
    </script>
    </div>
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)
    
    # Streamlit 컨테이너 닫기
    st.markdown('</div>', unsafe_allow_html=True)
