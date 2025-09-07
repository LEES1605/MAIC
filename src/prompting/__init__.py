# ============================ prompting/__init__.py — START ======================
from __future__ import annotations

from typing import Dict, Optional, Tuple

from .drive_source import fetch_prompts_from_drive
from .fallback_source import DEFAULT_PROMPTS
from .github_source import fetch_prompts_from_github


def _merge(base: Dict, extra: Optional[Dict]) -> Dict:
    if not isinstance(extra, dict):
        return dict(base)
    out = dict(base)
    out.update(extra)
    return out


def resolve_prompts(
    *,
    gh_repo: Optional[str] = None,
    gh_path: str = "prompts.yaml",
    gh_token: Optional[str] = None,
    drive_folder_id: Optional[str] = None,
    drive_file_name: str = "prompts.yaml",
) -> Tuple[Dict, str]:
    """
    우선순위: GitHub → Drive → Fallback
    반환: (prompts_dict, source_tag)
    """
    # 1) GitHub
    gh = fetch_prompts_from_github(repo=gh_repo, path=gh_path, token=gh_token)
    if isinstance(gh, dict) and gh.get("modes"):
        return gh, "github"

    # 2) Drive
    dr = fetch_prompts_from_drive(folder_id=drive_folder_id, file_name=drive_file_name)
    if isinstance(dr, dict) and dr.get("modes"):
        return dr, "drive"

    # 3) Fallback
    return dict(DEFAULT_PROMPTS), "fallback"


__all__ = ["resolve_prompts"]
# ============================= prompting/__init__.py — END =======================
