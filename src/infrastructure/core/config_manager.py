# ============== [01] ConfigManager 클래스 - 통합 설정 관리 ==============
from __future__ import annotations

import json
import os
import importlib
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, Union
from enum import Enum

# Streamlit은 실행 환경에 없을 수도 있으므로 동적 임포트 + Any로 안전 처리
try:
    _st: Any = importlib.import_module("streamlit")
except Exception:
    _st = None  # 실행환경에 없으면 None

# ============== [02] 설정 구현 타입 ==============
class ConfigImplType(Enum):
    PYDANTIC_V2 = "P2"
    PYDANTIC_V1 = "P1"
    SIMPLE = "SIMPLE"

# ============== [03] 기본 설정 키들 ==============
_DEFAULT_KEYS: Tuple[str, ...] = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "LLM_MODEL",
    "EMBED_MODEL",
    "ADMIN_PASSWORD",
    "APP_ADMIN_PASSWORD",
    "MAIC_ADMIN_PASSWORD",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_OWNER",
    "GH_REPO",
    "GITHUB_OWNER",
    "GITHUB_REPO_NAME",
    "GITHUB_REPO",
    "GDRIVE_PREPARED_FOLDER_ID",
    "GDRIVE_BACKUP_FOLDER_ID",
    "GDRIVE_FOLDER_ID",
    "BACKUP_FOLDER_ID",
    "GDRIVE_SERVICE_ACCOUNT_JSON",
    "GDRIVE_OAUTH",
    "PROMPTS_DRIVE_FOLDER_ID",
    "PROMPTS_FILE_NAME",
    "APP_MODE",
    "AUTO_START_MODE",
    "LOCK_MODE_FOR_STUDENTS",
    "DISABLE_BG",
    "MAIC_PERSIST_DIR",
    "RESPONSE_MODE",
    "SIMILARITY_TOP_K",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "MIN_CHARS_PER_DOC",
    "DEDUP_BY_TEXT_HASH",
    "SKIP_LOW_TEXT_DOCS",
    "PRE_SUMMARIZE_DOCS",
)

# ============== [04] ConfigManager 클래스 ==============
class ConfigManager:
    """
    통합 설정 관리 클래스 - Single Source of Truth
    
    기능:
    - Pydantic v1/v2/SIMPLE 폴백 자동 감지
    - Streamlit secrets → 환경변수 → 기본값 우선순위
    - 타입 안전성 보장
    - 캐싱을 통한 성능 최적화
    """
    
    def __init__(self):
        self._impl_type: ConfigImplType = self._detect_implementation()
        self._cache: Dict[str, Any] = {}
        self._initialized = False
        
    def _detect_implementation(self) -> ConfigImplType:
        """Pydantic 구현 타입 자동 감지"""
        try:
            # v2 (권장) — 별도 패키지
            import pydantic_settings
            return ConfigImplType.PYDANTIC_V2
        except ImportError:
            pass
        
        try:
            # v1 — pydantic 내 BaseSettings
            from pydantic import BaseSettings
            return ConfigImplType.PYDANTIC_V1
        except ImportError:
            pass
        
        # v1/v2 모두 사용 불가 → SIMPLE 폴백
        return ConfigImplType.SIMPLE
    
    def _read_dotenv(self, path: Path) -> Dict[str, str]:
        """간단한 .env 파일 파싱"""
        env = {}
        if not path.exists():
            return env
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env[key.strip()] = value.strip().strip('"\'')
        except Exception:
            # .env 파싱 실패는 침묵
            pass
        return env
    
    def _coerce_bool(self, value: str, default: bool) -> bool:
        """문자열을 boolean으로 변환"""
        if isinstance(value, bool):
            return value
        s = str(value).lower().strip()
        if s in ('true', '1', 'yes', 'on', 'enabled'):
            return True
        elif s in ('false', '0', 'no', 'off', 'disabled'):
            return False
        return default
    
    def _get_from_sources(self, name: str, default: Any = None, expected_type: str = "str") -> Any:
        """
        설정값을 여러 소스에서 우선순위에 따라 조회
        
        우선순위:
        1. Streamlit secrets
        2. 환경변수 (APP_ 접두어)
        3. 환경변수 (원본 이름)
        4. .env 파일
        5. 기본값
        """
        # 1. Streamlit secrets 확인
        if _st is not None and hasattr(_st, "secrets"):
            try:
                secrets_obj: Any = getattr(_st, "secrets")
                val: Any = secrets_obj.get(name, None)
                if val is not None:
                    if isinstance(val, (str, int, float, bool)):
                        raw_value = str(val)
                    else:
                        raw_value = json.dumps(val, ensure_ascii=False)
                    return self._coerce_value(raw_value, default, expected_type)
            except Exception:
                pass
        
        # 2. 환경변수 확인 (APP_ 접두어)
        app_key = f"APP_{name}"
        raw_value = os.environ.get(app_key)
        if raw_value is not None:
            return self._coerce_value(raw_value, default, expected_type)
        
        # 3. 환경변수 확인 (원본 이름)
        raw_value = os.environ.get(name)
        if raw_value is not None:
            return self._coerce_value(raw_value, default, expected_type)
        
        # 4. .env 파일 확인
        dotenv = self._read_dotenv(Path(".env"))
        raw_value = dotenv.get(app_key) or dotenv.get(name)
        if raw_value is not None:
            return self._coerce_value(raw_value, default, expected_type)
        
        # 5. 기본값 반환
        return default
    
    def _coerce_value(self, raw_value: str, default: Any, expected_type: str) -> Any:
        """값을 예상 타입으로 변환"""
        if raw_value is None:
            return default
        
        s = str(raw_value).strip()
        if not s:
            return default
        
        if expected_type == "bool":
            return self._coerce_bool(s, default)
        elif expected_type == "int":
            try:
                return int(s)
            except (ValueError, TypeError):
                return default
        elif expected_type == "float":
            try:
                return float(s)
            except (ValueError, TypeError):
                return default
        else:  # str
            return s
    
    def get(self, name: str, default: Any = None, expected_type: str = "str") -> Any:
        """
        설정값 조회 (캐싱 포함)
        
        Args:
            name: 설정 키
            default: 기본값
            expected_type: 예상 타입 ("str", "int", "float", "bool")
        """
        # 캐시 확인
        cache_key = f"{name}:{expected_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 값 조회
        value = self._get_from_sources(name, default, expected_type)
        
        # 캐시 저장
        self._cache[cache_key] = value
        return value
    
    def get_string(self, name: str, default: str = "") -> str:
        """문자열 설정값 조회"""
        return self.get(name, default, "str")
    
    def get_int(self, name: str, default: int = 0) -> int:
        """정수 설정값 조회"""
        return self.get(name, default, "int")
    
    def get_float(self, name: str, default: float = 0.0) -> float:
        """실수 설정값 조회"""
        return self.get(name, default, "float")
    
    def get_bool(self, name: str, default: bool = False) -> bool:
        """불린 설정값 조회"""
        return self.get(name, default, "bool")
    
    def get_optional_string(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """선택적 문자열 설정값 조회"""
        value = self.get(name, default, "str")
        return value if value else default
    
    def clear_cache(self) -> None:
        """캐시 초기화"""
        self._cache.clear()
    
    def get_implementation_type(self) -> ConfigImplType:
        """현재 구현 타입 반환"""
        return self._impl_type
    
    def is_pydantic_available(self) -> bool:
        """Pydantic 사용 가능 여부"""
        return self._impl_type in (ConfigImplType.PYDANTIC_V1, ConfigImplType.PYDANTIC_V2)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """모든 설정값을 딕셔너리로 반환"""
        settings = {}
        for key in _DEFAULT_KEYS:
            # 타입 추론
            if key in ("SIMILARITY_TOP_K", "CHUNK_SIZE", "CHUNK_OVERLAP", "MIN_CHARS_PER_DOC"):
                settings[key] = self.get_int(key, 0)
            elif key in ("DEDUP_BY_TEXT_HASH", "SKIP_LOW_TEXT_DOCS", "PRE_SUMMARIZE_DOCS", "DISABLE_BG"):
                settings[key] = self.get_bool(key, False)
            else:
                settings[key] = self.get_string(key, "")
        return settings

# ============== [05] 싱글턴 인스턴스 ==============
_config_manager_instance: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """ConfigManager 싱글턴 인스턴스 반환"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance

# ============== [06] 편의 함수들 ==============
def get_config(name: str, default: Any = None, expected_type: str = "str") -> Any:
    """설정값 조회 편의 함수"""
    return get_config_manager().get(name, default, expected_type)

def get_string_config(name: str, default: str = "") -> str:
    """문자열 설정값 조회 편의 함수"""
    return get_config_manager().get_string(name, default)

def get_int_config(name: str, default: int = 0) -> int:
    """정수 설정값 조회 편의 함수"""
    return get_config_manager().get_int(name, default)

def get_bool_config(name: str, default: bool = False) -> bool:
    """불린 설정값 조회 편의 함수"""
    return get_config_manager().get_bool(name, default)

def get_optional_string_config(name: str, default: Optional[str] = None) -> Optional[str]:
    """선택적 문자열 설정값 조회 편의 함수"""
    return get_config_manager().get_optional_string(name, default)

# ============== [07] 하위 호환성을 위한 별칭 ==============
def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """기존 _secret() 함수와의 호환성을 위한 별칭"""
    return get_optional_string_config(name, default)

# ============== [08] 내보내기 ==============
__all__ = [
    "ConfigManager",
    "ConfigImplType", 
    "get_config_manager",
    "get_config",
    "get_string_config",
    "get_int_config", 
    "get_bool_config",
    "get_optional_string_config",
    "_secret",  # 하위 호환성
]
