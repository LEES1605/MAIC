"""
Neumorphism 테마 컴포넌트
기존 MAIC 앱에 Neumorphism 디자인을 적용하는 간단한 테마 시스템
"""

import streamlit as st


def apply_neumorphism_theme():
    """Neumorphism 테마를 Streamlit에 적용"""
    
    # Poppins 폰트 로드
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)
    
    # Neumorphism CSS 적용
    st.markdown("""
    <style>
    /* Neumorphism 배경 */
    [data-testid="stApp"] {
        background: linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%) !important;
        color: #c1c3e0 !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* 사이드바 숨기기 */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Neumorphism 버튼 */
    [data-testid="stButton"] > button {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        border: none !important;
        border-radius: 20px !important;
        color: white !important;
        font-weight: 600 !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stButton"] > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 
            12px 12px 24px rgba(0, 0, 0, 0.4),
            -12px -12px 24px rgba(255, 255, 255, 0.15) !important;
    }
    
    /* Neumorphism 입력 필드 */
    [data-testid="stTextInput"] input {
        background: rgba(44, 47, 72, 0.8) !important;
        border-radius: 20px !important;
        color: #c1c3e0 !important;
        border: none !important;
        box-shadow: 
            inset 8px 8px 16px rgba(0, 0, 0, 0.3),
            inset -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    }
    
    /* Neumorphism 컨테이너 */
    .main .block-container {
        background: transparent !important;
        padding: 20px !important;
    }
    
    /* Neumorphism 카드 */
    [data-testid="stContainer"] {
        background: rgba(44, 47, 72, 0.9) !important;
        border-radius: 20px !important;
        padding: 20px !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
        margin: 10px 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # JavaScript로 강제 적용
    st.markdown("""
    <script>
    // 페이지 로드 후 강제로 Neumorphism 테마 적용
    document.addEventListener('DOMContentLoaded', function() {
        // 배경색 강제 적용
        document.body.style.background = 'linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)';
        document.documentElement.style.background = 'linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)';
        
        // 모든 Streamlit 컨테이너에 배경색 적용
        const containers = document.querySelectorAll('.main .block-container, .stApp, .main');
        containers.forEach(container => {
            container.style.background = 'linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)';
            container.style.color = '#c1c3e0';
        });
        
        // 텍스트 색상 적용
        const textElements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div');
        textElements.forEach(element => {
            if (!element.style.color || element.style.color === 'rgb(0, 0, 0)' || element.style.color === 'black') {
                element.style.color = '#c1c3e0';
            }
        });
    });
    
    // 지연 실행 (Streamlit이 완전히 로드된 후)
    setTimeout(function() {
        document.body.style.background = 'linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)';
        document.documentElement.style.background = 'linear-gradient(135deg, #2c2f48 0%, #1a1d2e 100%)';
    }, 1000);
    </script>
    """, unsafe_allow_html=True)


def render_neumorphism_header():
    """Neumorphism 스타일의 헤더 렌더링"""
    st.markdown("""
    <div class="neumorphic-header">
        <div class="header-content">
            <h1 class="app-title">LEES AI Teacher</h1>
            <div class="header-actions">
                <div class="status-indicator">
                    <span class="status-dot"></span>
                    <span class="status-text">준비완료</span>
                </div>
                <button class="admin-login-btn" onclick="adminLogin()">관리자 로그인</button>
            </div>
        </div>
    </div>
    
    <style>
    .neumorphic-header {
        background: rgba(44, 47, 72, 0.9) !important;
        backdrop-filter: blur(20px) !important;
        border-radius: 20px !important;
        padding: 20px !important;
        margin: 20px !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    }
    
    .header-content {
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
    }
    
    .app-title {
        color: #c1c3e0 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
    }
    
    .header-actions {
        display: flex !important;
        align-items: center !important;
        gap: 20px !important;
    }
    
    .status-indicator {
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    
    .status-dot {
        width: 12px !important;
        height: 12px !important;
        background: #10b981 !important;
        border-radius: 50% !important;
        animation: pulse 2s infinite !important;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .status-text {
        color: #c1c3e0 !important;
        font-weight: 600 !important;
    }
    
    .admin-login-btn {
        background: linear-gradient(90deg, #6366f1, #8b5cf6) !important;
        border: none !important;
        border-radius: 20px !important;
        color: white !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
        transition: all 0.3s ease !important;
    }
    
    .admin-login-btn:hover {
        transform: translateY(-2px) !important;
        box-shadow: 
            12px 12px 24px rgba(0, 0, 0, 0.4),
            -12px -12px 24px rgba(255, 255, 255, 0.15) !important;
    }
    </style>
    
    <!-- 관리자 로그인 모달 -->
    <div id="adminModal" class="modal" style="display: none;">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">관리자 로그인</h3>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>
            <div class="modal-body">
                <input type="password" id="adminPassword" class="modal-input" placeholder="비밀번호를 입력하세요" />
            </div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-primary" onclick="checkPassword()">로그인</button>
                <button class="modal-btn modal-btn-secondary" onclick="closeModal()">취소</button>
            </div>
        </div>
    </div>
    
    <style>
    .modal {
        position: fixed !important;
        z-index: 1000 !important;
        left: 0 !important;
        top: 0 !important;
        width: 100% !important;
        height: 100% !important;
        background-color: rgba(0, 0, 0, 0.5) !important;
        backdrop-filter: blur(10px) !important;
    }
    
    .modal-content {
        background: rgba(44, 47, 72, 0.95) !important;
        margin: 15% auto !important;
        padding: 0 !important;
        border-radius: 20px !important;
        width: 400px !important;
        box-shadow: 
            20px 20px 40px rgba(0, 0, 0, 0.5),
            -20px -20px 40px rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(20px) !important;
    }
    
    .modal-header {
        padding: 20px 20px 10px 20px !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
    }
    
    .modal-title {
        color: #c1c3e0 !important;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
    }
    
    .close {
        color: #c1c3e0 !important;
        font-size: 28px !important;
        font-weight: bold !important;
        cursor: pointer !important;
        transition: color 0.3s ease !important;
    }
    
    .close:hover {
        color: #ff6b6b !important;
    }
    
    .modal-body {
        padding: 20px !important;
    }
    
    .modal-input {
        width: 100% !important;
        padding: 15px !important;
        border: none !important;
        border-radius: 15px !important;
        background: rgba(44, 47, 72, 0.8) !important;
        color: #c1c3e0 !important;
        font-size: 1rem !important;
        box-shadow: 
            inset 8px 8px 16px rgba(0, 0, 0, 0.3),
            inset -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
        outline: none !important;
    }
    
    .modal-input::placeholder {
        color: #8b8b8b !important;
    }
    
    .modal-footer {
        padding: 10px 20px 20px 20px !important;
        display: flex !important;
        gap: 10px !important;
        justify-content: flex-end !important;
    }
    
    .modal-btn {
        padding: 12px 24px !important;
        border: none !important;
        border-radius: 15px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        min-width: 80px !important;
    }
    
    .modal-btn-primary {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        color: white !important;
        box-shadow: 
            8px 8px 16px rgba(99, 102, 241, 0.3),
            -8px -8px 16px rgba(139, 92, 246, 0.1) !important;
    }
    
    .modal-btn-primary:hover {
        transform: translateY(-2px) !important;
        box-shadow: 
            12px 12px 24px rgba(99, 102, 241, 0.4),
            -12px -12px 24px rgba(139, 92, 246, 0.15) !important;
    }
    
    .modal-btn-secondary {
        background: rgba(44, 47, 72, 0.8) !important;
        color: #c1c3e0 !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
    }
    
    .modal-btn-secondary:hover {
        transform: translateY(-2px) !important;
        box-shadow: 
            12px 12px 24px rgba(0, 0, 0, 0.4),
            -12px -12px 24px rgba(255, 255, 255, 0.15) !important;
    }
    </style>
    
    <script>
    function adminLogin() {
        document.getElementById('adminModal').style.display = 'block';
        document.getElementById('adminPassword').focus();
    }
    
    function closeModal() {
        document.getElementById('adminModal').style.display = 'none';
        document.getElementById('adminPassword').value = '';
    }
    
    function checkPassword() {
        const password = document.getElementById('adminPassword').value;
        if (password === 'admin123') {
            alert('관리자 모드로 로그인되었습니다!');
            closeModal();
            // 여기에 관리자 모드 전환 로직 추가
        } else {
            alert('비밀번호가 올바르지 않습니다.');
        }
    }
    
    // 모달 외부 클릭 시 닫기
    window.onclick = function(event) {
        const modal = document.getElementById('adminModal');
        if (event.target === modal) {
            closeModal();
        }
    }
    
    // Enter 키로 로그인
    document.addEventListener('keypress', function(event) {
        if (event.key === 'Enter' && document.getElementById('adminModal').style.display === 'block') {
            checkPassword();
        }
    });
    </script>
    """, unsafe_allow_html=True)


def render_neumorphism_mode_selector():
    """Neumorphism 스타일의 모드 선택 버튼 렌더링"""
    # 현재 선택된 모드 가져오기
    current_mode = st.session_state.get("__mode", "")
    
    st.markdown("""
    <div class="neumorphic-mode-selector">
        <h3 class="mode-title">질문 모드 선택</h3>
        <div class="mode-buttons">
            <button class="mode-btn" id="grammar-btn" onclick="selectMode('grammar')">문법</button>
            <button class="mode-btn" id="reading-btn" onclick="selectMode('reading')">독해</button>
            <button class="mode-btn" id="writing-btn" onclick="selectMode('writing')">작문</button>
        </div>
    </div>
    
    <style>
    .neumorphic-mode-selector {
        background: rgba(44, 47, 72, 0.9) !important;
        backdrop-filter: blur(20px) !important;
        border-radius: 20px !important;
        padding: 20px !important;
        margin: 20px !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
        text-align: center !important;
    }
    
    .mode-title {
        color: #c1c3e0 !important;
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        margin: 0 0 15px 0 !important;
    }
    
    .mode-buttons {
        display: flex !important;
        gap: 15px !important;
        justify-content: center !important;
        flex-wrap: wrap !important;
    }
    
    .mode-btn {
        background: rgba(44, 47, 72, 0.8) !important;
        border: none !important;
        border-radius: 15px !important;
        color: #c1c3e0 !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        box-shadow: 
            8px 8px 16px rgba(0, 0, 0, 0.3),
            -8px -8px 16px rgba(255, 255, 255, 0.1) !important;
        transition: all 0.3s ease !important;
        min-width: 80px !important;
    }
    
    .mode-btn:hover {
        transform: translateY(-2px) !important;
        box-shadow: 
            12px 12px 24px rgba(0, 0, 0, 0.4),
            -12px -12px 24px rgba(255, 255, 255, 0.15) !important;
    }
    
    .mode-btn.active {
        background: linear-gradient(135deg, #818cf8 0%, #a78bfa 100%) !important;
        color: white !important;
        box-shadow: 
            8px 8px 16px rgba(129, 140, 248, 0.4),
            -8px -8px 16px rgba(167, 139, 250, 0.2) !important;
        transform: translateY(-2px) !important;
    }
    </style>
    
    <script>
    function selectMode(mode) {
        // 모든 버튼에서 active 클래스 제거
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // 선택된 버튼에 active 클래스 추가
        document.getElementById(mode + '-btn').classList.add('active');
        
        // Streamlit 세션 상태 업데이트
        console.log('Selected mode:', mode);
        
        // Streamlit에 모드 변경 알림 (실제 구현에서는 서버와 통신)
        // 현재는 시각적 피드백만 제공
    }
    
    // 현재 모드에 따라 버튼 활성화
    document.addEventListener('DOMContentLoaded', function() {
        const currentMode = '""" + current_mode + """';
        if (currentMode) {
            selectMode(currentMode);
        }
    });
    </script>
    """, unsafe_allow_html=True)
