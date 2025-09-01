import os
from typing import Tuple, Dict
from .fallback_source import build_fallback
from .drive_source import build_from_drive
from .github_source import fetch_yaml_text, build_from_github

def resolve_prompts(mode_token: str, q: str, ev1: str, ev2: str,
                    cur_label: str, cache: Dict) -> Tuple[str, str, str]:
    # GitHub
    try:
        token  = os.getenv("GH_TOKEN") or cache.get("__GH_TOKEN") or ""
        repo   = os.getenv("GH_REPO")  or cache.get("__GH_REPO")  or ""
        branch = os.getenv("GH_BRANCH") or cache.get("__GH_BRANCH") or "main"
        path   = os.getenv("GH_PROMPTS_PATH") or cache.get("__GH_PROMPTS_PATH") or "prompts.yaml"
        if token and repo:
            text = cache.get("__gh_prompts_text") or fetch_yaml_text(token, repo, path, branch)
            if text:
                cache["__gh_prompts_text"] = text
                p = build_from_github(text, mode_token, q, ev1, ev2)
                if p: return p.system, p.user, p.source
    except Exception:
        pass
    # Drive
    p = build_from_drive(mode_token, q, ev1, ev2)
    if p: return p.system, p.user, p.source
    # Fallback
    p = build_fallback(mode_token, q, ev1, ev2, cur_label)
    return p.system, p.user, p.source
