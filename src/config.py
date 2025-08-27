# ===== [01] IMPORTS ==========================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# ===== [02] PATHS ============================================================
# >>>>> START [02] PATHS
import os
from pathlib import Path

APP_NAME = "my_ai_teacher"

def _default_app_data_dir() -> Path:
    """
    OS별 기본 앱 데이터 디렉터리:
      - Windows: %LOCALAPPDATA%\my_ai_teacher
      - POSIX   : $XDG_DATA_HOME 또는 ~/.local/share/my_ai_teacher
    """
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser(r"~\\AppData\\Local")
        return Path(base) / APP_NAME
    base = os.getenv("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / APP_NAME

# 환경변수로 오버라이드 가능(배포/테스트 편의)
APP_DATA_DIR: Path = Path(
    os.getenv("MY_AI_TEACHER_DATA_DIR", str(_default_app_data_dir()))
).resolve()

# 인덱스 산출물의 단일 저장 위치(Drive-first 빌더/앱 공용)
PERSIST_DIR: Path = (APP_DATA_DIR / "storage_gdrive").resolve()

# (신규) 전역 매니페스트/품질 리포트 경로 통일
MANIFEST_PATH: Path = (APP_DATA_DIR / "manifest.json").resolve()
QUALITY_REPORT_PATH: Path = (APP_DATA_DIR / "quality_report.json").resolve()
# <<<<< END [02] PATHS

# ===== [03] SETTINGS MODEL ===================================================
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", case_sensitive=False)

    ADMIN_PASSWORD: Optional[str] = None
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = "models/gemini-1.5-pro"
    EMBED_MODEL: str = "models/text-embedding-004"
    RESPONSE_MODE: str = "compact"
    SIMILARITY_TOP_K: int = 5
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 80
    MIN_CHARS_PER_DOC: int = 80
    DEDUP_BY_TEXT_HASH: bool = True
    SKIP_LOW_TEXT_DOCS: bool = True
    PRE_SUMMARIZE_DOCS: bool = False
    GDRIVE_FOLDER_ID: str = "prepared"
    GDRIVE_SERVICE_ACCOUNT_JSON: str = ""
    BACKUP_FOLDER_ID: Optional[str] = None


settings = Settings()
