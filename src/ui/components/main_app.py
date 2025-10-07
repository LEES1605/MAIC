# 메인 앱 UI 컴포넌트
"""
MAIC 앱의 메인 UI를 관리하는 컴포넌트
HTML 컴포넌트와 기존 Streamlit 컴포넌트를 선택적으로 사용
"""

from __future__ import annotations
import streamlit as st
from pathlib import Path


class MainAppComponent:
    """메인 앱 컴포넌트 클래스"""
    
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
        """메인 앱 렌더링"""
        if self._st is None:
            return
        
        # 항상 HTML 앱 사용 (기본값)
        self._render_html_app()
    
    def _render_html_app(self) -> None:
        """고급 CSS 주입으로 앱 렌더링"""
        try:
            # 고급 CSS 주입 시스템 사용
            from .advanced_css_injector import inject_advanced_neumorphism_styles
            inject_advanced_neumorphism_styles()
            
            # 기존 Streamlit 컴포넌트들을 Neumorphism 스타일로 렌더링
            self._render_neumorphism_ui()
            
        except Exception as e:
            self._st.error(f"고급 CSS 주입 실패: {e}")
            self._render_traditional_app()
    
    def _render_neumorphism_ui(self) -> None:
        """Neumorphism 스타일 UI 렌더링"""
        # 네비게이션 바
        self._render_neumorphism_navbar()
        
        # 히어로 섹션
        self._render_neumorphism_hero()
        
        # 모드 선택
        self._render_neumorphism_mode_selector()
        
        # 입력 섹션
        self._render_neumorphism_input_section()
        
        # 채팅 섹션 (선택적)
        if self._st.session_state.get("show_chat", False):
            self._render_neumorphism_chat()
    
    def _render_neumorphism_navbar(self) -> None:
        """Neumorphism 네비게이션 바"""
        col1, col2, col3, col4 = self._st.columns([2, 1, 1, 1])
        
        with col1:
            self._st.markdown("### 🎨 LEES AI Teacher")
        
        with col2:
            if self._st.button("홈", key="nav_home"):
                self._st.session_state["current_page"] = "home"
        
        with col3:
            if self._st.button("학습", key="nav_learn"):
                self._st.session_state["current_page"] = "learn"
        
        with col4:
            if self._st.button("설정", key="nav_settings"):
                self._st.session_state["current_page"] = "settings"
    
    def _render_neumorphism_hero(self) -> None:
        """Neumorphism 히어로 섹션"""
        self._st.markdown("## 🚀 AI 영어 선생님")
        self._st.markdown("개인 맞춤형 영어 학습을 시작하세요")
        
        # 상태 표시
        col1, col2, col3 = self._st.columns([1, 1, 1])
        with col2:
            self._st.markdown("### ✅ 준비완료")
    
    def _render_neumorphism_mode_selector(self) -> None:
        """Neumorphism 모드 선택"""
        self._st.markdown("### 📚 학습 모드를 선택하세요")
        
        col1, col2, col3 = self._st.columns(3)
        
        with col1:
            if self._st.button("📖 문법", key="mode_grammar"):
                self._st.session_state["selected_mode"] = "문법"
                self._st.success("문법 모드가 선택되었습니다.")
        
        with col2:
            if self._st.button("📝 독해", key="mode_reading"):
                self._st.session_state["selected_mode"] = "독해"
                self._st.success("독해 모드가 선택되었습니다.")
        
        with col3:
            if self._st.button("✍️ 작문", key="mode_writing"):
                self._st.session_state["selected_mode"] = "작문"
                self._st.success("작문 모드가 선택되었습니다.")
    
    def _render_neumorphism_input_section(self) -> None:
        """Neumorphism 입력 섹션"""
        self._st.markdown("### 💬 질문을 입력하세요")
        
        question = self._st.text_input(
            "질문",
            placeholder="예: 현재완료시제에 대해 설명해주세요",
            key="question_input"
        )
        
        col1, col2, col3 = self._st.columns([1, 1, 1])
        with col2:
            if self._st.button("🚀 시작하기", key="submit_question"):
                if question:
                    self._st.session_state["show_chat"] = True
                    self._st.session_state["user_question"] = question
                    self._st.success("질문이 제출되었습니다!")
                else:
                    self._st.warning("질문을 입력해주세요.")
    
    def _render_neumorphism_chat(self) -> None:
        """Neumorphism 채팅 섹션"""
        self._st.markdown("### 💭 대화")
        
        # 사용자 질문
        if "user_question" in self._st.session_state:
            self._st.markdown(f"**사용자:** {self._st.session_state['user_question']}")
        
        # AI 응답 시뮬레이션
        selected_mode = self._st.session_state.get("selected_mode", "문법")
        self._st.markdown(f"**AI 선생님:** {selected_mode} 모드로 질문에 답변드리겠습니다...")
    
    def _render_traditional_app(self) -> None:
        """기존 Streamlit 컴포넌트로 앱 렌더링"""
        # 기존 UI 컴포넌트들 사용
        try:
            from ..header_component import HeaderComponent
            from ..chat_panel import _render_chat_panel
            
            # 헤더 렌더링
            header = HeaderComponent()
            header.render()
            
            # 관리자 모드 확인
            if self._is_admin_view():
                self._render_admin_panel()
                return
            
            # 메인 UI 렌더링
            self._render_main_ui()
            
        except Exception as e:
            self._st.error(f"기존 UI 로드 실패: {e}")
            self._render_fallback_ui()
    
    def _is_admin_view(self) -> bool:
        """관리자 모드 확인"""
        if self._st is None:
            return False
        return bool(self._st.session_state.get("admin_mode", False))
    
    def _render_admin_panel(self) -> None:
        """관리자 패널 렌더링"""
        try:
            from ..ops.indexing_panel import AdminIndexingPanel
            panel = AdminIndexingPanel()
            panel.render()
        except Exception as e:
            self._st.error(f"관리자 패널 로드 실패: {e}")
    
    def _render_main_ui(self) -> None:
        """메인 UI 렌더링"""
        # 모드 선택 UI
        self._render_mode_selector()
        
        # 채팅 패널
        try:
            from ..chat_panel import _render_chat_panel
            _render_chat_panel()
        except Exception as e:
            self._st.error(f"채팅 패널 로드 실패: {e}")
    
    def _render_mode_selector(self) -> None:
        """모드 선택 UI 렌더링"""
        self._st.markdown("### 학습 모드를 선택하세요")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("문법", key="grammar_mode"):
                self._st.session_state["selected_mode"] = "문법"
                self._st.success("문법 모드가 선택되었습니다.")
        
        with col2:
            if st.button("독해", key="reading_mode"):
                self._st.session_state["selected_mode"] = "독해"
                self._st.success("독해 모드가 선택되었습니다.")
        
        with col3:
            if st.button("작문", key="writing_mode"):
                self._st.session_state["selected_mode"] = "작문"
                self._st.success("작문 모드가 선택되었습니다.")
    
    def _render_fallback_ui(self) -> None:
        """폴백 UI 렌더링"""
        self._st.title("🎨 MAIC - AI Teacher")
        self._st.markdown("시스템을 초기화하는 중입니다...")
        
        # HTML 앱 토글
        if self._st.button("HTML 앱으로 전환"):
            self._st.session_state["use_html_app"] = True
            self._st.rerun()


def render_main_app() -> None:
    """메인 앱 렌더링 함수"""
    app = MainAppComponent()
    app.render()
