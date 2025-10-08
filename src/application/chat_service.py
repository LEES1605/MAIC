"""
채팅 서비스 모듈
메시지 처리 및 대화 관리 담당
"""

import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

class ChatMessage:
    """채팅 메시지 클래스"""
    
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
        self.role = role  # 'user' 또는 'assistant'
        self.content = content
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """딕셔너리에서 객체 생성"""
        return cls(
            role=data['role'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )

class ChatService:
    """채팅 서비스 클래스"""
    
    def __init__(self):
        self.conversation_key = 'chat_conversation'
        self.initialize_conversation()
    
    def initialize_conversation(self) -> None:
        """대화 초기화"""
        if self.conversation_key not in st.session_state:
            st.session_state[self.conversation_key] = []
    
    def add_message(self, role: str, content: str) -> None:
        """
        메시지 추가
        
        Args:
            role (str): 메시지 역할 ('user' 또는 'assistant')
            content (str): 메시지 내용
        """
        message = ChatMessage(role, content)
        st.session_state[self.conversation_key].append(message)
    
    def get_conversation(self) -> List[ChatMessage]:
        """
        대화 기록 반환
        
        Returns:
            List[ChatMessage]: 대화 기록
        """
        conversation_data = st.session_state.get(self.conversation_key, [])
        return [ChatMessage.from_dict(msg) if isinstance(msg, dict) else msg for msg in conversation_data]
    
    def clear_conversation(self) -> None:
        """대화 기록 초기화"""
        st.session_state[self.conversation_key] = []
    
    def get_conversation_for_ai(self) -> List[Dict[str, str]]:
        """
        AI API용 대화 형식으로 변환
        
        Returns:
            List[Dict[str, str]]: AI API용 대화 형식
        """
        conversation = self.get_conversation()
        return [{'role': msg.role, 'content': msg.content} for msg in conversation]
    
    def get_last_messages(self, count: int = 10) -> List[ChatMessage]:
        """
        최근 메시지들 반환
        
        Args:
            count (int): 반환할 메시지 수
            
        Returns:
            List[ChatMessage]: 최근 메시지들
        """
        conversation = self.get_conversation()
        return conversation[-count:] if len(conversation) > count else conversation
    
    def format_conversation_for_display(self) -> str:
        """
        대화를 표시용 형식으로 변환
        
        Returns:
            str: 표시용 대화 내용
        """
        conversation = self.get_conversation()
        formatted = []
        
        for msg in conversation:
            timestamp = msg.timestamp.strftime("%H:%M")
            role_display = "사용자" if msg.role == "user" else "AI 선생님"
            formatted.append(f"[{timestamp}] {role_display}: {msg.content}")
        
        return "\n\n".join(formatted)
    
    def export_conversation(self) -> Dict[str, Any]:
        """
        대화 내보내기
        
        Returns:
            Dict[str, Any]: 대화 데이터
        """
        conversation = self.get_conversation()
        return {
            'conversation': [msg.to_dict() for msg in conversation],
            'export_time': datetime.now().isoformat(),
            'message_count': len(conversation)
        }
    
    def import_conversation(self, data: Dict[str, Any]) -> bool:
        """
        대화 가져오기
        
        Args:
            data (Dict[str, Any]): 가져올 대화 데이터
            
        Returns:
            bool: 성공 여부
        """
        try:
            conversation_data = data.get('conversation', [])
            messages = [ChatMessage.from_dict(msg) for msg in conversation_data]
            st.session_state[self.conversation_key] = messages
            return True
        except Exception as e:
            st.error(f"대화 가져오기 실패: {e}")
            return False

# 전역 채팅 서비스 인스턴스
chat_service = ChatService()
