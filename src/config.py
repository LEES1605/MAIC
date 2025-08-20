# ===== [01] IMPORTS ==========================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# ===== [02] PATHS ============================================================
# 하드코딩된 /tmp 대신, OS에 맞는 사용자 데이터 디렉터리를 기본값으로 사용.
# - Windows: %LOCALAPPDATA%\my_ai_teacher
# - POSIX (Linux/mac): $XDG_DATA_HOME 또는 ~/.local/share/my_ai_teacher
from pathlib import Path
import os

def _default_app_data_dir(app_name: str = "my_ai_teacher") -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / app_name

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR") or _default_app_data_dir()).resolve()
PERSIST_DIR = (APP_DATA_DIR / "storage_gdrive").resolve()
QUALITY_REPORT_PATH = (APP_DATA_DIR / "quality_report.json").resolve()


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
