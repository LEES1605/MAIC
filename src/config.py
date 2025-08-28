# ===== [01] IMPORTS & Pydantic 호환 레이어 ====================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# v2: pydantic-settings / v1: pydantic(BaseSettings)
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # v2 계열
    _P_V2 = True
except Exception:
    from pydantic import BaseSettings  # type: ignore  # v1 계열
    class SettingsConfigDict(dict):    # 더미(호환용)
        ...
    _P_V2 = False
# ===== [01] END ===============================================================


# ===== [02] PATHS =============================================================
# 하드코딩된 /tmp 대신, OS별 사용자 데이터 디렉터리를 기본값으로 사용
# - Windows: %LOCALAPPDATA%\my_ai_teacher
# - POSIX  : $XDG_DATA_HOME 또는 ~/.local/share/my_ai_teacher
def _default_app_data_dir(app_name: str = "my_ai_teacher") -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / app_name

ROOT_DIR = Path(__file__).resolve().parent.parent
APP_DATA_DIR = Path(os.environ.get("APP_DATA_DIR") or _default_app_data_dir()).resolve()

# 인덱스 산출물의 단일 저장 위치(Drive-first 빌더/앱 공용)
PERSIST_DIR = (APP_DATA_DIR / "storage_gdrive").resolve()

# 전역 매니페스트/품질 리포트 경로
MANIFEST_PATH = (APP_DATA_DIR / "manifest.json").resolve()
QUALITY_REPORT_PATH = (APP_DATA_DIR / "quality_report.json").resolve()

# 디렉터리 보장
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
# ===== [02] END ===============================================================


# ===== [03] SETTINGS MODEL ====================================================
class Settings(BaseSettings):
    # --- 자격/모델 ---
    ADMIN_PASSWORD: Optional[str] = None
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "models/gemini-1.5-pro"
    OPENAI_MODEL: Optional[str] = None
    EMBED_MODEL: str = "models/text-embedding-004"

    # --- 응답/인덱싱 파라미터 ---
    RESPONSE_MODE: str = "compact"
    SIMILARITY_TOP_K: int = 5
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 80
    MIN_CHARS_PER_DOC: int = 80
    DEDUP_BY_TEXT_HASH: bool = True
    SKIP_LOW_TEXT_DOCS: bool = True
    PRE_SUMMARIZE_DOCS: bool = False

    # --- Drive/백업 연계 ---
    GDRIVE_FOLDER_ID: str = "prepared"                 # 지식 폴더(읽기)
    BACKUP_FOLDER_ID: Optional[str] = None             # 백업 폴더(쓰기)
    GDRIVE_SERVICE_ACCOUNT_JSON: str = ""              # SA 사용 시
    GDRIVE_OAUTH: Optional[str] = None                 # OAuth(JSON 문자열/토큰 저장용, 선택)

    # --- 프롬프트 동기화(선택) ---
    PROMPTS_DRIVE_FOLDER_ID: Optional[str] = None
    PROMPTS_FILE_NAME: str = "prompts.yaml"

    # v2(권장): model_config / v1: 내부 Config 로 동일 동작 보장
    if _P_V2:
        model_config = SettingsConfigDict(
            env_prefix="APP_",
            env_file=".env",
            case_sensitive=False,
            extra="ignore",
        )
    else:
        class Config:
            env_prefix = "APP_"
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"

# 인스턴스(앱 전역에서 import하여 사용)
settings = Settings()
# ===== [03] END ===============================================================
