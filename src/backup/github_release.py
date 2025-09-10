# src/backup/github_release.py
# =============================================================================
# GitHub Release에서 최신 index_*.zip 받아 복원하는 유틸 (ruff/mypy 친화)
# - 공개 API: restore_latest(dest_dir: Path | str) -> bool
# - 사용처: app.py의 AUTO_START_MODE 경로 (우선 시도 대상)
# =============================================================================
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json
import os
import zipfile
from urllib import request as rq, error as er, parse as ps


__all__ = ["restore_latest"]


# ------------------------------ secrets/owner/repo ----------------------------
def _secret(name: str, default: str = "") -> str:
    """st.secrets → env 순으로 조회(의존성 최소화)."""
    try:
        # streamlit 미설치 환경 고려
        import streamlit as st  # type: ignore
        v = st.secrets.get(name)  # type: ignore[attr-defined]
        if isinstance(v, str) and v:
            return v
    except Exception:
        pass
    return os.getenv(name, default)


def _resolve_owner_repo() -> Tuple[str, str]:
    """src.core.secret 있으면 우선 사용, 없으면 env에서 추론."""
    try:
        from src.core.secret import resolve_owner_repo as _res  # type: ignore
        owner, repo = _res()
        if owner and repo:
            return owner, repo
    except Exception:
        pass

    owner = _secret("GH_OWNER") or _secret("GITHUB_OWNER")
    repo = _secret("GH_REPO") or _secret("GITHUB_REPO_NAME")
    combo = _secret("GITHUB_REPO")
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()
    return owner or "", repo or ""


def _resolve_token() -> str:
    """src.core.secret.token() 우선, 없으면 env/secrets."""
    try:
        from src.core.secret import token as _tok  # type: ignore
        t = _tok()
        if t:
            return t
    except Exception:
        pass
    return _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")


# --------------------------------- HTTP helper --------------------------------
def _gh_api(
    url: str,
    token: str,
    *,
    data: Optional[bytes] = None,
    method: str = "GET",
    ctype: str = "",
    timeout: int = 30,
) -> Dict[str, Any]:
    """GitHub REST API 호출(간단 래퍼). 실패 시 {_error: ...} 반환."""
    req = rq.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if ctype:
        req.add_header("Content-Type", ctype)

    try:
        with rq.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "ignore")
            try:
                return json.loads(text)
            except Exception:
                return {"_raw": text}
    except er.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()
        except Exception:
            pass
        return {"_error": f"HTTP {e.code}", "detail": detail}
    except Exception as e:
        return {"_error": f"net_error: {type(e).__name__}"}


# ----------------------------- asset picking helper ---------------------------
def _pick_index_asset(
    release: Dict[str, Any],
    *,
    prefix: str = "index_",
    suffix: str = ".zip",
) -> Optional[Dict[str, Any]]:
    """
    릴리스의 assets에서 index_*zip를 선택.
    첫 매칭 1건을 반환(여러 개면 가장 먼저 나온 항목).
    """
    assets = release.get("assets") or []
    for a in assets:
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


# --------------------------- download & extract zip ---------------------------
def _download_and_extract(url: str, dest_dir: Path) -> bool:
    """브라우저 다운로드 URL의 zip을 받아 dest_dir에 해제."""
    if not url:
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / "__release_restore__.zip"
    try:
        rq.urlretrieve(url, tmp)
        with zipfile.ZipFile(tmp, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception:
        return False
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


# ---------------------------------- public API --------------------------------
def restore_latest(dest_dir: Path | str) -> bool:
    """
    최신 Release의 index_*.zip을 다운로드해 dest_dir에 복원.
    성공 시 True, 실패 시 False.
    """
    token = _resolve_token()
    owner, repo = _resolve_owner_repo()
    if not (owner and repo and token):
        return False

    api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    rel = _gh_api(api, token)
    if "_error" in rel:
        return False

    asset = _pick_index_asset(rel)
    if not asset:
        return False

    dl = asset.get("browser_download_url")
    if not isinstance(dl, str) or not dl:
        return False

    p = Path(dest_dir).expanduser()
    ok = _download_and_extract(dl, p)
    if not ok:
        return False

    # 인덱스 준비 완료 마킹
    try:
        from src.core.index_probe import mark_ready as _mark  # type: ignore
        _mark(p)
    except Exception:
        try:
            (p / ".ready").write_text("ok", encoding="utf-8")
        except Exception:
            pass
    return True
