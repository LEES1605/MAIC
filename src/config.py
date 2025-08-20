# ===== [01] IMPORTS ==========================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# ===== [02] PATHS & CONSTS ===================================================
ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/tmp/my_ai_teacher")).resolve()
PERSIST_DIR = (APP_DATA_DIR / "storage_gdrive").resolve()
REPORT_DIR = (APP_DATA_DIR / "reports").resolve()
REPORT_DIR.mkdir(parents=True, exist_ok=True)

QUALITY_REPORT_PATH = str((REPORT_DIR / "quality_report.json").resolve())
MANIFEST_PATH       = str((APP_DATA_DIR / "drive_manifest.json").resolve())
CHECKPOINT_PATH     = str((APP_DATA_DIR / "checkpoint.json").resolve())

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
