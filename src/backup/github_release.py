# ===================== src/backup/github_release.py — FULL REPLACEMENT ==================
from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Optional

import requests

# streamlit은 있을 수도/없을 수도 있다.
try:
    import streamlit as st
except Exception:
    st = None  # pragma: no cover

# 공용 유틸(없을 수도 있음) — 안전 폴백 제공
try:
    from src.common.utils import get_secret, logger  # type: ignore[assignment]
except Exception:
    def get_secret(name: str, default: str = "") -> str:
        return os.getenv(name, default)

    class _Logger:
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def error(self, *a, **k): pass

    def logger() -> _Logger:
        return _Logger()

API = "https://api.github.com"


def _repo() -> str:
    return get_secret("GITHUB_REPO", "") or os.getenv("GITHUB_REPO", "")


def _headers(binary: bool = False) -> Dict[str, str]:
    token = get_secret("GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "maic-backup"}
    if token:
        h["Authorization"] = f"token {token}"
    if binary:
        h["Accept"] = "application/octet-stream"
    return h


def _log(msg: str) -> None:
    try:
        logger().info(msg)
    except Exception:
        pass
    if st:
        try:
            st.write(msg)
        except Exception:
            pass


def _latest_release(repo: str) -> Optional[dict]:
    if not repo:
        _log("GITHUB_REPO가 설정되지 않았습니다.")
        return None
    url = f"{API}/repos/{repo}/releases/latest"
    try:
        r = requests.get(url, headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"최신 릴리스 조회 실패: {type(e).__name__}: {e}")
        return None


def _pick_best_asset(rel: dict) -> Optional[dict]:
    assets = rel.get("assets") or []
    if not assets:
        return None
    # 우선순위: .zip > .tar.gz > 첫 번째
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".zip"):
            return a
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".tar.gz"):
            return a
    return assets[0]


def _download_asset(asset: dict) -> Optional[bytes]:
    # GitHub API 다운로드 URL 우선(use "url"), 없으면 browser_download_url 사용
    url = asset.get("url") or asset.get("browser_download_url")
    if not url:
        return None
    try:
        r = requests.get(url, headers=_headers(binary=True), timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        _log(f"자산 다운로드 실패: {type(e).__name__}: {e}")
        return None


def _extract_zip(data: bytes, dest_dir: Path) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
        return True
    except Exception as e:
        _log(f"압축 해제 실패: {type(e).__name__}: {e}")
        return False


def restore_latest(dest_dir: str | Path) -> bool:
    """최신 GitHub Release에서 아티팩트를 내려받아 dest_dir에 복원.
    반환: 성공 True / 실패 False (예외를 올리지 않음)
    예상 사용처: app.py에서 로컬 인덱스가 없을 때 자동 복원
    """
    dest = Path(dest_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    repo = _repo()
    if not repo:
        _log("restore_latest: GITHUB_REPO 미설정")
        return False

    rel = _latest_release(repo)
    if not rel:
        return False

    name = rel.get("name") or rel.get("tag_name") or "(no-tag)"
    _log(f"최신 릴리스: {name}")

    asset = _pick_best_asset(rel)
    if not asset:
        _log("릴리스에 다운로드 가능한 자산이 없습니다.")
        return False

    _log(f"자산 다운로드: {asset.get('name')}")
    data = _download_asset(asset)
    if not data:
        return False

    # 임시 디렉터리 사용 후 교체
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ok = _extract_zip(data, tmp)
        if not ok:
            return False
        # 복사(기존 동일 경로는 교체)
        for p in tmp.iterdir():
            target = dest / p.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if p.is_dir():
                shutil.copytree(p, target)
            else:
                shutil.copy2(p, target)

    _log("복원이 완료되었습니다.")
    return True
# ===================== end of file =====================================================
