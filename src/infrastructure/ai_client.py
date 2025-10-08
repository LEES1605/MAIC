"""
AI 클라이언트 모듈
OpenAI 및 Google AI 연동 담당
"""

import os
import streamlit as st
from typing import List, Dict, Any, Optional
import openai
import google.generativeai as genai
from datetime import datetime
import json

class AIClient:
    """AI 클라이언트 클래스"""
    
    def __init__(self):
        self.openai_client = None
        self.google_client = None
        self.current_provider = "openai"  # 기본값
        self.initialize_clients()
    
    def initialize_clients(self) -> None:
        """AI 클라이언트 초기화"""
        # OpenAI 클라이언트 초기화
        openai_api_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY')
        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Google AI 클라이언트 초기화
        google_api_key = os.getenv('GOOGLE_API_KEY') or st.secrets.get('GOOGLE_API_KEY')
        if google_api_key:
            genai.configure(api_key=google_api_key)
            self.google_client = genai.GenerativeModel('gemini-pro')
    
    def set_provider(self, provider: str) -> None:
        """
        AI 제공자 설정
        
        Args:
            provider (str): 'openai' 또는 'google'
        """
        if provider in ['openai', 'google']:
            self.current_provider = provider
            st.session_state['ai_provider'] = provider
    
    def get_provider(self) -> str:
        """현재 AI 제공자 반환"""
        return st.session_state.get('ai_provider', self.current_provider)
    
    def generate_response(self, messages: List[Dict[str, str]], user_mode: str = "student") -> str:
        """
        AI 응답 생성
        
        Args:
            messages (List[Dict[str, str]]): 대화 메시지들
            user_mode (str): 사용자 모드 ('student' 또는 'teacher')
            
        Returns:
            str: AI 응답
        """
        provider = self.get_provider()
        
        try:
            if provider == "openai" and self.openai_client:
                return self._generate_openai_response(messages, user_mode)
            elif provider == "google" and self.google_client:
                return self._generate_google_response(messages, user_mode)
            else:
                return "AI 서비스가 설정되지 않았습니다. API 키를 확인해주세요."
        except Exception as e:
            return f"AI 응답 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _generate_openai_response(self, messages: List[Dict[str, str]], user_mode: str) -> str:
        """OpenAI API를 통한 응답 생성"""
        # 시스템 프롬프트 설정
        system_prompt = self._get_system_prompt(user_mode)
        
        # 메시지에 시스템 프롬프트 추가
        formatted_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=formatted_messages,
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    def _generate_google_response(self, messages: List[Dict[str, str]], user_mode: str) -> str:
        """Google AI를 통한 응답 생성"""
        # 시스템 프롬프트 설정
        system_prompt = self._get_system_prompt(user_mode)
        
        # 대화 내용을 하나의 텍스트로 결합
        conversation_text = ""
        for msg in messages:
            role = "학생" if msg["role"] == "user" else "AI 선생님"
            conversation_text += f"{role}: {msg['content']}\n"
        
        # 전체 프롬프트 구성
        full_prompt = f"{system_prompt}\n\n대화 내용:\n{conversation_text}\nAI 선생님:"
        
        response = self.google_client.generate_content(full_prompt)
        return response.text
    
    def _get_system_prompt(self, user_mode: str) -> str:
        """
        사용자 모드에 따른 시스템 프롬프트 반환
        
        Args:
            user_mode (str): 사용자 모드
            
        Returns:
            str: 시스템 프롬프트
        """
        if user_mode == "teacher":
            return """당신은 MAIC(My AI Teacher)의 AI 선생님입니다. 
            선생님 모드에서는 교육자로서 다음 역할을 수행합니다:
            - 학생의 질문에 교육적으로 답변
            - 학습 내용을 체계적으로 설명
            - 예시와 비유를 활용한 설명
            - 학습 동기 부여 및 격려
            - 교육 과정에서의 가이드 역할
            
            항상 친근하고 이해하기 쉽게 설명해주세요."""
        
        else:  # student mode
            return """당신은 MAIC(My AI Teacher)의 AI 선생님입니다. 
            학생 모드에서는 다음 역할을 수행합니다:
            - 학생의 학습을 돕는 개인 튜터
            - 궁금한 것을 자유롭게 질문할 수 있는 환경 제공
            - 학습 내용을 단계별로 설명
            - 실수와 질문을 격려하고 도움
            - 학습 흥미와 동기 유지
            
            항상 친근하고 격려하는 말투로 답변해주세요."""
    
    def get_available_providers(self) -> List[str]:
        """사용 가능한 AI 제공자 목록 반환"""
        providers = []
        
        if self.openai_client:
            providers.append("openai")
        
        if self.google_client:
            providers.append("google")
        
        return providers
    
    def test_connection(self, provider: str) -> Dict[str, Any]:
        """
        AI 제공자 연결 테스트
        
        Args:
            provider (str): 테스트할 제공자
            
        Returns:
            Dict[str, Any]: 테스트 결과
        """
        test_message = [{"role": "user", "content": "안녕하세요! 테스트 메시지입니다."}]
        
        try:
            start_time = datetime.now()
            response = self.generate_response(test_message)
            end_time = datetime.now()
            
            return {
                "success": True,
                "provider": provider,
                "response": response,
                "response_time": (end_time - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "provider": provider,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# 전역 AI 클라이언트 인스턴스
ai_client = AIClient()
