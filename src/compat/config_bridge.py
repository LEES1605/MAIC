# ===== [01] PURPOSE ==========================================================
# settings / PERSIST_DIR 등 공통 심볼을 단일 바인딩하여
# no-redef / 경로 폴백 문제를 영구 제거합니다.
# ConfigManager를 사용하여 통합 설정 관리

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

from pathlib import Path
from typing import Optional
from src.core.config_manager import get_config_manager

# ===== [03] CONFIG MANAGER INTEGRATION =======================================
config_manager = get_config_manager()

# ===== [04] SINGLE BINDINGS ==================================================
# ConfigManager를 사용하여 설정값 조회
def _get_persist_dir() -> Path:
    """PERSIST_DIR 경로 결정"""
    persist_dir = config_manager.get_string("MAIC_PERSIST_DIR")
    if persist_dir:
        return Path(persist_dir).expanduser()
    
    # 기본값: ~/.maic/persist
    return Path.home() / ".maic" / "persist"

# 설정 객체 (하위 호환성)
class SettingsProxy:
    """기존 settings 객체와의 호환성을 위한 프록시"""
    def __getattr__(self, name: str):
        return config_manager.get_string(name, "")

settings = SettingsProxy()
PERSIST_DIR = _get_persist_dir()
QUALITY_REPORT_PATH: Optional[str] = config_manager.get_optional_string("QUALITY_REPORT_PATH")
MANIFEST_PATH: Optional[str] = config_manager.get_optional_string("MANIFEST_PATH")
CHECKPOINT_PATH: Optional[str] = config_manager.get_optional_string("CHECKPOINT_PATH")

# ===== [05] EXPORTS ==========================================================
__all__ = ["settings", "PERSIST_DIR", "QUALITY_REPORT_PATH", "MANIFEST_PATH", "CHECKPOINT_PATH"]
# ===== [06] END ==============================================================
