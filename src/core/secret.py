# ========================== [01] imports & defaults ==========================
from __future__ import annotations

import json
import os
from typing import Any, Optional, Sequence, Tuple

try:
    import streamlit as _st  # 런타임에 없을 수 있음
except Exception:
    _st = None  # type: ignore[assignment] 금지 -> Any|None로 처리

_DEFAULT_KEYS: Tuple[str, ...] = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GH_TOKEN",
    "GH_OWNER",
    "GH_REPO",
    "GH_BRANCH",
    "GH_PROMPTS_PATH",
    "GITHUB_TOKEN",
    "GITHUB_OWNER",
    "GITHUB_REPO_NAME",
    "GITHUB_REPO",
    "GDRIVE_PREPARED_FOLDER_ID",
    "GDRIVE_BACKUP_FOLDER_ID",
    "APP_MODE",
    "AUTO_START_MODE",
    "LOCK_MODE_FOR_STUDENTS",
    "APP_ADMIN_PASSWORD",
    "DISABLE_BG",
    "MAIC_PERSIST_DIR",
)

# ============================ [02] public helpers =============================
def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """secrets → env 순서로 조회. dict/list면 JSON 문자열로 반환."""
    # 1) streamlit secrets
    try:
        if _st is not None and hasattr(_st, "secrets"):
            secrets_obj: Any = getattr(_st, "secrets")
            val: Any = secrets_obj.get(name, None)
            if isinstance(val, (str, int, float, bool)):
                return str(val)
            if val is not None:
                return json.dumps(val, ensure_ascii=False)
    except Exception:
        pass
    # 2) env
    return os.getenv(name, default)


def promote_env(keys: Optional[Sequence[str]] = None) -> None:
    """필요 시 secrets 값을 환경변수로 승격."""
    klist = list(keys) if keys is not None else list(_DEFAULT_KEYS)
    for k in klist:
        if os.getenv(k):
            continue
        v = get(k, None)
        if v is not None:
            os.environ[k] = str(v)
    # 서버 안정화 기본값
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")


# ============================ [03] GH convenience =============================
def token() -> str:
    """GitHub 토큰 우선순위."""
    return get("GH_TOKEN") or get("GITHUB_TOKEN") or ""


def resolve_owner_repo() -> Tuple[str, str]:
    """GH 소유자/리포 결정."""
    owner = get("GH_OWNER") or ""
    repo = get("GH_REPO") or ""
    if owner and repo:
        return owner, repo
    combo = get("GITHUB_REPO") or ""
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        return o.strip(), r.strip()
    owner = owner or (get("GITHUB_OWNER") or "")
    repo = repo or (get("GITHUB_REPO_NAME") or "")
    return owner, repo
