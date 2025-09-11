# src/backup/github_release.py
# =============================================================================
# GitHub Release에서 최신 index_*.zip을 내려받아 dest_dir에 복원
# - Ruff E402/E501 준수: import 최상단, 100자 래핑
# - 네트워크/IO 실패 시 False 반환(예외 삼킴)
# - 외부 의존: (선택) src.core.secret, src.core.index_probe
# =============================================================================
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib import error as er
from urllib import request as rq


__all__ = ["restore_latest", "resolve_owner_repo", "token"]


# ============================== [01] Secrets & Repo ==============================
def token() -> str:
    """
    GitHub 토큰 조회:
      1) src.core.secret.token() (있으면)
      2) env: GH_TOKEN / GITHUB_TOKEN
    """
    try:
        # 지연 임포트: 순환 의존/환경 없는 테스트에서 안전
        from src.core.secret import token as _tok  # type: ignore
        t = _tok() or ""
        if isinstance(t, str) and t.strip():
            return t.strip()
    except Exception:
        pass
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = os.getenv(k, "")
        if v:
            return v.strip()
    return ""


def resolve_owner_repo() -> Tuple[str, str]:
    """
    owner/repo 결정:
      1) src.core.secret.resolve_owner_repo() (있으면)
      2) env: (GH_OWNER|GITHUB_OWNER) + (GH_REPO|GITHUB_REPO_NAME)
      3) env: GITHUB_REPO="owner/repo"
    """
    try:
        from src.core.secret import (  # type: ignore
            resolve_owner_repo as _res,
        )
        ow, rp = _res()
        if ow and rp:
            return ow.strip(), rp.strip()
    except Exception:
        pass

    owner = (os.getenv("GH_OWNER") or os.getenv("GITHUB_OWNER") or "").strip()
    repo = (os.getenv("GH_REPO") or os.getenv("GITHUB_REPO_NAME") or "").strip()
    if owner and repo:
        return owner, repo

    combo = (os.getenv("GITHUB_REPO") or "").strip()
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        return o.strip(), r.strip()

    return "", ""


# ============================== [02] HTTP Utilities ==============================
def _api_json(url: str, *, token_: str) -> Dict[str, Any]:
    """GitHub API GET → JSON(dict). 실패 시 빈 dict."""
    req = rq.Request(url)
    if token_:
        req.add_header("Authorization", f"token {token_}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with rq.urlopen(req, timeout=30) as resp:
            txt = resp.read().decode("utf-8", "ignore")
            try:
                return json.loads(txt)
            except Exception:
                return {}
    except er.HTTPError:
        return {}
    except Exception:
        return {}


def _download(url: str, dest: Path, *, token_: str) -> bool:
    """파일 다운로드. 성공 시 True."""
    req = rq.Request(url)
    if token_:
        req.add_header("Authorization", f"token {token_}")
    req.add_header("Accept", "application/octet-stream")
    try:
        with rq.urlopen(req, timeout=180) as resp, open(dest, "wb") as wf:
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                wf.write(chunk)
        return True
    except Exception:
        return False


# ============================== [03] Asset Picker ===============================
def _pick_index_asset(
    release: Dict[str, Any],
    *,
    prefix: str = "index_",
    suffix: str = ".zip",
) -> Optional[Dict[str, Any]]:
    """
    릴리스 assets에서 index_*.zip 선택(최초 매칭 1개).
    """
    assets = release.get("assets") or []
    for a in assets:
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


# ============================== [04] Extractor =================================
def _extract_zip(src_zip: Path, dest_dir: Path) -> bool:
    """ZIP 압축 해제. 성공 시 True."""
    try:
        with zipfile.ZipFile(src_zip, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception:
        return False


def _mark_ready(dest_dir: Path) -> None:
    """
    가능하면 코어 API로 ready 마킹. 실패 시 .ready 파일로 폴백.
    (테스트 환경 안전성 위해 예외 삼킴)
    """
    try:
        from src.core.index_probe import mark_ready as _mark  # type: ignore
        _mark(dest_dir)
        return
    except Exception:
        pass
    try:
        (dest_dir / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass


# ============================== [05] Public API =================================
def restore_latest(
    *,
    dest_dir: str | Path,
    asset_prefix: str = "index_",
    asset_suffix: str = ".zip",
) -> bool:
    """
    최신 릴리스에서 index_*.zip을 내려받아 dest_dir에 복원.
    성공 시 True, 실패 시 False.

    동작 요건:
      - token(): GH_TOKEN/GITHUB_TOKEN 또는 core.secret.token()
      - resolve_owner_repo(): owner/repo
    """
    t = token()
    ow, rp = resolve_owner_repo()
    if not (t and ow and rp):
        return False

    dest = Path(dest_dir).expanduser().resolve()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False

    api = f"https://api.github.com/repos/{ow}/{rp}/releases/latest"
    rel = _api_json(api, token_=t)
    if not rel:
        return False

    asset = _pick_index_asset(rel, prefix=asset_prefix, suffix=asset_suffix)
    if not asset:
        return False

    dl = str(asset.get("browser_download_url") or "")
    if not dl:
        return False

    tmp = dest / f"__restore_{asset.get('id') or 'latest'}.zip"
    ok = _download(dl, tmp, token_=t)
    if not ok:
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass
        return False

    if not _extract_zip(tmp, dest):
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass
        return False

    try:
        tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass

    _mark_ready(dest)
    return True
