# src/core/secret.py
"""
SSOT: Secrets/Env 유틸 (Streamlit 유무에 안전)
- get(): secrets/env 읽기 (dict/list는 JSON 문자열로 반환)
- promote_env(): 지정 키들을 env로 승격 (동명이 없을 때만)
- resolve_owner_repo(): GitHub owner/repo 결정
- token(): GitHub API 토큰 조회
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Sequence, Tuple

try:
    import streamlit as st  # 런타임에 없을 수도 있음
except Exception:
    st = None  # type: ignore[assignment]


_DEFAULT_KEYS: Tuple[str, ...] = (
    # LLM
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    # GitHub
    "GH_TOKEN",
    "GH_OWNER",
    "GH_REPO",
    "GITHUB_TOKEN",
    "GITHUB_OWNER",
    "GITHUB_REPO_NAME",
    "GITHUB_REPO",  # "owner/repo"
    # App
    "APP_MODE",
    "AUTO_START_MODE",
    "LOCK_MODE_FOR_STUDENTS",
    "APP_ADMIN_PASSWORD",
    "DISABLE_BG",
    "MAIC_PERSIST_DIR",
    # GDrive
    "GDRIVE_PREPARED_FOLDER_ID",
    "GDRIVE_BACKUP_FOLDER_ID",
)


def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """secrets 우선 → env, dict/list는 JSON 문자열로 반환."""
    val: Any = None
    try:
        if st is not None and hasattr(st, "secrets"):
            val = st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        val = None

    if val is None:
        val = os.getenv(name, None)

    if val is None:
        return default
    if isinstance(val, str):
        return val
    # dict/list → JSON 문자열
    try:
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return default


def promote_env(
    names: Optional[Sequence[str]] = None,
    *,
    # 호환용 별칭(앱에서 keys/also_env를 쓴 기록이 있어 지원)
    keys: Optional[Sequence[str]] = None,
    also_env: Optional[Sequence[str]] = None,
) -> None:
    """
    secrets → os.environ 승격.
    - 이미 env에 있으면 덮어쓰지 않음.
    - names/keys 둘 중 하나로 목록 제공. 없으면 _DEFAULT_KEYS 사용.
    - also_env: 승격 후 존재 여부만 강제 보정이 필요할 때 추가 확인용.
    """
    wanted: Sequence[str] = names or keys or _DEFAULT_KEYS
    for k in wanted:
        v = get(k)
        if v and not os.getenv(k):
            os.environ[k] = str(v)

    # 그냥 존재만 보장하고 싶은 키가 있다면 여기서 한 번 더 확인
    if also_env:
        for k in also_env:
            if not os.getenv(k):
                v2 = get(k)
                if v2:
                    os.environ[k] = str(v2)


def resolve_owner_repo() -> Tuple[str, str]:
    """
    GitHub owner/repo 결정 규칙:
    1) GH_OWNER + GH_REPO
    2) GITHUB_REPO = "owner/repo"
    3) GITHUB_OWNER + GITHUB_REPO_NAME
    없으면 ("","")
    """
    owner = get("GH_OWNER") or ""
    repo = get("GH_REPO") or ""
    if owner and repo:
        return owner.strip(), repo.strip()

    combo = get("GITHUB_REPO") or ""
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        return o.strip(), r.strip()

    owner = get("GITHUB_OWNER") or ""
    repo = get("GITHUB_REPO_NAME") or ""
    return owner.strip(), repo.strip()


def token() -> Optional[str]:
    """GitHub API 토큰 조회(GH_TOKEN → GITHUB_TOKEN)."""
    return get("GH_TOKEN") or get("GITHUB_TOKEN")
