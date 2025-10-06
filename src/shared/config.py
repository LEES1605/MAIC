# ===== [01] CONFIG MANAGER INTEGRATION ======================================  # [01] START
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from src.core.config_manager import get_config_manager

# ConfigManager 인스턴스
config_manager = get_config_manager()
# ===== [01] END ===============================================================


# ===== [02] 경로 상수(앱/스토리지/매니페스트) ==================================  # [02] START
def _default_app_data_dir(app_name: str = "my_ai_teacher") -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"),
            ".local",
            "share",
        )
    return Path(base) / app_name

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR") or _default_app_data_dir()).resolve()

# PERSIST_DIR은 ConfigManager를 통해 결정
def _get_persist_dir() -> Path:
    """PERSIST_DIR 경로 결정"""
    persist_dir = config_manager.get_string("MAIC_PERSIST_DIR")
    if persist_dir:
        return Path(persist_dir).expanduser()
    
    # 기본값: APP_DATA_DIR/storage_gdrive
    return (APP_DATA_DIR / "storage_gdrive").resolve()

PERSIST_DIR = _get_persist_dir()
MANIFEST_PATH = (APP_DATA_DIR / "manifest.json").resolve()
QUALITY_REPORT_PATH = (APP_DATA_DIR / "quality_report.json").resolve()

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
# ===== [02] END ===============================================================


# ===== [03] Settings 모델(ConfigManager 통합) =================  # [03] START
# ConfigManager를 사용한 통합 설정 관리

class Settings:
    """
    ConfigManager를 사용한 통합 설정 클래스
    기존 settings 객체와의 호환성을 위한 프록시
    """
    
    def __init__(self):
        self._config_manager = config_manager
    
    def __getattr__(self, name: str):
        """동적 속성 접근을 ConfigManager로 위임"""
        # 타입 추론
        if name in ("SIMILARITY_TOP_K", "CHUNK_SIZE", "CHUNK_OVERLAP", "MIN_CHARS_PER_DOC"):
            return self._config_manager.get_int(name, 0)
        elif name in ("DEDUP_BY_TEXT_HASH", "SKIP_LOW_TEXT_DOCS", "PRE_SUMMARIZE_DOCS"):
            return self._config_manager.get_bool(name, False)
        else:
            return self._config_manager.get_string(name, "")

# 인스턴스(앱 전역에서 import 하여 사용)
settings = Settings()
# ===== [03] END ===============================================================