# [01] START: src/services/index.py — Index publisher facade (전체 교체)
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from src.runtime.gh_release import GHReleases, from_env as gh_from_env, GHError

def _resolve_owner_repo_token() -> GHReleases:
    return gh_from_env()

def publish_index_from_dir(src_dir: str | Path, *, tag: str = "index-latest", asset_name: str = "index.tar.gz") -> Tuple[bool, str]:
    """
    주어진 디렉터리를 tar.gz로 묶어 지정 릴리스에 업로드한다.
    """
    import tarfile, tempfile
    p = Path(src_dir).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        return False, f"index dir not found: {p}"

    out = Path(tempfile.gettempdir()) / "maic-index.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        for item in p.rglob("*"):
            tf.add(item, arcname=str(item.relative_to(p)))

    try:
        gh = _resolve_owner_repo_token()
        gh.ensure_release(tag, title="Index Latest", notes="")
        gh.upload_asset(tag=tag, file_path=out, asset_name=asset_name, clobber=True)
        return True, str(out)
    except GHError as e:
        return False, f"publish failed: {e}"
# [01] END: src/services/index.py — Index publisher facade (전체 교체)
