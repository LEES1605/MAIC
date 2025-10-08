"""
데이터 관리 모듈
사용자 데이터, 대화 기록, 설정 저장/로드 담당
"""

import json
import os
import streamlit as st
from typing import Dict, Any, Optional, List
from datetime import datetime
import pickle
import hashlib

class DataManager:
    """데이터 관리 클래스"""
    
    def __init__(self):
        self.data_dir = "data"
        self.conversations_dir = os.path.join(self.data_dir, "conversations")
        self.users_dir = os.path.join(self.data_dir, "users")
        self.settings_dir = os.path.join(self.data_dir, "settings")
        
        self.ensure_directories()
    
    def ensure_directories(self) -> None:
        """필요한 디렉토리 생성"""
        directories = [self.data_dir, self.conversations_dir, self.users_dir, self.settings_dir]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def save_conversation(self, conversation_id: str, conversation_data: Dict[str, Any]) -> bool:
        """
        대화 기록 저장
        
        Args:
            conversation_id (str): 대화 ID
            conversation_data (Dict[str, Any]): 대화 데이터
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            file_path = os.path.join(self.conversations_dir, f"{conversation_id}.json")
            
            # 메타데이터 추가
            conversation_data['metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'conversation_id': conversation_id,
                'message_count': len(conversation_data.get('messages', []))
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            st.error(f"대화 저장 실패: {e}")
            return False
    
    def load_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        대화 기록 로드
        
        Args:
            conversation_id (str): 대화 ID
            
        Returns:
            Optional[Dict[str, Any]]: 대화 데이터
        """
        try:
            file_path = os.path.join(self.conversations_dir, f"{conversation_id}.json")
            
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"대화 로드 실패: {e}")
            return None
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        저장된 대화 목록 반환
        
        Returns:
            List[Dict[str, Any]]: 대화 목록
        """
        conversations = []
        
        try:
            for filename in os.listdir(self.conversations_dir):
                if filename.endswith('.json'):
                    conversation_id = filename[:-5]  # .json 제거
                    conversation_data = self.load_conversation(conversation_id)
                    
                    if conversation_data:
                        conversations.append({
                            'id': conversation_id,
                            'metadata': conversation_data.get('metadata', {}),
                            'message_count': len(conversation_data.get('messages', [])),
                            'created_at': conversation_data.get('metadata', {}).get('saved_at', '')
                        })
            
            # 생성일 기준으로 정렬 (최신순)
            conversations.sort(key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            st.error(f"대화 목록 로드 실패: {e}")
        
        return conversations
    
    def save_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """
        사용자 설정 저장
        
        Args:
            user_id (str): 사용자 ID
            settings (Dict[str, Any]): 설정 데이터
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            file_path = os.path.join(self.users_dir, f"{user_id}.json")
            
            # 메타데이터 추가
            settings['metadata'] = {
                'user_id': user_id,
                'saved_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            st.error(f"사용자 설정 저장 실패: {e}")
            return False
    
    def load_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 설정 로드
        
        Args:
            user_id (str): 사용자 ID
            
        Returns:
            Optional[Dict[str, Any]]: 설정 데이터
        """
        try:
            file_path = os.path.join(self.users_dir, f"{user_id}.json")
            
            if not os.path.exists(file_path):
                return self._get_default_settings()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"사용자 설정 로드 실패: {e}")
            return self._get_default_settings()
    
    def save_global_settings(self, settings: Dict[str, Any]) -> bool:
        """
        전역 설정 저장
        
        Args:
            settings (Dict[str, Any]): 설정 데이터
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            file_path = os.path.join(self.settings_dir, "global.json")
            
            settings['metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            st.error(f"전역 설정 저장 실패: {e}")
            return False
    
    def load_global_settings(self) -> Dict[str, Any]:
        """
        전역 설정 로드
        
        Returns:
            Dict[str, Any]: 설정 데이터
        """
        try:
            file_path = os.path.join(self.settings_dir, "global.json")
            
            if not os.path.exists(file_path):
                return self._get_default_global_settings()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"전역 설정 로드 실패: {e}")
            return self._get_default_global_settings()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """기본 사용자 설정 반환"""
        return {
            'ai_provider': 'openai',
            'user_mode': 'student',
            'theme': 'neumorphism',
            'language': 'ko',
            'auto_save': True,
            'notifications': True,
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'is_default': True
            }
        }
    
    def _get_default_global_settings(self) -> Dict[str, Any]:
        """기본 전역 설정 반환"""
        return {
            'app_version': '1.0.0',
            'maintenance_mode': False,
            'max_conversation_length': 100,
            'session_timeout': 3600,
            'backup_enabled': True,
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'is_default': True
            }
        }
    
    def generate_conversation_id(self) -> str:
        """고유한 대화 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        return f"conv_{timestamp}_{random_suffix}"
    
    def backup_data(self, backup_path: Optional[str] = None) -> bool:
        """
        데이터 백업
        
        Args:
            backup_path (Optional[str]): 백업 경로
            
        Returns:
            bool: 백업 성공 여부
        """
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"backup_{timestamp}.zip"
            
            import zipfile
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.data_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.data_dir)
                        zipf.write(file_path, arcname)
            
            return True
        except Exception as e:
            st.error(f"데이터 백업 실패: {e}")
            return False
    
    def cleanup_old_conversations(self, days: int = 30) -> int:
        """
        오래된 대화 정리
        
        Args:
            days (int): 보관 기간 (일)
            
        Returns:
            int: 삭제된 대화 수
        """
        deleted_count = 0
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        try:
            for filename in os.listdir(self.conversations_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.conversations_dir, filename)
                    
                    if os.path.getmtime(file_path) < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
            
        except Exception as e:
            st.error(f"대화 정리 실패: {e}")
        
        return deleted_count

# 전역 데이터 매니저 인스턴스
data_manager = DataManager()
