# ======================== prompting/github_source.py — START =====================
from __future__ import annotations

import base64
import json
from typing import Dict, Optional

import urllib.error
import urllib.request


def _gh_get_file(repo: str, path: str, token: Optional[str]) -> Optional[bytes]:
    """
    GitHub REST v3: GET /repos/{repo}/contents/{path}
    - token 없으면 무인증(레이트리밋 주의)
    """
    if not repo or not path:
        return None
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "maic/1.0")
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def _safe_yaml_load(b64_content: str) -> Optional[Dict]:
    try:
        raw = base64.b64decode(b64_content.encode("utf-8"))
    except Exception:
        return None
    try:
        import yaml  # lazy

        return yaml.safe_load(raw) or {}
    except Exception:
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None


def fetch_prompts_from_github(
    *,
    repo: Optional[str],
    path: str = "prompts.yaml",
    token: Optional[str] = None,
) -> Optional[Dict]:
    """
    GitHub 레포에서 prompts.yaml을 받아 dict로 반환.
    실패 시 None.
    """
    if not repo:
        return None
    blob = _gh_get_file(repo, path, token)
    if not blob:
        return None
    try:
        meta = json.loads(blob.decode("utf-8"))
        content = meta.get("content")
        if not content:
            return None
        return _safe_yaml_load(content)
    except Exception:
        return None
# ========================= prompting/github_source.py — END ======================
