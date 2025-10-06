from __future__ import annotations

from typing import Optional
from .config_manager import get_config_manager

def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """secrets → env 순서로 조회. dict/list면 JSON 문자열로 반환."""
    return get_config_manager().get_optional_string(name, default)

def promote_env(
    keys: Optional[Sequence[str]] = None,
    also_env: Union[bool, Sequence[str], None] = None,
) -> None:
    """
    필요 시 secrets 값을 환경변수로 승격.

    - keys: 승격을 시도할 키 목록(없으면 내부 기본셋 사용)
    - also_env: True면 단순 보존(하위호환 플래그), 시퀀스면 keys에 추가
    """
    import os
    from typing import Sequence, Union
    
    config_manager = get_config_manager()
    base_keys = list(keys) if keys is not None else list(config_manager.get_all_settings().keys())
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
    from typing import Tuple
    
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
