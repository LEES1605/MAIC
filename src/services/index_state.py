"""
MAIC 인덱스 상태 관리 모듈

인덱싱 상태 및 로그 관리를 담당합니다.
"""

import time
from typing import Any, Dict, Optional


class IndexStateManager:
    """인덱스 상태 관리자"""
    
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
    
    def ensure_index_state(self) -> None:
        """인덱스 상태 초기화"""
        if self._st is None:
            return
        
        try:
            if "indexing_steps" not in self._st.session_state:
                self._st.session_state["indexing_steps"] = {}
            if "indexing_logs" not in self._st.session_state:
                self._st.session_state["indexing_logs"] = []
        except Exception:
            pass
    
    def log(self, message: str, level: str = "info") -> None:
        """로그 메시지 추가"""
        if self._st is None:
            return
        
        try:
            logs = self._st.session_state.get("indexing_logs", [])
            logs.append({
                "timestamp": time.time(),
                "message": message,
                "level": level
            })
            # 최대 100개 로그만 유지
            if len(logs) > 100:
                logs = logs[-100:]
            self._st.session_state["indexing_logs"] = logs
        except Exception:
            pass
    
    def step_set(self, step_id: int, status: str, message: str) -> None:
        """인덱싱 단계 상태 설정"""
        if self._st is None:
            return
        
        try:
            steps = self._st.session_state.get("indexing_steps", {})
            steps[step_id] = {
                "status": status,  # "run", "ok", "wait", "err"
                "message": message,
                "timestamp": time.time()
            }
            self._st.session_state["indexing_steps"] = steps
        except Exception:
            pass


# 전역 인스턴스
index_state_manager = IndexStateManager()


# 편의 함수들
def ensure_index_state() -> None:
    """인덱스 상태 초기화"""
    index_state_manager.ensure_index_state()


def log(message: str, level: str = "info") -> None:
    """로그 메시지 추가"""
    index_state_manager.log(message, level)


def step_set(step_id: int, status: str, message: str) -> None:
    """인덱싱 단계 상태 설정"""
    index_state_manager.step_set(step_id, status, message)
