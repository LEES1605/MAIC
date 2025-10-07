"""
MAIC 헤더 컴포넌트 모듈

app.py에서 분리된 헤더 관련 로직을 담당합니다.
- 헤더 렌더링
- 상태 배지 표시
- 관리자 모드 헤더
"""

from pathlib import Path
from typing import Optional

from src.services.indexing_service import _persist_dir_safe


class HeaderComponent:
    """헤더 컴포넌트 클래스"""
    
    def __init__(self):
        self._st = None
        self._initialize_streamlit()
    
    def _initialize_streamlit(self):
        """Streamlit 초기화"""
        try:
            import streamlit as st
            self._st = st
        except ImportError:
            self._st = None
    
    def render(self) -> None:
        """
        H1: 상단 헤더에서 **최신 릴리스 복원 여부**를 3단계(🟩/🟨/🟧)로 항상 표기합니다.
        - 우선 tri-state 배지를 렌더(지연 import, 실패 시 무시)
        - 가능하면 외부 헤더(src.ui.header.render)도 이어서 렌더
        - 외부 헤더가 없을 때만 간단 폴백을 표시
        (H1 규칙은 MASTERPLAN vNext의 합의안을 준수합니다)
        """
        if self._st is None:
            return
        
        # 고급 CSS 주입 시스템 적용
        self._inject_advanced_css()
        
        # Neumorphism 테마 적용
        self._apply_neumorphism_theme()

        # 0) Tri-state readiness chip (관리자 모드에서만 표시)
        try:
            # 관리자 모드일 때만 readiness 헤더 표시
            if self._st.session_state.get("admin_mode", False):
                from src.ui.utils.readiness import render_readiness_header  # type: ignore
                render_readiness_header(compact=True)
        except Exception:
            # 배지 렌더 실패는 치명적이지 않으므로 조용히 계속 진행
            pass
        
        # 1) 기본 헤더 렌더링 (모든 모드에서 표시)
        self._render_neumorphism_header()
        self._render_neumorphism_mode_selector()
    
    def _render_neumorphism_header(self) -> None:
        """Neumorphism 스타일의 헤더 렌더링"""
        if self._st is None:
            return
        
        self._st.markdown("""
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
        
        <script>
        function adminLogin() {
            document.getElementById('adminModal').style.display = 'block';
            document.getElementById('adminPassword').focus();
        }
        </script>
        """, unsafe_allow_html=True)

    def _render_neumorphism_mode_selector(self) -> None:
        """Neumorphism 스타일의 모드 선택 버튼 렌더링"""
        if self._st is None:
            return
        
        # 현재 선택된 모드 가져오기
        current_mode = self._st.session_state.get("__mode", "")
        
        self._st.markdown("""
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

    def _apply_neumorphism_theme(self) -> None:
        """Neumorphism 테마를 Streamlit에 적용"""
        if self._st is None:
            return
        
        self._st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        """, unsafe_allow_html=True)

        self._st.markdown("""
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
        </style>
        """, unsafe_allow_html=True)

    def _render_basic_header(self) -> None:
        """기본 헤더 렌더링"""
        if self._st is None:
            return
        
        # Neumorphism 스타일의 헤더
        self._st.markdown("""
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
        
        <script>
        function adminLogin() {
            alert('관리자 로그인 기능이 준비되었습니다!');
        }
        </script>
        """, unsafe_allow_html=True)
    
    def _inject_advanced_css(self) -> None:
        """고급 CSS 주입 시스템"""
        if self._st is None:
            return
        
        # 1단계: data-testid 기반 CSS (가장 강력)
        self._st.markdown("""
        <style>
        /* Streamlit 앱 전체 배경 - Neumorphism 스타일 */
        [data-testid="stApp"] {
            background: #2c2f48 !important;
            color: #c1c3e0 !important;
            font-family: 'Poppins', sans-serif !important;
            min-height: 100vh !important;
        }
        
        /* 사이드바 완전 숨김 */
        [data-testid="stSidebar"] {
            display: none !important;
        }
        
        /* Neumorphism 헤더 */
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
        
        /* 메인 콘텐츠 영역 */
        [data-testid="stApp"] > div {
            background: transparent !important;
        }
        
        .main .block-container {
            background: transparent !important;
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        
        /* Neumorphism 버튼 스타일 */
        [data-testid="stButton"] > button {
            background: linear-gradient(90deg, #8a63f3, #63b0f3) !important;
            color: white !important;
            border: none !important;
            border-radius: 15px !important;
            padding: 15px 30px !important;
            box-shadow: -5px -5px 10px rgba(255, 255, 255, 0.08),
                        5px 5px 10px rgba(0, 0, 0, 0.3) !important;
            transition: all 0.3s ease !important;
            font-family: 'Poppins', sans-serif !important;
        }
        
        [data-testid="stButton"] > button:hover {
            transform: scale(0.98) !important;
            box-shadow: -3px -3px 6px rgba(255, 255, 255, 0.08),
                        3px 3px 6px rgba(0, 0, 0, 0.3) !important;
        }
        
        /* Neumorphism 입력 필드 스타일 */
        [data-testid="stTextInput"] {
            background: #2c2f48 !important;
            border: none !important;
            border-radius: 15px !important;
            box-shadow: inset -5px -5px 10px rgba(255, 255, 255, 0.08),
                        inset 5px 5px 10px rgba(0, 0, 0, 0.3) !important;
        }
        
        [data-testid="stTextInput"] input {
            background: transparent !important;
            color: #c1c3e0 !important;
            border: none !important;
            padding: 12px 16px !important;
            font-family: 'Poppins', sans-serif !important;
        }
        
        /* 컨테이너 스타일 */
        [data-testid="stContainer"] {
            background: rgba(23, 28, 65, 0.3) !important;
            backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 24px !important;
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
            padding: 20px !important;
            margin: 16px 0 !important;
            transition: all 0.3s ease !important;
        }
        
        [data-testid="stContainer"]:hover {
            background: rgba(23, 28, 65, 0.5) !important;
            transform: translateY(-4px) !important;
            box-shadow: 
                0 12px 40px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
        }
        
        /* 텍스트 색상 */
        h1, h2, h3, h4, h5, h6, p, span, div {
            color: #e8eaf6 !important;
        }
        
        h1, h2, h3 {
            color: #f0f4ff !important;
            font-weight: 600 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 2단계: CSS 특이성 극대화
        self._st.markdown("""
        <style>
        /* CSS 특이성 극대화 - 더 강력한 선택자 */
        html body div[data-testid="stApp"] div[data-testid="stApp"] {
            background: 
                radial-gradient(1200px 600px at 20% 20%, #4a148c, transparent 60%),
                radial-gradient(800px 480px at 80% 80%, #1a237e, transparent 55%),
                linear-gradient(135deg, #1a1a2e, #16213e, #0f3460) !important;
        }
        
        html body div[data-testid="stApp"] .main .block-container {
            background: transparent !important;
        }
        
        html body div[data-testid="stApp"] [data-testid="stButton"] > button {
            background: linear-gradient(135deg, #9c27b0, #673ab7) !important;
            color: white !important;
            border: none !important;
            border-radius: 28px !important;
            box-shadow: 0 8px 32px rgba(156, 39, 176, 0.4) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 3단계: JavaScript 강제 적용
        self._st.markdown("""
        <script>
        // JavaScript로 강제 스타일 적용
        function forceNeumorphismStyles() {
            // Streamlit 앱 요소 찾기
            const stApp = document.querySelector('[data-testid="stApp"]');
            if (stApp) {
                // 배경 강제 적용
                stApp.style.setProperty('background', 
                    'radial-gradient(1200px 600px at 20% 20%, #4a148c, transparent 60%), ' +
                    'radial-gradient(800px 480px at 80% 80%, #1a237e, transparent 55%), ' +
                    'linear-gradient(135deg, #1a1a2e, #16213e, #0f3460)', 'important');
                stApp.style.setProperty('color', '#e8eaf6', 'important');
                stApp.style.setProperty('font-family', "'Poppins', sans-serif", 'important');
                stApp.style.setProperty('min-height', '100vh', 'important');
                
                // 사이드바 숨기기
                const sidebar = document.querySelector('[data-testid="stSidebar"]');
                if (sidebar) {
                    sidebar.style.setProperty('display', 'none', 'important');
                }
                
                // 모든 버튼 스타일 적용
                const buttons = stApp.querySelectorAll('[data-testid="stButton"] > button');
                buttons.forEach(btn => {
                    btn.style.setProperty('background', 'linear-gradient(135deg, #9c27b0, #673ab7)', 'important');
                    btn.style.setProperty('color', 'white', 'important');
                    btn.style.setProperty('border', 'none', 'important');
                    btn.style.setProperty('border-radius', '28px', 'important');
                    btn.style.setProperty('box-shadow', '0 8px 32px rgba(156, 39, 176, 0.4)', 'important');
                    btn.style.setProperty('transition', 'all 0.3s ease', 'important');
                });
                
                console.log('Neumorphism 스타일 강제 적용 완료!');
            }
        }
        
        // 즉시 실행
        forceNeumorphismStyles();
        
        // 페이지 로드 완료 후 실행
        window.addEventListener('load', forceNeumorphismStyles);
        
        // 주기적으로 실행 (Streamlit이 스타일을 재적용할 수 있으므로)
        setInterval(forceNeumorphismStyles, 500);
        
        // DOM 변경 감지
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    setTimeout(forceNeumorphismStyles, 100);
                }
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        </script>
        """, unsafe_allow_html=True)
        
        # 폰트 주입
        self._st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
        """, unsafe_allow_html=True)

        # 1) 외부 헤더가 정의되어 있으면 추가로 렌더
        try:
            from src.ui.header import render as _render_header
            _render_header()
            return
        except Exception:
            # 외부 헤더가 없으면 아래 폴백으로 이어감
            pass

        # 2) 폴백 헤더 (일관성 있는 상태 표시)
        self._render_fallback_header()
    
    def _render_fallback_header(self) -> None:
        """폴백 헤더 렌더링"""
        try:
            p = _persist_dir_safe()
            cj = p / "chunks.jsonl"
            rf = p / ".ready"
            
            # 실제 파일 상태 확인
            chunks_ready = cj.exists() and cj.stat().st_size > 0
            ready_file = rf.exists()
            
            # 세션 상태와 실제 파일 상태 일치 확인
            session_ready = self._st.session_state.get("_INDEX_LOCAL_READY", False)
            
            # 일관성 있는 상태 표시
            if chunks_ready and ready_file:
                badge = "🟢 준비완료"
                status_color = "green"
            elif chunks_ready or ready_file:
                badge = "🟡 부분준비"
                status_color = "orange"
            else:
                badge = "🔴 인덱스없음"
                status_color = "red"
                
            self._st.markdown(f"{badge} **LEES AI Teacher**")
            
            # 관리자 모드에서만 상세 정보 표시
            if self._st.session_state.get("admin_mode", False):
                with self._st.container():
                    self._st.caption("상태 정보")
                    self._st.json({
                        "chunks_ready": chunks_ready,
                        "ready_file": ready_file,
                        "session_ready": session_ready,
                        "persist_dir": str(p)
                    })
        except Exception as e:
            self._st.markdown("🔴 오류 **LEES AI Teacher**")
            if self._st.session_state.get("admin_mode", False):
                self._st.error(f"상태 확인 오류: {e}")
    
    def render_admin_header(self) -> None:
        """관리자 모드 헤더 렌더링"""
        if self._st is None:
            return
        
        try:
            # 관리자 모드 헤더를 맨 위로 이동
            with self._st.container():
                col1, col2 = self._st.columns([3, 1])
                
                with col1:
                    self._st.markdown("### 🔧 관리자 모드")
                
                with col2:
                    if self._st.button("로그아웃", key="admin_logout"):
                        self._st.session_state["admin_mode"] = False
                        self._st.session_state.pop("_admin_ok", None)
                        self._st.rerun()
                
                self._st.divider()
        except Exception as e:
            self._st.error(f"관리자 헤더 렌더링 오류: {e}")


# 전역 인스턴스
header_component = HeaderComponent()


# 편의 함수 (기존 app.py와의 호환성을 위해)
def _header() -> None:
    """헤더 렌더링"""
    header_component.render()
