# ======================== src/backup/github_release.py =========================
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import json
import os
import tempfile
import zipfile
from urllib import request as _rq, error as _er, parse as _ps

# 내부 SSOT/코어 유틸
def _secret_token() -> str:
    """
    GH 토큰 조회: src.core.secret.token() 우선, 없으면 환경변수 폴백.
    """
    try:
        from src.core.secret import token as _tok
        t = _tok()
        if isinstance(t, str) and t:
            return t
    except Exception:
        pass
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = os.getenv(k, "")
        if v:
            return v
    return ""


def _resolve_owner_repo() -> Tuple[str, str]:
    """
    리포지토리 소유자/이름 결정: src.core.secret.resolve_owner_repo() 우선.
    """
    try:
        from src.core.secret import resolve_owner_repo as _res
        ow, rp = _res()
        if ow and rp:
            return ow, rp
    except Exception:
        pass
    # 환경변수 폴백
    owner = os.getenv("GH_OWNER") or os.getenv("GITHUB_OWNER") or ""
    repo = os.getenv("GH_REPO") or os.getenv("GITHUB_REPO_NAME") or ""
    combo = os.getenv("GITHUB_REPO") or ""
    if not (owner and repo) and combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()
    return owner or "", repo or ""


def _headers(token: str, content_type: str = "") -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"token {token}"
    if content_type:
        h["Content-Type"] = content_type
    return h


def _http_json(url: str, token: str) -> Dict[str, Any]:
    req = _rq.Request(url, headers=_headers(token))
    with _rq.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {"_raw": raw}


def _pick_index_asset(release: Dict[str, Any], prefix: str, suffix: str) -> Optional[Dict[str, Any]]:
    """
    릴리스의 assets에서 index_*zip를 선택.
    - 여러 개인 경우 첫 번째 매칭을 사용(일반적으로 1개)
    """
    for a in (release.get("assets") or []):
        name = str(a.get("name") or "")
        if name.startswith(prefix) and name.endswith(suffix):
            return a
    return None


def _download(url: str, token: str, dest: Path) -> None:
    """
    브라우저 다운로드 URL 또는 assets URL을 받아 파일 저장.
    토큰이 있어도 browser_download_url에는 헤더가 요구되지 않는 경우가 대부분이나,
    private 리포 가능성을 고려해 인증 헤더를 함께 보냅니다.
    """
    req = _rq.Request(url, headers=_headers(token))
    with _rq.urlopen(req, timeout=120) as resp, open(dest, "wb") as wf:
        wf.write(resp.read())


def _mark_ready(persist_dir: Path) -> None:
    """
    인덱스 준비 마킹: 코어 제공 함수가 있으면 우선 사용.
    """
    try:
        from src.core.index_probe import mark_ready as core_mark_ready
        core_mark_ready(persist_dir)
        return
    except Exception:
        pass
    # 폴백: .ready 파일
    try:
        (persist_dir / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass


def restore_latest(
    dest_dir: str | Path,
    *,
    asset_prefix: str = "index_",
    asset_suffix: str = ".zip",
) -> bool:
    """
    GitHub 최신 Release의 인덱스 ZIP(index_*.zip)을 내려받아 dest_dir에 복원.
    성공 시 True, 실패 시 False.
    """
    try:
        dest = Path(dest_dir).expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)

        token = _secret_token()
        owner, repo = _resolve_owner_repo()
        if not (owner and repo):
            return False

        # 최신 릴리스 메타
        latest_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        rel = _http_json(latest_url, token)
        if not isinstance(rel, dict) or ("assets" not in rel):
            return False

        asset = _pick_index_asset(rel, asset_prefix, asset_suffix)
        if not asset:
            return False

        dl = str(asset.get("browser_download_url") or "")
        if not dl:
            return False

        # 다운로드 → 임시 파일
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "index.zip"
            _download(dl, token, tmp)

            # 안전 추출
            with zipfile.ZipFile(tmp, "r") as zf:
                zf.extractall(dest)

        _mark_ready(dest)
        return True
    except _er.HTTPError:
        return False
    except Exception:
        # 민감 정보 노출 방지: 에러는 상위에서 처리/로그
        return False
