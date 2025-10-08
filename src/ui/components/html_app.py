# HTML 컴포넌트 기반 MAIC 앱
"""
HTML 컴포넌트를 사용한 완전한 MAIC 앱 UI
Streamlit의 CSS 제약을 우회하여 완전한 Neumorphism 디자인 구현
"""

from __future__ import annotations
import streamlit as st
from pathlib import Path
import json
import sys

# src 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.application.auth_service import auth_service


def render_html_app() -> None:
    """(Deprecated) 기존 경로는 사용하지 않고 정본 UI만 렌더링"""
    render_neumorphism_html_file()


def _render_fallback_ui() -> None:
    """HTML 컴포넌트 실패 시 폴백 UI"""
    st.title("🎨 MAIC - AI Teacher")
    st.markdown("HTML 컴포넌트를 로드할 수 없습니다. 기본 UI를 표시합니다.")
    
    # 기본 기능들
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 문법")
        if st.button("문법 학습 시작", key="grammar"):
            st.info("문법 모드로 전환되었습니다.")
    
    with col2:
        st.markdown("### 독해")
        if st.button("독해 학습 시작", key="reading"):
            st.info("독해 모드로 전환되었습니다.")
    
    with col3:
        st.markdown("### 작문")
        if st.button("작문 학습 시작", key="writing"):
            st.info("작문 모드로 전환되었습니다.")
    
    # 질문 입력
    question = st.text_input("질문을 입력하세요:", placeholder="예: 현재완료시제에 대해 설명해주세요")
    if st.button("질문 제출"):
        if question:
            st.success(f"질문이 제출되었습니다: {question}")
        else:
            st.warning("질문을 입력해주세요.")


def handle_auth_callback(action: str, data: dict) -> dict:
    """인증 관련 콜백 처리"""
    try:
        if action == "check_password":
            password = data.get("password", "")
            success = auth_service.login(password)
            
            if success:
                return {
                    "success": True,
                    "message": "관리자 모드로 진입했습니다!",
                    "session_info": auth_service.get_session_info()
                }
            else:
                return {
                    "success": False,
                    "message": "비밀번호가 틀렸습니다!"
                }
        
        elif action == "logout":
            auth_service.logout()
            return {
                "success": True,
                "message": "로그아웃되었습니다.",
                "session_info": auth_service.get_session_info()
            }
        
        elif action == "get_session":
            return {
                "success": True,
                "session_info": auth_service.get_session_info()
            }
        
        else:
            return {
                "success": False,
                "message": f"알 수 없는 액션: {action}"
            }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"오류 발생: {str(e)}"
        }


def render_neumorphism_html_file() -> None:
    """src/ui/neumorphism_app.html 파일을 렌더링 (기존 UI와 연결)"""
    # html 파일 경로를 모듈 상대경로로 안전하게 계산
    html_file = (Path(__file__).parent.parent / "neumorphism_app.html").resolve()

    if not html_file.exists():
        st.error(f"UI 파일을 찾을 수 없습니다: {html_file}")
        return

    try:
        html_content = html_file.read_text(encoding="utf-8")
        
        # 현재 인증 상태 확인
        is_authenticated = st.session_state.get('authenticated', False)
        
        # HTML UI의 JavaScript 함수들을 Python 백엔드와 연결
        auth_script = f"""
        <script>
        // Python에서 전달된 인증 상태
        window.isAuthenticated = {str(is_authenticated).lower()};
        
        // 기존 HTML UI의 관리자 로그인 함수를 Python 백엔드와 연결
        document.addEventListener('DOMContentLoaded', function() {{
            // 관리자 로그인 버튼 연결
            const adminBtn = document.getElementById('admin-login-btn');
            if (adminBtn) {{
                adminBtn.onclick = function() {{
                    if (window.isAuthenticated) {{
                        // 로그아웃 처리
                        const currentUrl = new URL(window.location);
                        currentUrl.searchParams.set('auth_action', 'logout');
                        window.location.href = currentUrl.toString();
                    }} else {{
                        // 기존 로그인 모달 표시
                        const modal = document.getElementById('passwordModal');
                        if (modal) {{
                            modal.style.display = 'block';
                            document.getElementById('adminPassword').focus();
                        }}
                    }}
                }};
            }}
            
            // 기존 checkPassword 함수를 Python 백엔드와 연결
            const originalCheckPassword = window.checkPassword;
            window.checkPassword = function() {{
                const password = document.getElementById('adminPassword').value;
                
                if (!password) {{
                    alert('비밀번호를 입력해주세요!');
                    return;
                }}
                
                // URL 파라미터로 로그인 처리
                const currentUrl = new URL(window.location);
                currentUrl.searchParams.set('auth_action', 'login');
                currentUrl.searchParams.set('password', password);
                window.location.href = currentUrl.toString();
            }};
            
            // 로그인 상태에 따른 UI 업데이트
            console.log('인증 상태 확인:', window.isAuthenticated);
            if (window.isAuthenticated) {{
                console.log('관리자 모드로 전환 시작');
                // 즉시 관리자 모드로 변경
                setTimeout(function() {{
                    console.log('showAdminMode 함수 호출 시도');
                    // 기존 showAdminMode 함수 호출
                    if (typeof showAdminMode === 'function') {{
                        console.log('showAdminMode 함수 발견, 호출 중...');
                        showAdminMode();
                        console.log('showAdminMode 함수 호출 완료');
                    }} else {{
                        console.error('showAdminMode 함수를 찾을 수 없습니다');
                        // 수동으로 관리자 모드 UI 변경
                        const title = document.querySelector('.title');
                        if (title) {{
                            title.innerHTML = 'LEES 관리자패널';
                            console.log('제목 변경 완료');
                        }}
                        
                        const statusText = document.querySelector('.status-text');
                        if (statusText) {{
                            statusText.textContent = '관리자 모드';
                            console.log('상태 텍스트 변경 완료');
                        }}
                    }}
                    
                    // 관리자 버튼 텍스트 변경
                    if (adminBtn) {{
                        adminBtn.textContent = '🚪';
                        adminBtn.title = '관리자 로그아웃';
                        console.log('관리자 버튼 변경 완료');
                    }}
                    
                    // 로그인 버튼 숨기기
                    const studentLoginBtn = document.querySelector('.student-login-btn');
                    if (studentLoginBtn) {{
                        studentLoginBtn.style.display = 'none';
                        console.log('학생 로그인 버튼 숨김 완료');
                    }}
                    
                    console.log('관리자 모드 전환 완료');
                }}, 200);
            }} else {{
                console.log('일반 사용자 모드');
            }}
        }});
        </script>
        """
        
        # Streamlit 사이드바 완전 숨기기 CSS 추가
        sidebar_css = """
        <style>
        /* Streamlit 사이드바 완전 숨기기 - 더 강력한 선택자 */
        section[data-testid="stSidebar"],
        .css-1d391kg, 
        .css-1cypcdb, 
        .css-1v3fvcr,
        [data-testid="stSidebar"],
        .sidebar .sidebar-content {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            min-width: 0 !important;
        }
        
        /* 메인 컨테이너 전체 너비 사용 */
        .main .block-container {
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
            padding-bottom: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        
        /* 앱 전체 패딩 제거 */
        .stApp > div {
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        
        /* 메인 영역 전체 너비 */
        .main {
            flex: 1 !important;
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* 스크롤바 숨기기 */
        ::-webkit-scrollbar {
            display: none;
        }
        
        /* 전체 페이지 스타일 */
        .stApp {
            background: transparent !important;
        }
        
        /* iframe 컨테이너 전체 너비 */
        .stApp > div > div > div > div {
            width: 100% !important;
            max-width: 100% !important;
        }
        </style>
        """
        
        # HTML에 사이드바 숨기기 CSS와 인증 스크립트 추가
        html_content = html_content.replace('</head>', sidebar_css + '</head>')
        html_content = html_content.replace('</body>', auth_script + '</body>')
        
        # HTML UI 렌더링
        st.components.v1.html(html_content, height=1000)
        
        # URL 파라미터 기반 인증 처리 (안전한 방법)
        if st.query_params.get('auth_action') == 'login':
            # 로그인 처리
            password = st.query_params.get('password', '')
            if password == 'admin123':  # 임시로 하드코딩, 나중에 AuthService 사용
                st.session_state['authenticated'] = True
                st.session_state['user_role'] = 'admin'
                st.success("관리자 로그인 성공!")
                # URL 파라미터 제거
                st.query_params.clear()
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다!")
                st.query_params.clear()
                st.rerun()
        
        elif st.query_params.get('auth_action') == 'logout':
            # 로그아웃 처리
            st.session_state['authenticated'] = False
            st.session_state.pop('user_role', None)
            st.success("로그아웃되었습니다!")
            st.query_params.clear()
            st.rerun()
    
    except Exception as e:
        st.error(f"HTML 로드 실패: {e}")
