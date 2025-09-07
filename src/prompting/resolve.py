# ============================ prompting/resolve.py — START =======================
from __future__ import annotations

from typing import Dict, Optional, Tuple

from . import resolve_prompts as _resolve


def resolve_prompts_dict(
    *,
    gh_repo: Optional[str],
    gh_path: str = "prompts.yaml",
    gh_token: Optional[str] = None,
    drive_folder_id: Optional[str] = None,
    drive_file_name: str = "prompts.yaml",
) -> Tuple[Dict, str]:
    """
    래퍼 함수(외부 의존 처리를 한 곳으로 모음).
    """
    return _resolve(
        gh_repo=gh_repo,
        gh_path=gh_path,
        gh_token=gh_token,
        drive_folder_id=drive_folder_id,
        drive_file_name=drive_file_name,
    )
# ============================= prompting/resolve.py — END ========================
