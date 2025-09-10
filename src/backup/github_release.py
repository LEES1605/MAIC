# src/backup/github_release.py
# ============================== [PP-04] github_release ==============================
"""
GitHub Release에서 최신 index_*.zip 자산을 내려받아 지정 폴더에 복원합니다.

특징
- token/owner/repo는 src.core.secret에서 우선 해석, 실패 시 안전 폴백.
- 최신 릴리스에서 prefix/suffix로 자산을 선택(기본: index_*.zip).
- 네트워크/압축/파일 IO를 방어적으로 처리하고, 성공 시 .ready를 마킹.

외부 계약(앱에서 사용)
- restore_latest(dest_dir: Path | str, asset_prefix="index_", asset_suffix=".zip") -> bool
  app.py가 이 함수만 호출합니다. (return True: 성공 / False: 실패)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib import request as _rq, error as _er
import json
import os
import time
import zipfile


# ------------------------------- secrets/owners --------------------------------
def _get_token_owner_repo() -> Tuple[str, str, str]:
    """
    src.core.secret가 있으면 그걸 우선 사용하고, 없으면 env로 폴백.
    반환: (token, owner, repo) — 실패 시 ("", "", "")
    """
    token = owner = repo = ""
    try:
        from src.core.secret import token as _tok, resolve_owner_repo as _res
        token = _tok() or ""
        try:
            owner, repo = _res()
        except Exception:
            owner, repo = "", ""
    except Exception:
        # env fallback
        token = (
            os.getenv("GH_TOKEN")
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("GH_PAT")
            or ""
        )
        combo = os.getenv("GITHUB_REPO", "")
        owner = os.getenv("GH_OWNER") or os.getenv("GITHUB_OWNER") or ""
        repo = os.getenv("GH_REPO") or os.getenv("GITHUB_REPO_NAME") or ""
        if not (owner and repo) and combo and "/" in combo:
            o, r = combo.split("/", 1)
            owner, repo = o.strip(), r.strip()
    return token, owner, repo


# --------------------------------- http/json -----------------------------------
def _http_json(
    url: str,
    *,
    token: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    content_type: str = "application/json",
    timeout: int = 20,
) -> Dict[str, Any]:
    """작은 GitHub API 호출 헬퍼: JSON 파싱 + 에러 안전화."""
    req = _rq.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None and content_type:
        req.add_header("Content-Type", content_type)

    try:
        with _rq.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            try:
                return json.loads(raw)
            except Exception:
                return {"_raw": raw}
    except _er.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "ignore")
        except Exception:
            detail = ""
        return {"_error": f"HTTP {e.code}", "detail": detail}
    except Exception as e:
        return {"_error": f"net_error: {type(e).__name__}", "detail": str(e)}


# ------------------------------- asset selector --------------------------------
def _pick_index_asset(
    release: Dict[str, Any],
    *,
    prefix: str,
    suffix: str,
) -> Optional[Dict[str, Any]]:
    """
    릴리스 객체의 assets에서 prefix/suffix에 맞는 첫 파일을 선택.
    예: prefix='index_', suffix='.zip'
    """
    for a in release.get("assets") or []:
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


# --------------------------------- unzip util ----------------------------------
def _extract_zip(zip_path: Path, dest: Path) -> bool:
    """zip을 dest에 풀어 넣음. 실패 시 False."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        return True
    except Exception:
        return False


# --------------------------------- .ready mark ---------------------------------
def _mark_ready(dest: Path) -> None:
    """가능하면 core_mark_ready 사용, 실패 시 .ready 파일 생성."""
    try:
        from src.core.index_probe import mark_ready as _mark
        _mark(dest)
        return
    except Exception:
        pass
    try:
        (dest / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        # 마지막까지 실패하더라도 치명적이지 않음
        pass


# -------------------------------- restore API ----------------------------------
def restore_latest(
    dest_dir: Path | str,
    *,
    asset_prefix: str = "index_",
    asset_suffix: str = ".zip",
) -> bool:
    """
    최신 Release의 index_*.zip을 내려받아 dest_dir에 복원.
    성공 시 True, 실패 시 False.
    """
    dest = Path(dest_dir).expanduser().resolve()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception:
        # 폴더 생성 실패
        return False

    token, owner, repo = _get_token_owner_repo()
    if not (token and owner and repo):
        # 설정 부족
        return False

    api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    rel = _http_json(api, token=token)
    if "_error" in rel:
        return False

    asset = _pick_index_asset(
        rel,
        prefix=asset_prefix,
        suffix=asset_suffix,
    )
    if not asset:
        return False

    url = str(asset.get("browser_download_url") or "")
    if not url:
        return False

    # 임시 파일로 다운로드 후 안전 추출
    tmp = dest / f"__restore_{int(time.time())}.zip"
    try:
        _rq.urlretrieve(url, tmp)  # github의 asset은 공개 URL로 접근 가능
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False

    ok = _extract_zip(tmp, dest)
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass

    if not ok:
        return False

    _mark_ready(dest)
    return True
# =================================== [END] ====================================
