from __future__ import annotations

import json
import os
import importlib
from typing import Any, Optional, Sequence, Tuple, Union

# streamlit은 실행 환경에 없을 수도 있으므로 동적 임포트 + Any로 안전 처리
try:
    _st: Any = importlib.import_module("streamlit")
except Exception:
    _st = None  # 실행환경에 없으면 None

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

def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """secrets → env 순서로 조회. dict/list면 JSON 문자열로 반환."""
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
    return os.getenv(name, default)

def promote_env(
    keys: Optional[Sequence[str]] = None,
    also_env: Union[bool, Sequence[str], None] = None,
) -> None:
    """
    필요 시 secrets 값을 환경변수로 승격.

    - keys: 승격을 시도할 키 목록(없으면 내부 기본셋 사용)
    - also_env: True면 단순 보존(하위호환 플래그), 시퀀스면 keys에 추가
    """
    base_keys = list(keys) if keys is not None else list(_DEFAULT_KEYS)
    if isinstance(also_env, (list, tuple)):
        base_keys.extend([str(k) for k in also_env])

    for k in base_keys:
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
