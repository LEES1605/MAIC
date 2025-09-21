# ===== [01] FILE: src/backup/github_release.py — START =====
from __future__ import annotations

from pathlib import Path
from typing import Optional

# SSOT 런타임 클라이언트 재노출
from src.runtime.gh_release import GHConfig, GHError, GHReleases, RestoreLog

def publish_zip(*, owner: str, repo: str, token: Optional[str], tag: str, name: Optional[str], zip_path: Path) -> str:
    """
    Backward-compatible convenience for publishing a zip to a release.
    """
    client = GHReleases(GHConfig(owner=owner, repo=repo, token=token))
    rel = client.ensure_release(tag, name=name or f"Indices {tag}")
    client.upload_asset(rel, zip_path)
    return f"OK: uploaded {zip_path.name} to {owner}/{repo} tag={tag}"

__all__ = ["GHConfig", "GHError", "RestoreLog", "GHReleases", "publish_zip"]
# ===== [01] FILE: src/backup/github_release.py — END =====
