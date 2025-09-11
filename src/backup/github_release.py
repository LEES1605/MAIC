"""
GitHub Release helper for MAIC index backups.

- Clear logging on every failure path.
- No silent pass: return False with reason or re-raise where appropriate.
- Keep imports at top to satisfy ruff E402.
"""
from __future__ import annotations

import json
import os
import traceback
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib import error as er
from urllib import request as rq
from urllib import parse as ps


__all__ = ["restore_latest", "resolve_owner_repo", "token"]


def _log(msg: str) -> None:
    print(f"[github_release] {msg}")


def _log_exc(msg: str, e: Exception) -> None:
    print(f"[github_release] {msg}: {type(e).__name__}: {e}")
    traceback.print_exc()


def token() -> str:
    """
    Resolve GH token from env/secrets consistently.
    Returns empty string if not present.
    """
    # Prefer env; streamlit secrets may not be available on CI.
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = os.getenv(name, "")
        if v:
            return v
    return ""


def resolve_owner_repo() -> Tuple[str, str]:
    """
    Return (owner, repo) from env.
    Accepted variables:
      - GH_OWNER / GITHUB_OWNER
      - GH_REPO / GITHUB_REPO_NAME
      - GITHUB_REPO (format: owner/repo)
    """
    owner = os.getenv("GH_OWNER") or os.getenv("GITHUB_OWNER") or ""
    repo = os.getenv("GH_REPO") or os.getenv("GITHUB_REPO_NAME") or ""

    combo = os.getenv("GITHUB_REPO", "")
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()

    return (owner or ""), (repo or "")


def _gh_api(url: str, token_: str, data: Optional[bytes],
            method: str, ctype: str) -> Dict[str, Any]:
    req = rq.Request(url, data=data, method=method)
    if token_:
        req.add_header("Authorization", f"token {token_}")
    req.add_header("Accept", "application/vnd.github+json")
    if ctype:
        req.add_header("Content-Type", ctype)
    with rq.urlopen(req, timeout=30) as resp:
        txt = resp.read().decode("utf-8", "ignore")
        try:
            return json.loads(txt)
        except Exception:
            return {"_raw": txt}


def _latest_release(owner: str, repo: str, token_: str) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        return _gh_api(url, token_, None, "GET", "")
    except er.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "detail": e.read().decode()}
    except Exception as e:
        _log_exc("latest release fetch failed", e)
        return {"_error": "network_error"}


def _pick_index_asset(rel: Dict[str, Any],
                      prefix: str = "index_",
                      suffix: str = ".zip") -> Optional[Dict[str, Any]]:
    assets = rel.get("assets") or []
    for a in assets:
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


def _download(url: str, dest: Path) -> bool:
    try:
        rq.urlretrieve(url, dest)  # noqa: S310 (trusted URL from GitHub)
        return True
    except Exception as e:
        _log_exc("download failed", e)
        return False


def _extract(zip_path: Path, dest_dir: Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception as e:
        _log_exc("zip extract failed", e)
        return False


def restore_latest(*, dest_dir: Path) -> bool:
    """
    Download latest index_*.zip from releases and extract into dest_dir.
    Returns True on success, False on any error with logs printed.
    """
    tok = token()
    owner, repo = resolve_owner_repo()
    if not owner or not repo:
        _log("owner/repo not set. Set GH_OWNER/GH_REPO or GITHUB_REPO.")
        return False
    if not tok:
        _log("token missing. Add GH_TOKEN or GITHUB_TOKEN in repository secrets.")
        return False

    rel = _latest_release(owner, repo, tok)
    if "_error" in rel:
        _log(f"latest release error: {rel.get('_error')}")
        if "detail" in rel:
            _log(rel["detail"][:300])
        return False

    asset = _pick_index_asset(rel)
    if not asset:
        _log("no index_*.zip asset in latest release.")
        return False

    dl = asset.get("browser_download_url")
    if not dl:
        _log("asset has no browser_download_url.")
        return False

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _log_exc("cannot create dest_dir", e)
        return False

    tmp = dest_dir / f"__restore_{asset.get('id', 'unknown')}.zip"
    if not _download(str(dl), tmp):
        return False

    ok = _extract(tmp, dest_dir)
    try:
        tmp.unlink(missing_ok=True)  # py>=3.8
    except Exception:
        pass
    if not ok:
        return False

    # mark ready
    try:
        (dest_dir / ".ready").write_text("ok", encoding="utf-8")
    except Exception as e:
        _log_exc("failed to mark .ready", e)
        # still consider success; index extracted
    _log("restore_latest: success")
    return True
