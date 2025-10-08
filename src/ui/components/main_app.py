# 메인 앱 UI 컴포넌트
"""
MAIC 앱의 메인 UI를 관리하는 컴포넌트
HTML 컴포넌트와 기존 Streamlit 컴포넌트를 선택적으로 사용
"""

from __future__ import annotations
import streamlit as st
from pathlib import Path
import sys
import os

# 상위 디렉토리 경로 추가 (application, infrastructure 모듈 접근용)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 기존 구현된 서비스들 임포트
try:
    from application.auth_service import AuthService
    from application.chat_service import ChatService
    from infrastructure.ai_client import AIClient
    from infrastructure.data_manager import DataManager
    
    # 서비스 인스턴스 생성
    auth_service = AuthService()
    chat_service = ChatService()
    ai_client = AIClient()
    data_manager = DataManager()
    SERVICES_AVAILABLE = True
except ImportError as e:
    SERVICES_AVAILABLE = False
    # st가 아직 초기화되지 않았을 수 있음
    pass


class MainAppComponent:
    """메인 앱 컴포넌트 클래스"""
    
    def __init__(self):
        self._st = None
        self._initialize_streamlit()
    
    def _initialize_streamlit(self) -> None:
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
        
        # 서비스가 사용 가능한 경우 인증 체크
        if SERVICES_AVAILABLE and auth_service:
            if not auth_service.is_authenticated():
                self._render_login_interface()
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
        
        # 서비스가 사용 가능한 경우 채팅 인터페이스 렌더링
        if SERVICES_AVAILABLE and auth_service and auth_service.is_authenticated():
            self._render_chat_interface()
            return
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


    def _render_login_interface(self) -> None:
        """로그인 인터페이스 렌더링"""
        self._st.title("🎓 MAIC - My AI Teacher")
        self._st.markdown("### 로그인이 필요합니다")
        
        if not SERVICES_AVAILABLE or not auth_service:
            self._st.warning("인증 서비스가 사용할 수 없습니다. 기본 모드로 진행합니다.")
            self._render_html_app()
            return
        
        password = self._st.text_input("관리자 비밀번호:", type="password", key="login_password")
        
        col1, col2 = self._st.columns([1, 4])
        
        with col1:
            if self._st.button("로그인", key="login_button"):
                if auth_service.login(password):
                    self._st.success("로그인 성공!")
                    self._st.rerun()
                else:
                    self._st.error("비밀번호가 올바르지 않습니다.")
        
        with col2:
            if self._st.button("학생 모드로 시작", key="student_login"):
                auth_service.login("student_mode")
                auth_service.set_mode("student")
                self._st.success("학생 모드로 시작합니다!")
                self._st.rerun()
        
        # HTML UI 표시 (로그인 전)
        self._render_html_app()
    
    def _render_chat_interface(self) -> None:
        """채팅 인터페이스 렌더링"""
        if not SERVICES_AVAILABLE or not auth_service:
            self._st.warning("서비스가 사용할 수 없습니다. 기본 UI로 전환합니다.")
            self._render_html_app()
            return
        
        # 헤더
        col1, col2 = self._st.columns([4, 1])
        with col1:
            self._st.title("🎓 MAIC - AI Teacher")
        with col2:
            if self._st.button("로그아웃", key="logout_button"):
                auth_service.logout()
                self._st.rerun()
        
        # 모드 표시
        current_mode = auth_service.get_mode()
        self._st.info(f"현재 모드: {current_mode}")
        
        # 채팅 영역
        self._st.markdown("### 💬 AI와 대화하기")
        
        # 채팅 히스토리
        messages = chat_service.get_messages()
        for message in messages:
            if message["role"] == "user":
                self._st.markdown(f"**나**: {message['content']}")
            else:
                self._st.markdown(f"**AI**: {message['content']}")
        
        # 메시지 입력
        user_input = self._st.text_input("메시지를 입력하세요:", key="chat_input")
        
        if self._st.button("전송", key="send_message"):
            if user_input:
                # 사용자 메시지 추가
                chat_service.add_message("user", user_input)
                
                # AI 응답 생성
                response = ai_client.generate_response(user_input, current_mode)
                chat_service.add_message("assistant", response)
                
                # 데이터 저장
                data_manager.save_conversation()
                
                self._st.rerun()
        
        # 관리자 패널
        if current_mode == "admin":
            self._render_admin_panel()
    
    def _render_admin_panel(self) -> None:
        """관리자 패널 렌더링"""
        if not SERVICES_AVAILABLE or not auth_service or not chat_service:
            self._st.warning("관리자 패널 서비스가 사용할 수 없습니다.")
            return
        
        self._st.markdown("### 🔧 관리자 패널")
        
        tab1, tab2, tab3 = self._st.tabs(["대화 관리", "시스템 설정", "데이터 관리"])
        
        with tab1:
            if self._st.button("대화 내역 초기화"):
                chat_service.clear_conversation()
                self._st.success("대화 내역이 초기화되었습니다.")
            
            if self._st.button("대화 내역 내보내기"):
                export_data = chat_service.export_conversation()
                self._st.download_button(
                    label="대화 내역 다운로드",
                    data=export_data,
                    file_name="conversation.json",
                    mime="application/json"
                )
        
        with tab2:
            new_mode = self._st.selectbox(
                "모드 변경:",
                ["student", "admin"],
                index=0 if auth_service.get_mode() == "student" else 1
            )
            
            if self._st.button("모드 변경"):
                auth_service.set_mode(new_mode)
                self._st.success(f"모드가 {new_mode}로 변경되었습니다.")
        
        with tab3:
            if self._st.button("데이터 정리"):
                data_manager.cleanup_old_data()
                self._st.success("오래된 데이터가 정리되었습니다.")


def render_main_app() -> None:
    """메인 앱 렌더링 함수"""
    app = MainAppComponent()
    app.render()
