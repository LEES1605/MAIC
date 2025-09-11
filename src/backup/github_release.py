from __future__ import annotations

"""
GitHub Release: index_*.zip 복원 유틸리티

- restore_latest(dest_dir): 최신 릴리스의 index_*.zip을 받아 dest_dir에 풀고 .ready 마킹.
- 공개/비공개 리포 모두 지원(토큰 필요 시 Authorization 헤더 사용).

보안 주의:
- 토큰은 로깅하거나 예외 메시지에 포함하지 않습니다.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json
import os
import zipfile
from urllib import request as rq, error as er, parse as ps


__all__ = ["restore_latest", "resolve_owner_repo", "token"]


# ----------------------------- secrets resolve ------------------------------
def token() -> str:
    """우선순위: GH_TOKEN > GITHUB_TOKEN > 빈 문자열(미설정)."""
    return os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or ""


def resolve_owner_repo() -> Tuple[str, str]:
    """
    Owner/Repo 해석 규칙:
      1) GH_OWNER/GITHUB_OWNER
      2) GH_REPO/GITHUB_REPO_NAME
      3) GITHUB_REPO (owner/name)
      4) GITHUB_REPOSITORY (CI에서 제공)
    """
    owner = os.getenv("GH_OWNER") or os.getenv("GITHUB_OWNER") or ""
    repo = os.getenv("GH_REPO") or os.getenv("GITHUB_REPO_NAME") or ""

    combo = os.getenv("GITHUB_REPO") or os.getenv("GITHUB_REPOSITORY") or ""
    if not (owner and repo) and combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()

    return owner or "", repo or ""


# ------------------------------ http helpers --------------------------------
def _api_json(url: str, tok: str) -> Dict[str, Any]:
    req = rq.Request(url)
    if tok:
        req.add_header("Authorization", f"token {tok}")
    req.add_header("Accept", "application/vnd.github+json")
    with rq.urlopen(req, timeout=30) as resp:
        txt = resp.read().decode("utf-8", "ignore")
        try:
            return json.loads(txt)
        except Exception:
            return {"_raw": txt}


def _download(url: str, dst: Path, tok: str) -> None:
    req = rq.Request(url)
    if tok:
        req.add_header("Authorization", f"token {tok}")
    req.add_header("Accept", "application/octet-stream")
    with rq.urlopen(req, timeout=180) as resp:
        dst.write_bytes(resp.read())


# ------------------------------- core logic ---------------------------------
def _latest_release(owner: str, repo: str, tok: str) -> Dict[str, Any]:
    api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        return _api_json(api, tok)
    except er.HTTPError as e:  # pragma: no cover
        return {"_error": f"HTTP {e.code}"}
    except Exception as e:  # pragma: no cover
        return {"_error": f"net_error: {type(e).__name__}"}


def _pick_index_asset(
    release: Dict[str, Any], prefix: str, suffix: str
) -> Optional[Dict[str, Any]]:
    """
    릴리스의 assets에서 index_*zip를 선택.
    가장 먼저 일치하는 항목을 채택(다수면 최신 릴리스 규칙에 의해 충분).
    """
    assets = release.get("assets") or []
    for a in assets:
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


def _extract_zip(zip_path: Path, dest_dir: Path) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except zipfile.BadZipFile:
        return False


def _mark_ready(dest_dir: Path) -> None:
    try:
        # 코어 API 있으면 사용(없으면 파일 작성)
        from src.core.index_probe import mark_ready as _core_mark_ready  # type: ignore
        _core_mark_ready(dest_dir)
    except Exception:
        try:
            (dest_dir / ".ready").write_text("ok", encoding="utf-8")
        except Exception:
            pass


def _already_ready(dest_dir: Path) -> bool:
    cj = dest_dir / "chunks.jsonl"
    ready = dest_dir / ".ready"
    try:
        if cj.exists() and cj.stat().st_size > 0 and ready.exists():
            return True
    except Exception:
        return False
    return False


# --------------------------------- public -----------------------------------
def restore_latest(dest_dir: Path) -> bool:
    """
    최신 릴리스의 index_*.zip을 복원.
    - dest_dir가 이미 준비되어 있으면 no-op으로 True 반환.
    - 실패 시 False.
    """
    if not isinstance(dest_dir, Path):
        dest_dir = Path(str(dest_dir)).expanduser()

    if _already_ready(dest_dir):
        return True

    tok = token()
    owner, repo = resolve_owner_repo()
    if not (owner and repo):
        return False

    rel = _latest_release(owner, repo, tok)
    if "_error" in rel or not rel:
        return False

    asset = _pick_index_asset(rel, prefix="index_", suffix=".zip")
    if not asset:
        return False

    url = asset.get("browser_download_url") or ""
    if not url:
        return False

    tmp = dest_dir / f"__index_restore_{os.getpid()}.zip"
    try:
        _download(url, tmp, tok)
        ok = _extract_zip(tmp, dest_dir)
        if not ok:
            return False
        _mark_ready(dest_dir)
        return True
    except Exception:
        return False
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
