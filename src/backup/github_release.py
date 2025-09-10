# ========================= [backup/github_release.py] =========================
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union
from pathlib import Path
from urllib import request as _rq, error as _er, parse as _ps
import json
import zipfile
import tempfile
import shutil
import os


__all__ = ["restore_latest"]


def _secret(name: str, default: str = "") -> str:
    """st.secrets → env 순으로 조회."""
    try:
        import streamlit as st  # lazy
        v = st.secrets.get(name)  # type: ignore[attr-defined]
        if isinstance(v, str) and v:
            return v
    except Exception:
        pass
    return os.getenv(name, default)


def _resolve_owner_repo() -> Tuple[str, str]:
    """
    owner/repo 해석(우선순위):
      1) src.core.secret.resolve_owner_repo()
      2) secrets/env(GH_OWNER/GITHUB_OWNER + GH_REPO/GITHUB_REPO_NAME/GITHUB_REPO)
    """
    try:
        from src.core.secret import resolve_owner_repo as _rr  # type: ignore
        ow, rp = _rr()
        if ow and rp:
            return ow, rp
    except Exception:
        pass

    owner = _secret("GH_OWNER") or _secret("GITHUB_OWNER")
    repo = _secret("GH_REPO") or _secret("GITHUB_REPO_NAME")
    combo = _secret("GITHUB_REPO")
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()

    return owner or "", repo or ""


def _gh_api(url: str, token: str) -> Dict[str, Any]:
    """GitHub API GET with token. 에러 시 {'_error': ...} 반환."""
    req = _rq.Request(url, method="GET")
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with _rq.urlopen(req, timeout=30) as resp:
            txt = resp.read().decode("utf-8", "ignore")
            try:
                return json.loads(txt)
            except Exception:
                return {"_raw": txt}
    except _er.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "detail": e.read().decode()}
    except Exception as e:
        return {"_error": f"net_error: {type(e).__name__}"}


def _pick_index_asset(
    release: Dict[str, Any],
    prefix: str,
    suffix: str,
) -> Optional[Dict[str, Any]]:
    """
    릴리스의 assets에서 index_*zip를 선택.
    - prefix: "index_"
    - suffix: ".zip"
    """
    for a in (release.get("assets") or []):
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


def _download(url: str, dest: Path, token: str = "") -> bool:
    """URL을 dest로 다운로드. 성공 시 True."""
    req = _rq.Request(url, method="GET")
    req.add_header("Accept", "application/octet-stream")
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with _rq.urlopen(req, timeout=180) as resp, open(dest, "wb") as wf:
            shutil.copyfileobj(resp, wf)
        return True
    except Exception:
        return False


def _extract_zip(zip_path: Path, dest_dir: Path) -> bool:
    """zip_path를 dest_dir로 풀기. 성공 시 True."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception:
        return False


def restore_latest(dest_dir: Union[str, Path]) -> bool:
    """
    최신 릴리스에서 'index_*.zip'을 찾아 dest_dir에 복원.
    성공 시 True, 아니면 False.
    """
    token = (
        _secret("GH_TOKEN")
        or _secret("GITHUB_TOKEN")
        or ""
    )
    owner, repo = _resolve_owner_repo()
    if not (token and owner and repo):
        # 토큰/owner/repo 중 누락 → 복원 불가
        return False

    api = f"https://api.github.com/repos/{_ps.quote(owner)}/{_ps.quote(repo)}/releases/latest"
    data = _gh_api(api, token)
    if "_error" in data:
        return False

    asset = _pick_index_asset(data, prefix="index_", suffix=".zip")
    if not asset:
        return False

    url = str(asset.get("browser_download_url") or "")
    if not url:
        return False

    dest = Path(dest_dir).expanduser().resolve()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False

    # 임시 파일로 받은 뒤 추출
    with tempfile.TemporaryDirectory(prefix="maic_dl_") as td:
        tmp_zip = Path(td) / "index.zip"
        if not _download(url, tmp_zip, token):
            return False
        if not _extract_zip(tmp_zip, dest):
            return False

    # 코어 레디마킹 시도(있으면 사용)
    try:
        from src.core.index_probe import mark_ready as _mark_ready  # type: ignore
        _mark_ready(dest)
    except Exception:
        # 폴백: .ready 생성
        try:
            (dest / ".ready").write_text("ok", encoding="utf-8")
        except Exception:
            pass

    return True
# ======================= [backup/github_release.py] END =======================
