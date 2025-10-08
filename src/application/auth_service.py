"""
인증 서비스 모듈
관리자 로그인 및 세션 관리 담당
"""

import streamlit as st
from typing import Dict, Any, Optional
import hashlib
import time

class AuthService:
    """인증 서비스 클래스"""
    
    def __init__(self):
        self.admin_password = "admin123"
        self.session_timeout = 3600  # 1시간
    
    def login(self, password: str) -> bool:
        """
        관리자 로그인 처리
        
        Args:
            password (str): 입력된 비밀번호
            
        Returns:
            bool: 로그인 성공 여부
        """
        if password == self.admin_password:
            # 로그인 성공 시 세션 정보 저장
            st.session_state['authenticated'] = True
            st.session_state['login_time'] = time.time()
            st.session_state['user_role'] = 'admin'
            return True
        return False
    
    def logout(self) -> None:
        """로그아웃 처리"""
        # 세션 정보 초기화
        st.session_state['authenticated'] = False
        st.session_state.pop('login_time', None)
        st.session_state.pop('user_role', None)
        st.session_state.pop('current_mode', None)
    
    def is_authenticated(self) -> bool:
        """
        인증 상태 확인
        
        Returns:
            bool: 인증된 사용자 여부
        """
        # st.session_state.get 대신 직접 접근
        if 'authenticated' not in st.session_state or not st.session_state['authenticated']:
            return False
        
        # 세션 타임아웃 확인
        if 'login_time' in st.session_state:
            login_time = st.session_state['login_time']
            if time.time() - login_time > self.session_timeout:
                self.logout()
                return False
        
        return True
    
    def get_user_role(self) -> Optional[str]:
        """
        사용자 역할 반환
        
        Returns:
            Optional[str]: 사용자 역할 (admin, student, None)
        """
        if not self.is_authenticated():
            return None
        return st.session_state['user_role'] if 'user_role' in st.session_state else None
    
    def set_mode(self, mode: str) -> None:
        """
        사용 모드 설정
        
        Args:
            mode (str): 모드 (teacher, student)
        """
        if self.is_authenticated():
            st.session_state['current_mode'] = mode
    
    def get_current_mode(self) -> Optional[str]:
        """
        현재 모드 반환
        
        Returns:
            Optional[str]: 현재 모드 (teacher, student, None)
        """
        if not self.is_authenticated():
            return None
        return st.session_state['current_mode'] if 'current_mode' in st.session_state else None
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        세션 정보 반환
        
        Returns:
            Dict[str, Any]: 세션 정보
        """
        login_time = st.session_state['login_time'] if 'login_time' in st.session_state else 0
        
        return {
            'authenticated': self.is_authenticated(),
            'user_role': self.get_user_role(),
            'current_mode': self.get_current_mode(),
            'login_time': login_time,
            'session_duration': time.time() - login_time if self.is_authenticated() else 0
        }

# 전역 인증 서비스 인스턴스
auth_service = AuthService()
