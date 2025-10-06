# ===== [01] PURPOSE ==========================================================
# 보안 강화 시스템 - 입력 검증, 에러 메시지 개선, 보안 정책 관리
# Zero-Trust 원칙에 따른 외부 입력 검증 및 안전한 에러 처리

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

import re
import hashlib
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# ===== [03] SECURITY CONFIGURATION ===========================================
@dataclass
class SecurityConfig:
    """보안 설정"""
    # 입력 검증
    max_input_length: int = 10000
    max_password_length: int = 128
    min_password_length: int = 4
    
    # 시도 제한
    max_login_attempts: int = 5
    lockout_duration_seconds: int = 300  # 5분
    
    # 에러 메시지
    generic_error_message: str = "처리 중 오류가 발생했습니다."
    login_failed_message: str = "로그인에 실패했습니다."
    invalid_input_message: str = "입력값이 올바르지 않습니다."
    
    # 허용된 문자 패턴
    allowed_chars_pattern: str = r'^[a-zA-Z0-9가-힣\s\-_.,!?@#$%^&*()+=\[\]{}|\\:";\'<>?/~`]*$'
    password_pattern: str = r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?~`]*$'
    
    # 파일 업로드 제한
    max_file_size_mb: int = 10
    allowed_file_extensions: List[str] = None
    
    def __post_init__(self):
        if self.allowed_file_extensions is None:
            self.allowed_file_extensions = ['.txt', '.md', '.json', '.yaml', '.yml']

class SecurityLevel(Enum):
    """보안 수준"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class InputType(Enum):
    """입력 타입"""
    TEXT = "text"
    PASSWORD = "password"
    EMAIL = "email"
    URL = "url"
    FILENAME = "filename"
    YAML = "yaml"
    JSON = "json"

# ===== [04] SECURITY MANAGER CLASS ===========================================
class SecurityManager:
    """보안 관리자 - 통합 보안 정책 및 검증"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self._login_attempts: Dict[str, List[float]] = {}
        self._locked_accounts: Dict[str, float] = {}
        self._error_history: List[Dict[str, Any]] = []
        
    def validate_input(
        self, 
        value: Any, 
        input_type: InputType,
        field_name: str = "입력값",
        security_level: SecurityLevel = SecurityLevel.MEDIUM
    ) -> Tuple[bool, Optional[str]]:
        """
        입력값 검증
        
        Args:
            value: 검증할 값
            input_type: 입력 타입
            field_name: 필드명 (에러 메시지용)
            security_level: 보안 수준
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # None/빈 값 체크
            if value is None:
                return False, f"{field_name}은(는) 필수입니다."
            
            # 문자열 변환
            str_value = str(value).strip()
            if not str_value:
                return False, f"{field_name}은(는) 비어있을 수 없습니다."
            
            # 길이 검증
            if len(str_value) > self.config.max_input_length:
                return False, f"{field_name}은(는) {self.config.max_input_length}자를 초과할 수 없습니다."
            
            # 타입별 검증
            if input_type == InputType.PASSWORD:
                return self._validate_password(str_value, field_name)
            elif input_type == InputType.EMAIL:
                return self._validate_email(str_value, field_name)
            elif input_type == InputType.URL:
                return self._validate_url(str_value, field_name)
            elif input_type == InputType.FILENAME:
                return self._validate_filename(str_value, field_name)
            elif input_type == InputType.YAML:
                return self._validate_yaml(str_value, field_name)
            elif input_type == InputType.JSON:
                return self._validate_json(str_value, field_name)
            else:  # TEXT
                return self._validate_text(str_value, field_name, security_level)
                
        except Exception as e:
            self._log_security_error("input_validation", str(e), {"field": field_name, "type": input_type.value})
            return False, self.config.generic_error_message
    
    def _validate_password(self, password: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """비밀번호 검증"""
        if len(password) < self.config.min_password_length:
            return False, f"{field_name}은(는) 최소 {self.config.min_password_length}자 이상이어야 합니다."
        
        if len(password) > self.config.max_password_length:
            return False, f"{field_name}은(는) {self.config.max_password_length}자를 초과할 수 없습니다."
        
        if not re.match(self.config.password_pattern, password):
            return False, f"{field_name}에 허용되지 않은 문자가 포함되어 있습니다."
        
        return True, None
    
    def _validate_email(self, email: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """이메일 검증"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False, f"{field_name} 형식이 올바르지 않습니다."
        return True, None
    
    def _validate_url(self, url: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """URL 검증"""
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url):
            return False, f"{field_name} 형식이 올바르지 않습니다."
        return True, None
    
    def _validate_filename(self, filename: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """파일명 검증"""
        # 경로 조작 공격 방지
        if '..' in filename or '/' in filename or '\\' in filename:
            return False, f"{field_name}에 허용되지 않은 문자가 포함되어 있습니다."
        
        # 확장자 검증
        path = Path(filename)
        if path.suffix.lower() not in self.config.allowed_file_extensions:
            return False, f"{field_name}의 확장자가 허용되지 않습니다."
        
        return True, None
    
    def _validate_yaml(self, yaml_text: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """YAML 검증"""
        try:
            import yaml
            yaml.safe_load(yaml_text)
            return True, None
        except Exception as e:
            return False, f"{field_name} YAML 형식이 올바르지 않습니다: {str(e)[:100]}"
    
    def _validate_json(self, json_text: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """JSON 검증"""
        try:
            import json
            json.loads(json_text)
            return True, None
        except Exception as e:
            return False, f"{field_name} JSON 형식이 올바르지 않습니다: {str(e)[:100]}"
    
    def _validate_text(self, text: str, field_name: str, security_level: SecurityLevel) -> Tuple[bool, Optional[str]]:
        """일반 텍스트 검증"""
        # 보안 수준에 따른 검증
        if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            # SQL 인젝션 패턴 검사
            sql_patterns = [
                r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
                r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
                r'(\b(OR|AND)\s+\w+\s*=\s*\w+)',
                r'(\b(OR|AND)\s+\'\s*=\s*\')',
                r'(\b(OR|AND)\s+"\s*=\s*")',
            ]
            
            for pattern in sql_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    self._log_security_error("sql_injection_attempt", f"SQL injection pattern detected: {pattern}", {"text": text[:100]})
                    return False, f"{field_name}에 허용되지 않은 내용이 포함되어 있습니다."
            
            # XSS 패턴 검사
            xss_patterns = [
                r'<script[^>]*>.*?</script>',
                r'javascript:',
                r'on\w+\s*=',
                r'<iframe[^>]*>',
                r'<object[^>]*>',
                r'<embed[^>]*>',
            ]
            
            for pattern in xss_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    self._log_security_error("xss_attempt", f"XSS pattern detected: {pattern}", {"text": text[:100]})
                    return False, f"{field_name}에 허용되지 않은 내용이 포함되어 있습니다."
        
        # 허용된 문자 패턴 검사
        if not re.match(self.config.allowed_chars_pattern, text):
            return False, f"{field_name}에 허용되지 않은 문자가 포함되어 있습니다."
        
        return True, None
    
    def check_login_attempts(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """
        로그인 시도 횟수 확인
        
        Args:
            identifier: 사용자 식별자 (IP, 사용자명 등)
            
        Returns:
            (is_allowed, error_message)
        """
        current_time = time.time()
        
        # 계정 잠금 확인
        if identifier in self._locked_accounts:
            lockout_time = self._locked_accounts[identifier]
            if current_time - lockout_time < self.config.lockout_duration_seconds:
                remaining_time = int(self.config.lockout_duration_seconds - (current_time - lockout_time))
                return False, f"계정이 잠겼습니다. {remaining_time}초 후 다시 시도해주세요."
            else:
                # 잠금 해제
                del self._locked_accounts[identifier]
                if identifier in self._login_attempts:
                    del self._login_attempts[identifier]
        
        # 시도 횟수 확인
        if identifier in self._login_attempts:
            attempts = self._login_attempts[identifier]
            # 오래된 시도 제거 (잠금 시간보다 오래된 것)
            attempts = [t for t in attempts if current_time - t < self.config.lockout_duration_seconds]
            self._login_attempts[identifier] = attempts
            
            if len(attempts) >= self.config.max_login_attempts:
                self._locked_accounts[identifier] = current_time
                return False, f"너무 많은 로그인 시도가 있었습니다. {self.config.lockout_duration_seconds}초 후 다시 시도해주세요."
        
        return True, None
    
    def record_login_attempt(self, identifier: str, success: bool) -> None:
        """로그인 시도 기록"""
        current_time = time.time()
        
        if success:
            # 성공 시 기록 초기화
            if identifier in self._login_attempts:
                del self._login_attempts[identifier]
            if identifier in self._locked_accounts:
                del self._locked_accounts[identifier]
        else:
            # 실패 시 기록
            if identifier not in self._login_attempts:
                self._login_attempts[identifier] = []
            self._login_attempts[identifier].append(current_time)
            
            # 보안 로그 기록
            self._log_security_error("login_failed", f"Login attempt failed for {identifier}", {"identifier": identifier})
    
    def sanitize_error_message(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
        """
        에러 메시지 정화 - 민감한 정보 제거
        
        Args:
            error: 원본 에러
            context: 추가 컨텍스트
            
        Returns:
            정화된 에러 메시지
        """
        try:
            error_str = str(error)
            
            # 민감한 정보 패턴 제거
            sensitive_patterns = [
                r'password["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
                r'token["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
                r'key["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
                r'secret["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
                r'api_key["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
                r'/[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/',  # 이메일
                r'/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/',  # IP 주소
            ]
            
            for pattern in sensitive_patterns:
                error_str = re.sub(pattern, '[REDACTED]', error_str, flags=re.IGNORECASE)
            
            # 스택 트레이스 제거 (보안상 민감한 경로 정보)
            if 'Traceback' in error_str:
                error_str = error_str.split('Traceback')[0].strip()
            
            # 길이 제한
            if len(error_str) > 500:
                error_str = error_str[:500] + "..."
            
            return error_str or self.config.generic_error_message
            
        except Exception:
            return self.config.generic_error_message
    
    def _log_security_error(self, event_type: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """보안 이벤트 로깅"""
        try:
            log_entry = {
                "timestamp": time.time(),
                "event_type": event_type,
                "message": message,
                "context": context or {},
            }
            
            # 최근 1000개 이벤트만 유지
            self._error_history.append(log_entry)
            if len(self._error_history) > 1000:
                self._error_history = self._error_history[-1000:]
                
        except Exception:
            pass  # 로깅 실패는 무시
    
    def get_security_summary(self) -> Dict[str, Any]:
        """보안 상태 요약"""
        current_time = time.time()
        
        # 활성 잠금 계정 수
        active_locks = sum(
            1 for lock_time in self._locked_accounts.values()
            if current_time - lock_time < self.config.lockout_duration_seconds
        )
        
        # 최근 보안 이벤트 수 (24시간)
        recent_events = sum(
            1 for event in self._error_history
            if current_time - event["timestamp"] < 86400  # 24시간
        )
        
        return {
            "active_locks": active_locks,
            "recent_security_events": recent_events,
            "total_events": len(self._error_history),
            "config": {
                "max_login_attempts": self.config.max_login_attempts,
                "lockout_duration": self.config.lockout_duration_seconds,
                "max_input_length": self.config.max_input_length,
            }
        }

# ===== [05] SINGLETON PATTERN ================================================
_security_manager_instance: Optional[SecurityManager] = None

def get_security_manager() -> SecurityManager:
    """보안 관리자 싱글톤 인스턴스 반환"""
    global _security_manager_instance
    if _security_manager_instance is None:
        _security_manager_instance = SecurityManager()
    return _security_manager_instance

# ===== [06] CONVENIENCE FUNCTIONS ============================================
def validate_input(
    value: Any, 
    input_type: InputType,
    field_name: str = "입력값",
    security_level: SecurityLevel = SecurityLevel.MEDIUM
) -> Tuple[bool, Optional[str]]:
    """입력값 검증 편의 함수"""
    return get_security_manager().validate_input(value, input_type, field_name, security_level)

def sanitize_error_message(error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
    """에러 메시지 정화 편의 함수"""
    return get_security_manager().sanitize_error_message(error, context)

def check_login_attempts(identifier: str) -> Tuple[bool, Optional[str]]:
    """로그인 시도 확인 편의 함수"""
    return get_security_manager().check_login_attempts(identifier)

def record_login_attempt(identifier: str, success: bool) -> None:
    """로그인 시도 기록 편의 함수"""
    get_security_manager().record_login_attempt(identifier, success)

# ===== [07] END ==============================================================
