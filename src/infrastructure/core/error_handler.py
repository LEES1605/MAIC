# ============== [01] imports & docstring — START ==============
"""
ErrorHandler - 통합 에러 처리 클래스 (SSOT)

이 클래스는 프로젝트 전체에서 사용되는 모든 에러 처리 로직을 통합하여
Single Source of Truth (SSOT)를 제공합니다.

주요 기능:
- 에러 로깅 및 추적
- 에러 메시지 포맷팅
- 에러 레벨 관리 (info, warn, error, critical)
- 에러 누적 및 세션 상태 관리
- 에러 통계 및 분석
- 에러 복구 제안

에러 레벨:
- INFO: 일반적인 정보성 메시지
- WARN: 경고성 메시지 (기능은 정상 작동)
- ERROR: 에러 메시지 (기능 일부 실패)
- CRITICAL: 치명적 에러 (앱 전체 실패)
"""
from __future__ import annotations

import traceback
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field

try:
    import streamlit as st
except Exception:  # noqa: BLE001
    st = None  # Streamlit 없는 환경(예: CI) 대비

__all__ = ["ErrorHandler", "ErrorLevel", "ErrorEntry", "get_error_handler"]

# ============== [01] imports & docstring — END ==============


# ============== [02] 에러 레벨 및 데이터 클래스 — START ==============
class ErrorLevel(Enum):
    """에러 레벨 열거형"""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorEntry:
    """에러 엔트리 데이터 클래스"""
    timestamp: datetime
    level: ErrorLevel
    message: str
    source: str
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
            "traceback": self.traceback,
            "context": self.context,
            "user_id": self.user_id,
            "session_id": self.session_id
        }
    
    def to_string(self) -> str:
        """문자열로 변환 (로그용)"""
        level_icon = {
            ErrorLevel.INFO: "[INFO]",
            ErrorLevel.WARN: "[WARN]",
            ErrorLevel.ERROR: "[ERROR]",
            ErrorLevel.CRITICAL: "[CRITICAL]"
        }
        
        icon = level_icon.get(self.level, "[UNKNOWN]")
        timestamp_str = self.timestamp.strftime("%H:%M:%S")
        
        if self.traceback:
            return f"[{timestamp_str}] {icon} {self.source}: {self.message}\n{self.traceback}"
        else:
            return f"[{timestamp_str}] {icon} {self.source}: {self.message}"

# ============== [02] 에러 레벨 및 데이터 클래스 — END ==============


# ============== [03] ErrorHandler 클래스 — START ==============
class ErrorHandler:
    """
    통합 에러 처리 클래스
    
    모든 에러 처리 로직을 중앙화하여 일관성과 유지보수성을 향상시킵니다.
    """
    
    def __init__(self, max_errors: int = 200):
        """
        ErrorHandler 인스턴스 초기화
        
        Args:
            max_errors: 최대 에러 저장 개수
        """
        self.max_errors = max_errors
        self._errors: List[ErrorEntry] = []
        self._error_counters: Dict[ErrorLevel, int] = {
            level: 0 for level in ErrorLevel
        }
        self._session_id = self._generate_session_id()
        self._callbacks: List[Callable[[ErrorEntry], None]] = []
    
    def _generate_session_id(self) -> str:
        """세션 ID 생성"""
        try:
            if st is not None:
                return st.session_state.get("_error_handler_session_id", f"session_{int(time.time())}")
        except Exception:  # noqa: BLE001
            pass
        return f"session_{int(time.time())}"
    
    def _add_error_entry(self, entry: ErrorEntry) -> None:
        """에러 엔트리 추가"""
        # 에러 리스트에 추가
        self._errors.append(entry)
        
        # 카운터 증가
        self._error_counters[entry.level] += 1
        
        # 최대 개수 초과 시 오래된 에러 제거
        if len(self._errors) > self.max_errors:
            removed = self._errors.pop(0)
            self._error_counters[removed.level] -= 1
        
        # 콜백 실행
        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception:  # noqa: BLE001
                pass
        
        # Streamlit 세션 상태에 저장
        self._save_to_session_state()
    
    def _save_to_session_state(self) -> None:
        """Streamlit 세션 상태에 에러 저장"""
        try:
            if st is not None:
                # 최근 에러들만 세션에 저장 (성능 고려)
                recent_errors = self._errors[-50:] if len(self._errors) > 50 else self._errors
                st.session_state["_error_handler_errors"] = [error.to_dict() for error in recent_errors]
                st.session_state["_error_handler_counters"] = self._error_counters.copy()
                st.session_state["_error_handler_session_id"] = self._session_id
        except Exception:  # noqa: BLE001
            pass
    
    def log(
        self,
        message: str,
        level: ErrorLevel = ErrorLevel.INFO,
        source: str = "unknown",
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        에러 로깅 (보안 강화)
        
        Args:
            message: 에러 메시지
            level: 에러 레벨
            source: 에러 발생 소스
            exception: 예외 객체 (선택사항)
            context: 추가 컨텍스트 정보
            user_id: 사용자 ID (선택사항)
        """
        # 보안 에러 메시지 정화
        from src.core.security_manager import sanitize_error_message
        sanitized_message = sanitize_error_message(Exception(message), context) if message else "Unknown error"
        
        # 트레이스백 생성 (보안상 민감한 정보 제거)
        traceback_str = None
        if exception:
            try:
                raw_tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
                # 민감한 경로 정보 제거
                import re
                # 파일 경로를 간소화
                traceback_str = re.sub(r'File "([^"]*[/\\])([^/\\"]+)"', r'File "\2"', raw_tb)
                # 라인 번호 제거
                traceback_str = re.sub(r', line \d+', ', line ...', traceback_str)
            except Exception:
                traceback_str = "Traceback information unavailable"
        
        # 에러 엔트리 생성
        entry = ErrorEntry(
            timestamp=datetime.now(),
            level=level,
            message=sanitized_message,
            source=source,
            traceback=traceback_str,
            context=context or {},
            user_id=user_id,
            session_id=self._session_id
        )
        
        # 에러 엔트리 추가
        self._add_error_entry(entry)
        
        # 콘솔 출력 (개발 환경)
        print(entry.to_string())
    
    def log_info(self, message: str, source: str = "unknown", **kwargs) -> None:
        """정보 로깅"""
        self.log(message, ErrorLevel.INFO, source, **kwargs)
    
    def log_warn(self, message: str, source: str = "unknown", **kwargs) -> None:
        """경고 로깅"""
        self.log(message, ErrorLevel.WARN, source, **kwargs)
    
    def log_error(self, message: str, source: str = "unknown", **kwargs) -> None:
        """에러 로깅"""
        self.log(message, ErrorLevel.ERROR, source, **kwargs)
    
    def log_critical(self, message: str, source: str = "unknown", **kwargs) -> None:
        """치명적 에러 로깅"""
        self.log(message, ErrorLevel.CRITICAL, source, **kwargs)
    
    def log_exception(
        self,
        exception: Exception,
        message: Optional[str] = None,
        source: str = "unknown",
        level: ErrorLevel = ErrorLevel.ERROR,
        **kwargs
    ) -> None:
        """예외 로깅"""
        if message is None:
            message = f"Exception: {type(exception).__name__}: {str(exception)}"
        
        self.log(message, level, source, exception=exception, **kwargs)
    
    def get_errors(
        self,
        level: Optional[ErrorLevel] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ErrorEntry]:
        """
        에러 목록 조회
        
        Args:
            level: 필터링할 에러 레벨
            source: 필터링할 소스
            limit: 최대 개수
            
        Returns:
            필터링된 에러 목록
        """
        errors = self._errors
        
        # 레벨 필터링
        if level is not None:
            errors = [e for e in errors if e.level == level]
        
        # 소스 필터링
        if source is not None:
            errors = [e for e in errors if e.source == source]
        
        # 개수 제한
        if limit is not None:
            errors = errors[-limit:]
        
        return errors
    
    def get_error_summary(self) -> Dict[str, Any]:
        """에러 요약 정보 반환"""
        return {
            "total_errors": len(self._errors),
            "error_counters": self._error_counters.copy(),
            "session_id": self._session_id,
            "latest_error": self._errors[-1].to_dict() if self._errors else None,
            "error_sources": list(set(e.source for e in self._errors)),
            "error_levels": list(set(e.level.value for e in self._errors))
        }
    
    def clear_errors(self) -> None:
        """에러 목록 초기화"""
        self._errors.clear()
        self._error_counters = {level: 0 for level in ErrorLevel}
        self._save_to_session_state()
    
    def add_callback(self, callback: Callable[[ErrorEntry], None]) -> None:
        """에러 발생 시 호출될 콜백 추가"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[ErrorEntry], None]) -> None:
        """콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_errors_text(self) -> str:
        """에러 목록을 텍스트로 반환 (기존 _errors_text() 호환)"""
        if not self._errors:
            return "—"
        
        # 최근 에러들만 텍스트로 변환
        recent_errors = self._errors[-10:] if len(self._errors) > 10 else self._errors
        return "\n".join(error.to_string() for error in recent_errors)
    
    def has_errors(self, level: Optional[ErrorLevel] = None) -> bool:
        """에러 존재 여부 확인"""
        if level is None:
            return len(self._errors) > 0
        return self._error_counters[level] > 0
    
    def get_error_rate(self, level: ErrorLevel) -> float:
        """에러 레벨별 비율 계산"""
        total = len(self._errors)
        if total == 0:
            return 0.0
        return self._error_counters[level] / total

# ============== [03] ErrorHandler 클래스 — END ==============


# ============== [04] 싱글톤 인스턴스 — START ==============
_error_handler_instance: Optional[ErrorHandler] = None

def get_error_handler() -> ErrorHandler:
    """
    ErrorHandler 싱글톤 인스턴스 반환
    
    Returns:
        ErrorHandler 인스턴스
    """
    global _error_handler_instance
    if _error_handler_instance is None:
        _error_handler_instance = ErrorHandler()
    return _error_handler_instance

# ============== [04] 싱글톤 인스턴스 — END ==============


# ============== [05] 편의 함수들 — START ==============
def log_error(message: str, source: str = "unknown", **kwargs) -> None:
    """
    기존 함수와의 호환성을 위한 편의 함수
    
    Args:
        message: 에러 메시지
        source: 에러 발생 소스
        **kwargs: 추가 인자
    """
    get_error_handler().log_error(message, source, **kwargs)

def log_info(message: str, source: str = "unknown", **kwargs) -> None:
    """
    정보 로깅 편의 함수
    
    Args:
        message: 정보 메시지
        source: 메시지 발생 소스
        **kwargs: 추가 인자
    """
    get_error_handler().log_info(message, source, **kwargs)

def log_warn(message: str, source: str = "unknown", **kwargs) -> None:
    """
    경고 로깅 편의 함수
    
    Args:
        message: 경고 메시지
        source: 메시지 발생 소스
        **kwargs: 추가 인자
    """
    get_error_handler().log_warn(message, source, **kwargs)

def log_exception(exception: Exception, message: Optional[str] = None, source: str = "unknown", **kwargs) -> None:
    """
    예외 로깅 편의 함수
    
    Args:
        exception: 예외 객체
        message: 커스텀 메시지
        source: 예외 발생 소스
        **kwargs: 추가 인자
    """
    get_error_handler().log_exception(exception, message, source, **kwargs)

def get_errors_text() -> str:
    """
    기존 _errors_text() 함수와의 호환성을 위한 편의 함수
    
    Returns:
        에러 목록 텍스트
    """
    return get_error_handler().get_errors_text()

def add_error(exception: Exception) -> None:
    """
    기존 _add_error() 함수와의 호환성을 위한 편의 함수
    
    Args:
        exception: 예외 객체
    """
    get_error_handler().log_exception(exception, source="orchestrator")

# ============== [05] 편의 함수들 — END ==============
