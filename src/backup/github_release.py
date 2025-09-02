# ===== [01] IMPORTS & UTILS FALLBACK ========================================  # [01] START
from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

import importlib
import requests

# streamlit은 있을 수도/없을 수도 있다.
try:
    import streamlit as st
except Exception:
    st = None  # pragma: no cover

# 공용 유틸: "속성 임포트" 금지 → 모듈 동적 임포트 후 존재 확인 + 폴백 제공
try:
    _utils = importlib.import_module("src.common.utils")
except Exception:
    _utils = None  # 모듈 자체가 없을 수 있음


def get_secret(name: str, default: str = "") -> str:
    """Streamlit secrets → env → default 순으로 조회."""
    # 1) src.common.utils.get_secret 우선
    if _utils is not None:
        func = getattr(_utils, "get_secret", None)
        if callable(func):
            try:
                val = func(name, default)
                return val if isinstance(val, str) else str(val)
            except Exception:
                pass

    # 2) streamlit.secrets
    try:
        if st is not None and hasattr(st, "secrets"):
            v = st.secrets.get(name)
            if v is not None:
                return v if isinstance(v, str) else str(v)
    except Exception:
        pass

    # 3) 환경변수
    return os.getenv(name, default)


def logger():
    """src.common.utils.logger()가 있으면 사용, 없으면 no-op 로거."""
    if _utils is not None:
        func = getattr(_utils, "logger", None)
        if callable(func):
            try:
                return func()
            except Exception:
                pass

    class _Logger:
        def info(self, *a: Any, **k: Any) -> None: ...
        def warning(self, *a: Any, **k: Any) -> None: ...
        def error(self, *a: Any, **k: Any) -> None: ...

    return _Logger()
# [01] END =====================================================================



# ===== [02] CONSTANTS & PUBLIC EXPORTS =======================================  # [02] START
API = "https://api.github.com"
__all__ = ["restore_latest"]
# [02] END =====================================================================


# ===== [03] HEADERS / LOG HELPERS ============================================  # [03] START
def _repo() -> str:
    """대상 저장소 'owner/repo' 문자열을 조회."""
    return get_secret("GITHUB_REPO", "") or os.getenv("GITHUB_REPO", "")


def _headers(binary: bool = False) -> Dict[str, str]:
    """GitHub API 호출용 기본 헤더 구성."""
    token = get_secret("GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")
    h: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "maic-backup",
    }
    if token:
        h["Authorization"] = f"token {token}"
    if binary:
        h["Accept"] = "application/octet-stream"
    return h


def _log(msg: str) -> None:
    """가능하면 logger/streamlit로도 메시지를 출력."""
    try:
        logger().info(msg)
    except Exception:
        pass
    if st is not None:
        try:
            st.write(msg)
        except Exception:
            pass
# [03] END =====================================================================


# ===== [04] RELEASE DISCOVERY =================================================  # [04] START
def _latest_release(repo: str) -> Optional[dict]:
    """가장 최신 릴리스를 조회. 실패 시 None."""
    if not repo:
        _log("GITHUB_REPO가 설정되지 않았습니다.")
        return None
    url = f"{API}/repos/{repo}/releases/latest"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"최신 릴리스 조회 실패: {type(e).__name__}: {e}")
        return None


def _pick_best_asset(rel: dict) -> Optional[dict]:
    """릴리스 자산 중 우선순위(.zip > .tar.gz > 첫 번째)를 선택."""
    assets = rel.get("assets") or []
    if not assets:
        return None
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".zip"):
            return a
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".tar.gz"):
            return a
    return assets[0] if assets else None
# [04] END =====================================================================


# ===== [05] ASSET DOWNLOAD & EXTRACT =========================================  # [05] START
def _download_asset(asset: dict) -> Optional[bytes]:
    """GitHub 릴리스 자산을 내려받아 바이트로 반환. 실패 시 None."""
    url = asset.get("url") or asset.get("browser_download_url")
    if not url:
        return None
    try:
        r = requests.get(url, headers=_headers(binary=True), timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        _log(f"자산 다운로드 실패: {type(e).__name__}: {e}")
        return None


def _extract_zip(data: bytes, dest_dir: Path) -> bool:
    """ZIP 바이트를 dest_dir에 풀기. 성공 True/실패 False."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
        return True
    except Exception as e:
        _log(f"압축 해제 실패: {type(e).__name__}: {e}")
        return False
# [05] END =====================================================================


# ===== [06] PUBLIC API: restore_latest =======================================  # [06] START
def restore_latest(dest_dir: str | Path) -> bool:
    """최신 GitHub Release에서 아티팩트를 내려받아 dest_dir에 복원.

    반환:
        성공 시 True, 실패 시 False (예외를 올리지 않음)

    비고:
        - 기존 파일/디렉터리는 동일 경로일 경우 교체됩니다.
        - Streamlit 환경이면 진행 로그를 UI에 함께 남깁니다.
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

    # 임시 디렉터리를 사용해 원자적 교체에 가깝게 복원
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
# [06] END =====================================================================
