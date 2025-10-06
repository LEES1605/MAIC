# ============== [01] imports & docstring — START ==============
"""
PathResolver - 통합 경로 해석 클래스 (SSOT)

이 클래스는 프로젝트 전체에서 사용되는 모든 경로 해석 로직을 통합하여
Single Source of Truth (SSOT)를 제공합니다.

주요 기능:
- PERSIST_DIR 경로 해석 (우선순위 기반)
- 데이터셋 디렉토리 해석
- 앱 데이터 디렉토리 해석
- 임시 디렉토리 해석
- 경로 검증 및 정규화

우선순위 (높음 → 낮음):
1) st.session_state["_PERSIST_DIR"]
2) env "MAIC_PERSIST"
3) env "MAIC_PERSIST_DIR" (legacy)
4) src.rag.index_build.PERSIST_DIR (legacy)
5) src.config.PERSIST_DIR (legacy)
6) default: ~/.maic/persist
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import streamlit as st
except Exception:  # noqa: BLE001
    st = None  # Streamlit 없는 환경(예: CI) 대비

__all__ = ["PathResolver", "get_path_resolver"]

# ============== [01] imports & docstring — END ==============


# ============== [02] PathResolver 클래스 — START ==============
class PathResolver:
    """
    통합 경로 해석 클래스
    
    모든 경로 해석 로직을 중앙화하여 일관성과 유지보수성을 향상시킵니다.
    """
    
    def __init__(self):
        """PathResolver 인스턴스 초기화"""
        self._cache: Dict[str, Path] = {}
        self._default_persist_dir = Path.home() / ".maic" / "persist"
    
    def _normalize_path(self, value: Optional[str]) -> Optional[Path]:
        """문자열 경로를 Path 객체로 정규화"""
        if not value:
            return None
        s = value.strip()
        if not s:
            return None
        return Path(s).expanduser().resolve()
    
    def _get_from_session_state(self, key: str) -> Optional[Path]:
        """Streamlit 세션 상태에서 경로 가져오기"""
        try:
            if st is not None and key in st.session_state:
                return self._normalize_path(str(st.session_state[key]))
        except Exception:  # noqa: BLE001
            pass
        return None
    
    def _get_from_env(self, env_var: str) -> Optional[Path]:
        """환경 변수에서 경로 가져오기"""
        return self._normalize_path(os.getenv(env_var))
    
    def _get_from_module(self, module_name: str, attr_name: str) -> Optional[Path]:
        """모듈에서 경로 가져오기 (lazy import)"""
        try:
            import importlib
            mod = importlib.import_module(module_name)
            if hasattr(mod, attr_name):
                return self._normalize_path(str(getattr(mod, attr_name)))
        except Exception:  # noqa: BLE001
            pass
        return None
    
    def get_persist_dir(self) -> Path:
        """
        PERSIST_DIR 경로 해석 (SSOT)
        
        우선순위:
        1) st.session_state["_PERSIST_DIR"]
        2) env "MAIC_PERSIST"
        3) env "MAIC_PERSIST_DIR" (legacy)
        4) src.rag.index_build.PERSIST_DIR (legacy)
        5) src.config.PERSIST_DIR (legacy)
        6) default: ~/.maic/persist
        """
        cache_key = "persist_dir"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 1) Session-stamped path
        path = self._get_from_session_state("_PERSIST_DIR")
        if path is not None:
            self._cache[cache_key] = path
            return path
        
        # 2) New env
        path = self._get_from_env("MAIC_PERSIST")
        if path is not None:
            self._cache[cache_key] = path
            return path
        
        # 3) Legacy env
        path = self._get_from_env("MAIC_PERSIST_DIR")
        if path is not None:
            self._cache[cache_key] = path
            return path
        
        # 4) Legacy constant from index_build
        path = self._get_from_module("src.rag.index_build", "PERSIST_DIR")
        if path is not None:
            self._cache[cache_key] = path
            return path
        
        # 5) Legacy constant from config
        path = self._get_from_module("src.config", "PERSIST_DIR")
        if path is not None:
            self._cache[cache_key] = path
            return path
        
        # 6) Default
        self._cache[cache_key] = self._default_persist_dir
        return self._default_persist_dir
    
    def get_dataset_dir(self, dataset_dir: Optional[str] = None) -> Path:
        """
        데이터셋 디렉토리 경로 해석
        
        Args:
            dataset_dir: 사용자 지정 데이터셋 디렉토리
            
        Returns:
            정규화된 데이터셋 디렉토리 경로
        """
        if dataset_dir:
            return self._normalize_path(dataset_dir) or self._get_default_dataset_dir()
        return self._get_default_dataset_dir()
    
    def _get_default_dataset_dir(self) -> Path:
        """기본 데이터셋 디렉토리 경로"""
        try:
            # 프로젝트 루트에서 knowledge 디렉토리 찾기
            current_dir = Path(__file__).resolve()
            while current_dir.parent != current_dir:
                knowledge_dir = current_dir / "knowledge"
                if knowledge_dir.exists():
                    return knowledge_dir
                current_dir = current_dir.parent
        except Exception:  # noqa: BLE001
            pass
        
        # 폴백: 현재 디렉토리의 knowledge
        return Path.cwd() / "knowledge"
    
    def get_app_data_dir(self) -> Path:
        """앱 데이터 디렉토리 경로 해석"""
        cache_key = "app_data_dir"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 환경 변수에서 가져오기
        app_data_dir = os.getenv("APP_DATA_DIR")
        if app_data_dir:
            path = self._normalize_path(app_data_dir)
            if path is not None:
                self._cache[cache_key] = path
                return path
        
        # 기본값: ~/.maic/app_data
        default_path = Path.home() / ".maic" / "app_data"
        self._cache[cache_key] = default_path
        return default_path
    
    def get_temp_dir(self) -> Path:
        """임시 디렉토리 경로 해석"""
        cache_key = "temp_dir"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 시스템 임시 디렉토리 사용
        temp_path = Path(tempfile.gettempdir()) / "maic"
        self._cache[cache_key] = temp_path
        return temp_path
    
    def ensure_dir(self, path: Path) -> Path:
        """
        디렉토리 존재 확인 및 생성
        
        Args:
            path: 확인할 디렉토리 경로
            
        Returns:
            정규화된 디렉토리 경로
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path.resolve()
        except Exception as e:
            # 권한 문제 시 대체 경로 시도
            alt_path = Path.home() / "maic_temp" / path.name
            alt_path.mkdir(parents=True, exist_ok=True)
            return alt_path.resolve()
    
    def validate_path(self, path: Path) -> bool:
        """
        경로 유효성 검증
        
        Args:
            path: 검증할 경로
            
        Returns:
            유효한 경로인지 여부
        """
        try:
            # 경로가 존재하고 접근 가능한지 확인
            return path.exists() and os.access(path, os.R_OK)
        except Exception:  # noqa: BLE001
            return False
    
    def clear_cache(self) -> None:
        """캐시 초기화"""
        self._cache.clear()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """캐시 정보 반환"""
        return {
            "cached_paths": list(self._cache.keys()),
            "cache_size": len(self._cache),
            "default_persist_dir": str(self._default_persist_dir)
        }


# ============== [02] PathResolver 클래스 — END ==============


# ============== [03] 싱글톤 인스턴스 — START ==============
_path_resolver_instance: Optional[PathResolver] = None

def get_path_resolver() -> PathResolver:
    """
    PathResolver 싱글톤 인스턴스 반환
    
    Returns:
        PathResolver 인스턴스
    """
    global _path_resolver_instance
    if _path_resolver_instance is None:
        _path_resolver_instance = PathResolver()
    return _path_resolver_instance

# ============== [03] 싱글톤 인스턴스 — END ==============


# ============== [04] 편의 함수들 — START ==============
def effective_persist_dir() -> Path:
    """
    기존 함수와의 호환성을 위한 편의 함수
    
    Returns:
        PERSIST_DIR 경로
    """
    return get_path_resolver().get_persist_dir()

def share_persist_dir_to_session(path: Path) -> None:
    """
    경로를 Streamlit 세션에 공유
    
    Args:
        path: 공유할 경로
    """
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = str(path.resolve())
    except Exception:  # noqa: BLE001
        pass

# ============== [04] 편의 함수들 — END ==============
