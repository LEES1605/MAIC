# ===== [01] IMPORTS & Settings 구현 선택(무의존 폴백 포함) =====================  # [01] START
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# 구현 선택:
# 1) pydantic-settings(v2)        → 최우선
# 2) pydantic(BaseSettings, v1)   → 차선
# 3) SIMPLE(무의존 폴백)          → 둘 다 없거나 v2만 설치된 경우
_IMPL: str = "SIMPLE"

# 폴백용: 외부 패키지 유무와 무관하게 안전하게 재할당 가능하도록 Any로 선언
BaseSettings: Any
SettingsConfigDict: Any

try:
    # v2 (권장) — 별도 패키지
    from pydantic_settings import (  # noqa: F401
        BaseSettings as _P2Base,
        SettingsConfigDict as _P2Cfg,
    )

    BaseSettings = _P2Base
    SettingsConfigDict = _P2Cfg
    _IMPL = "P2"
except Exception:
    try:
        # v1 — pydantic 내 BaseSettings (v2에선 ImportError 유발)
        from pydantic import BaseSettings as _P1Base  # noqa: F401

        class _P1Cfg(dict):
            pass

        BaseSettings = _P1Base
        SettingsConfigDict = _P1Cfg
        _IMPL = "P1"
    except Exception:
        # v1/v2 모두 사용 불가 → SIMPLE 폴백으로 진행
        _IMPL = "SIMPLE"
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
PERSIST_DIR = (APP_DATA_DIR / "storage_gdrive").resolve()
MANIFEST_PATH = (APP_DATA_DIR / "manifest.json").resolve()
QUALITY_REPORT_PATH = (APP_DATA_DIR / "quality_report.json").resolve()

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
# ===== [02] END ===============================================================


# ===== [03] Settings 모델(세 가지 구현을 하나의 인터페이스로) =================  # [03] START
def _coerce_bool(x: str | None, default: bool = False) -> bool:
    if x is None:
        return default
    return str(x).strip().lower() in ("1", "true", "yes", "y", "on")


def _read_dotenv(path: Path) -> dict[str, str]:
    """간단한 .env 파서(선택). 키=값 형태만, 따옴표/주석 일부 지원."""
    env: dict[str, str] = {}
    try:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" not in s:
                    continue
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip().strip("'").strip('"')
    except Exception:
        # .env 파싱 실패는 침묵
        pass
    return env


# --- 공통 필드 정의(타입힌트 목적) --------------------------------------------
class _BaseFields:
    # 자격/모델
    ADMIN_PASSWORD: Optional[str] = None
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "models/gemini-1.5-pro"
    OPENAI_MODEL: Optional[str] = None
    EMBED_MODEL: str = "models/text-embedding-004"

    # 응답/인덱싱 파라미터
    RESPONSE_MODE: str = "compact"
    SIMILARITY_TOP_K: int = 5
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 80
    MIN_CHARS_PER_DOC: int = 80
    DEDUP_BY_TEXT_HASH: bool = True
    SKIP_LOW_TEXT_DOCS: bool = True
    PRE_SUMMARIZE_DOCS: bool = False

    # Drive/백업
    GDRIVE_FOLDER_ID: str = "prepared"  # 지식 폴더(읽기)
    BACKUP_FOLDER_ID: Optional[str] = None  # 백업 폴더(쓰기)
    GDRIVE_SERVICE_ACCOUNT_JSON: str = ""  # 서비스계정(선택)
    GDRIVE_OAUTH: Optional[str] = None  # OAuth JSON 문자열(선택)

    # 프롬프트 동기화
    PROMPTS_DRIVE_FOLDER_ID: Optional[str] = None
    PROMPTS_FILE_NAME: str = "prompts.yaml"


# --- 구현 A: pydantic v2(pydantic-settings) -----------------------------------
if _IMPL == "P2":

    class Settings(_BaseFields, BaseSettings):
        model_config = SettingsConfigDict(
            env_prefix="APP_",
            env_file=".env",
            case_sensitive=False,
            extra="ignore",
        )


# --- 구현 B: pydantic v1 ------------------------------------------------------
elif _IMPL == "P1":

    class Settings(_BaseFields, BaseSettings):
        class Config:
            env_prefix = "APP_"
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"


# --- 구현 C: SIMPLE(무의존) ---------------------------------------------------
else:

    class Settings(_BaseFields):
        """
        pydantic 없이 동작하는 가벼운 설정.
        - 우선순위: os.environ → .env → 기본값
        - 접두어: APP_
        - 간단 캐스팅 지원(bool/int)
        """

        def __init__(self) -> None:
            # 1) .env 읽기(있으면)
            dotenv = _read_dotenv(Path(".env"))

            def _get(name: str, default: Any, kind: str = "str") -> Any:
                env_key = f"APP_{name}"
                raw = os.environ.get(env_key, dotenv.get(env_key))
                if raw is None:
                    return default
                s = str(raw).strip()
                if kind == "bool":
                    return _coerce_bool(s, default)
                if kind == "int":
                    try:
                        return int(s)
                    except Exception:
                        return default
                return s

            # 2) 각 필드 주입
            self.ADMIN_PASSWORD = _get("ADMIN_PASSWORD", None)
            self.GEMINI_API_KEY = _get("GEMINI_API_KEY", "")
            self.OPENAI_API_KEY = _get("OPENAI_API_KEY", None)
            self.LLM_MODEL = _get("LLM_MODEL", "models/gemini-1.5-pro")
            self.OPENAI_MODEL = _get("OPENAI_MODEL", None)
            self.EMBED_MODEL = _get("EMBED_MODEL", "models/text-embedding-004")

            self.RESPONSE_MODE = _get("RESPONSE_MODE", "compact")
            self.SIMILARITY_TOP_K = _get("SIMILARITY_TOP_K", 5, "int")
            self.CHUNK_SIZE = _get("CHUNK_SIZE", 1024, "int")
            self.CHUNK_OVERLAP = _get("CHUNK_OVERLAP", 80, "int")
            self.MIN_CHARS_PER_DOC = _get("MIN_CHARS_PER_DOC", 80, "int")
            self.DEDUP_BY_TEXT_HASH = _get("DEDUP_BY_TEXT_HASH", True, "bool")
            self.SKIP_LOW_TEXT_DOCS = _get("SKIP_LOW_TEXT_DOCS", True, "bool")
            self.PRE_SUMMARIZE_DOCS = _get("PRE_SUMMARIZE_DOCS", False, "bool")

            self.GDRIVE_FOLDER_ID = _get("GDRIVE_FOLDER_ID", "prepared")
            self.BACKUP_FOLDER_ID = _get("BACKUP_FOLDER_ID", None)
            self.GDRIVE_SERVICE_ACCOUNT_JSON = _get(
                "GDRIVE_SERVICE_ACCOUNT_JSON",
                "",
            )
            self.GDRIVE_OAUTH = _get("GDRIVE_OAUTH", None)

            self.PROMPTS_DRIVE_FOLDER_ID = _get("PROMPTS_DRIVE_FOLDER_ID", None)
            self.PROMPTS_FILE_NAME = _get("PROMPTS_FILE_NAME", "prompts.yaml")


# 인스턴스(앱 전역에서 import 하여 사용)
settings = Settings()
# ===== [03] END ===============================================================
