# 고급 CSS 주입 시스템
"""
다른 앱들이 사용하는 고급 CSS 우회 기법들을 구현
- data-testid 속성 활용
- CSS 특이성 극대화
- JavaScript + CSS 조합
"""

from __future__ import annotations
import streamlit as st


class AdvancedCSSInjector:
    """고급 CSS 주입 클래스"""
    
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
    
    def inject_neumorphism_styles(self) -> None:
        """Neumorphism 스타일 주입"""
        if self._st is None:
            return
        
        # 1단계: data-testid 기반 CSS (가장 강력)
        self._inject_data_testid_css()
        
        # 2단계: CSS 특이성 극대화
        self._inject_high_specificity_css()
        
        # 3단계: JavaScript 강제 적용
        self._inject_javascript_override()
    
    def _inject_data_testid_css(self) -> None:
        """data-testid 속성 기반 CSS 주입"""
        self._st.markdown("""
        <style>
        /* Streamlit 앱 전체 배경 - data-testid 기반 */
        [data-testid="stApp"] {
            background: 
                radial-gradient(1200px 600px at 20% 20%, #4a148c, transparent 60%),
                radial-gradient(800px 480px at 80% 80%, #1a237e, transparent 55%),
                linear-gradient(135deg, #1a1a2e, #16213e, #0f3460) !important;
            color: #e8eaf6 !important;
            font-family: 'Poppins', sans-serif !important;
            min-height: 100vh !important;
        }
        
        /* 사이드바 완전 숨김 */
        [data-testid="stSidebar"] {
            display: none !important;
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
        
        /* 모든 버튼 스타일 */
        [data-testid="stButton"] > button {
            background: linear-gradient(135deg, #9c27b0, #673ab7) !important;
            color: white !important;
            border: none !important;
            border-radius: 28px !important;
            padding: 12px 24px !important;
            box-shadow: 0 8px 32px rgba(156, 39, 176, 0.4) !important;
            transition: all 0.3s ease !important;
            font-family: 'Poppins', sans-serif !important;
        }
        
        [data-testid="stButton"] > button:hover {
            transform: translateY(-3px) !important;
            box-shadow: 0 12px 40px rgba(156, 39, 176, 0.5) !important;
        }
        
        /* 입력 필드 스타일 */
        [data-testid="stTextInput"] {
            background: rgba(21, 26, 60, 0.4) !important;
            backdrop-filter: blur(15px) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 28px !important;
            box-shadow: 
                inset 0 2px 4px rgba(0, 0, 0, 0.2),
                0 4px 8px rgba(0, 0, 0, 0.1) !important;
        }
        
        [data-testid="stTextInput"] input {
            background: transparent !important;
            color: #e6ebff !important;
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
            color: #e6ebff !important;
        }
        
        h1, h2, h3 {
            color: #f0f4ff !important;
            font-weight: 600 !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def _inject_high_specificity_css(self) -> None:
        """CSS 특이성 극대화"""
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
    
    def _inject_javascript_override(self) -> None:
        """JavaScript 강제 적용"""
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
    
    def inject_fonts(self) -> None:
        """폰트 주입"""
        if self._st is None:
            return
        
        self._st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
        """, unsafe_allow_html=True)


def inject_advanced_neumorphism_styles() -> None:
    """고급 Neumorphism 스타일 주입 함수"""
    injector = AdvancedCSSInjector()
    injector.inject_fonts()
    injector.inject_neumorphism_styles()
