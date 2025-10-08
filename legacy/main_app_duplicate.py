"""
MAIC 메인 애플리케이션 UI
실제 애플리케이션 로직을 담당하는 모듈
"""

import streamlit as st
import streamlit.components.v1 as components
import os

# 서비스 임포트
from application.auth_service import auth_service
from application.chat_service import chat_service
from infrastructure.ai_client import ai_client
from infrastructure.data_manager import data_manager

def handle_login(password: str) -> bool:
    """로그인 처리"""
    return auth_service.login(password)

def handle_logout():
    """로그아웃 처리"""
    auth_service.logout()
    chat_service.clear_conversation()

def handle_chat_message(message: str, user_mode: str) -> str:
    """채팅 메시지 처리"""
    # 사용자 메시지 추가
    chat_service.add_message("user", message)
    
    # AI 응답 생성
    conversation = chat_service.get_conversation_for_ai()
    ai_response = ai_client.generate_response(conversation, user_mode)
    
    # AI 응답 추가
    chat_service.add_message("assistant", ai_response)
    
    return ai_response

def render_chat_interface():
    """채팅 인터페이스 렌더링"""
    st.title("💬 MAIC 채팅")
    
    # 현재 모드 표시
    current_mode = auth_service.get_current_mode()
    mode_display = "선생님 모드" if current_mode == "teacher" else "학생 모드"
    st.info(f"현재 모드: {mode_display}")
    
    # 채팅 입력
    user_input = st.text_input("메시지를 입력하세요:", key="chat_input")
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("전송", key="send_button"):
            if user_input.strip():
                # AI 응답 생성
                response = handle_chat_message(user_input, current_mode or "student")
                
                # 입력창 초기화
                st.session_state.chat_input = ""
                st.rerun()
    
    with col2:
        if st.button("대화 초기화", key="clear_button"):
            chat_service.clear_conversation()
            st.rerun()
    
    # 채팅 기록 표시
    st.subheader("💭 대화 기록")
    conversation = chat_service.get_conversation()
    
    if conversation:
        for msg in conversation[-10:]:  # 최근 10개 메시지만 표시
            if msg.role == "user":
                st.markdown(f"**👤 사용자:** {msg.content}")
            else:
                st.markdown(f"**🤖 AI 선생님:** {msg.content}")
            st.markdown("---")
    else:
        st.info("아직 대화가 없습니다. 위에서 메시지를 입력해보세요!")

def render_admin_panel():
    """관리자 패널 렌더링"""
    st.title("⚙️ 관리자 패널")
    
    # AI 설정
    st.subheader("🤖 AI 설정")
    
    # AI 제공자 선택
    available_providers = ai_client.get_available_providers()
    if available_providers:
        current_provider = ai_client.get_provider()
        selected_provider = st.selectbox(
            "AI 제공자 선택:",
            available_providers,
            index=available_providers.index(current_provider) if current_provider in available_providers else 0
        )
        
        if selected_provider != current_provider:
            ai_client.set_provider(selected_provider)
            st.success(f"AI 제공자가 {selected_provider}로 변경되었습니다.")
        
        # 연결 테스트
        if st.button("AI 연결 테스트"):
            with st.spinner("AI 연결 테스트 중..."):
                test_result = ai_client.test_connection(selected_provider)
                
                if test_result["success"]:
                    st.success(f"✅ {selected_provider} 연결 성공!")
                    st.write(f"응답 시간: {test_result['response_time']:.2f}초")
                    st.write(f"테스트 응답: {test_result['response']}")
                else:
                    st.error(f"❌ {selected_provider} 연결 실패: {test_result['error']}")
    else:
        st.warning("⚠️ 사용 가능한 AI 제공자가 없습니다. API 키를 설정해주세요.")
    
    # 모드 설정
    st.subheader("📚 모드 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("선생님 모드", key="teacher_mode"):
            auth_service.set_mode("teacher")
            st.success("선생님 모드로 변경되었습니다.")
            st.rerun()
    
    with col2:
        if st.button("학생 모드", key="student_mode"):
            auth_service.set_mode("student")
            st.success("학생 모드로 변경되었습니다.")
            st.rerun()
    
    # 데이터 관리
    st.subheader("💾 데이터 관리")
    
    # 대화 내보내기
    if st.button("대화 내보내기"):
        conversation_data = chat_service.export_conversation()
        conversation_id = data_manager.generate_conversation_id()
        success = data_manager.save_conversation(conversation_id, conversation_data)
        
        if success:
            st.success(f"대화가 저장되었습니다. ID: {conversation_id}")
        else:
            st.error("대화 저장에 실패했습니다.")
    
    # 저장된 대화 목록
    conversations = data_manager.list_conversations()
    if conversations:
        st.write("**저장된 대화 목록:**")
        for conv in conversations[:5]:  # 최근 5개만 표시
            st.write(f"- {conv['id']} ({conv['message_count']}개 메시지)")
    
    # 데이터 정리
    if st.button("오래된 대화 정리 (30일 이상)"):
        deleted_count = data_manager.cleanup_old_conversations(30)
        st.success(f"{deleted_count}개의 오래된 대화가 정리되었습니다.")

def render_html_ui(height: int = 400):
    """HTML UI 렌더링"""
    html_file_path = "src/ui/neumorphism_app.html"
    if os.path.exists(html_file_path):
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        components.html(html_content, height=height, scrolling=True)

def render_main_app():
    """메인 애플리케이션 렌더링"""
    # 인증 상태 확인
    if not auth_service.is_authenticated():
        # 로그인 페이지
        st.title("🎓 MAIC - My AI Teacher")
        st.markdown("### 로그인이 필요합니다")
        
        password = st.text_input("관리자 비밀번호:", type="password", key="login_password")
        
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if st.button("로그인", key="login_button"):
                if handle_login(password):
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
        
        with col2:
            if st.button("학생 모드로 시작", key="student_login"):
                auth_service.login("student_mode")  # 학생 모드는 비밀번호 없이
                auth_service.set_mode("student")
                st.success("학생 모드로 시작합니다!")
                st.rerun()
        
        # HTML UI 표시 (로그인 전)
        render_html_ui(height=600)
    
    else:
        # 인증된 사용자 - 메인 인터페이스
        # 사이드바에 로그아웃 버튼
        with st.sidebar:
            st.markdown("### 👤 사용자 정보")
            session_info = auth_service.get_session_info()
            st.write(f"역할: {session_info['user_role']}")
            st.write(f"모드: {session_info.get('current_mode', '미설정')}")
            
            if st.button("로그아웃", key="logout_button"):
                handle_logout()
                st.success("로그아웃되었습니다.")
                st.rerun()
        
        # 메인 컨텐츠
        current_mode = auth_service.get_current_mode()
        
        if current_mode == "teacher":
            # 관리자 패널
            render_admin_panel()
        else:
            # 채팅 인터페이스
            render_chat_interface()
        
        # HTML UI도 함께 표시 (백그라운드)
        render_html_ui(height=400)
