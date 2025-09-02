# ===== [01] IMPORTS & UTILS FALLBACK ========================================  # [01] START
from __future__ import annotations

import importlib
import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional, Protocol, Mapping, cast

import requests

# streamlit은 있을 수도/없을 수도 있다.
# - mypy 충돌 방지: st 변수를 먼저 Any|None로 선언 후, 런타임에 모듈/None을 대입
from typing import Any as _AnyForSt
st: _AnyForSt | None
try:
    import streamlit as _st_mod
    st = cast(_AnyForSt, _st_mod)
except Exception:
    st = None  # mypy OK: Optional[Any]

# 공용 유틸: 모듈 동적 임포트 후 존재 확인 + 폴백 제공
_utils: ModuleType | None
try:
    _utils = importlib.import_module("src.common.utils")
except Exception:
    _utils = None  # 모듈 자체가 없을 수 있음


# --- 정적 인터페이스(Protocol) ------------------------------------------------
class _LoggerProto(Protocol):
    def info(self, *a: Any, **k: Any) -> None: ...
    def warning(self, *a: Any, **k: Any) -> None: ...
    def error(self, *a: Any, **k: Any) -> None: ...


def get_secret(name: str, default: str = "") -> str:
    """Streamlit secrets → env → default 순으로 조회(반환은 항상 str)."""
    # 1) src.common.utils.get_secret 우선
    if _utils is not None:
        func = getattr(_utils, "get_secret", None)
        if callable(func):
            try:
                val = func(name, default)
                # 외부 util이 Optional/비문자열을 줄 수 있으므로 안전 변환
                if val is None:
                    return default
                return val if isinstance(val, str) else str(val)
            except Exception:
                pass

    # 2) streamlit.secrets (정적 타입 가드 + 매핑 캐스팅)
    try:
        if st is not None and hasattr(st, "secrets"):
            sec = cast(Mapping[str, Any], st.secrets)  # runtime은 Mapping 유사체
            v = sec.get(name, None)
            if v is not None:
                return v if isinstance(v, str) else str(v)
    except Exception:
        pass

    # 3) 환경변수 (Optional → str로 강제)
    env_v = os.getenv(name)
    return env_v if env_v is not None else default


def logger() -> _LoggerProto:
    """src.common.utils.logger()가 있으면 사용, 없으면 _Logger(Protocol 준수) 반환."""
    if _utils is not None:
        func = getattr(_utils, "logger", None)
        if callable(func):
            try:
                lg = func()
                # 외부 구현이 무엇이든, 최소한 Protocol 충족 보장(duck typing)
                return cast(_LoggerProto, lg)
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
__all__ = ["restore_latest", "get_latest_release"]
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
    """릴리스 자산 중 우선순위(.zip > .tar.gz/.tgz > .gz > 첫 번째)를 선택."""
    assets = rel.get("assets") or []
    if not assets:
        return None
    # 1) zip
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".zip"):
            return a
    # 2) tar.gz / tgz
    for a in assets:
        n = str(a.get("name", "")).lower()
        if n.endswith(".tar.gz") or n.endswith(".tgz"):
            return a
    # 3) 단일 gz (예: chunks.jsonl.gz)
    for a in assets:
        n = str(a.get("name", "")).lower()
        if n.endswith(".gz"):
            return a
    # 4) 그 외 첫 번째
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
        _log(f"압축 해제 실패(zip): {type(e).__name__}: {e}")
        return False


def _extract_targz(data: bytes, dest_dir: Path) -> bool:
    """TAR.GZ / TGZ 바이트를 dest_dir에 풀기."""
    try:
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            tf.extractall(dest_dir)
        return True
    except Exception as e:
        _log(f"압축 해제 실패(tar.gz): {type(e).__name__}: {e}")
        return False


def _extract_gz_to_file(asset_name: str, data: bytes, dest_dir: Path) -> bool:
    """단일 .gz(예: chunks.jsonl.gz)를 dest_dir/<basename>으로 풀기."""
    try:
        import gzip  # 지역 임포트로 상단 구획 변경 불필요
        base = asset_name[:-3] if asset_name.lower().endswith(".gz") else asset_name
        out_path = dest_dir / base
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gf:
            out_path.write_bytes(gf.read())
        return True
    except Exception as e:
        _log(f"압축 해제 실패(gz): {type(e).__name__}: {e}")
        return False


def _extract_auto(asset_name: str, data: bytes, dest_dir: Path) -> bool:
    """자산 이름으로 형식을 유추하여 적절히 해제."""
    n = (asset_name or "").lower()
    if n.endswith(".zip"):
        return _extract_zip(data, dest_dir)
    if n.endswith(".tar.gz") or n.endswith(".tgz"):
        return _extract_targz(data, dest_dir)
    if n.endswith(".gz"):
        return _extract_gz_to_file(asset_name, data, dest_dir)
    # 알 수 없는 형식: zip 시도(실패 시 False)
    return _extract_zip(data, dest_dir)
# [05] END =====================================================================


# ===== [06] PUBLIC API: restore_latest =======================================  # [06] START
def restore_latest(dest_dir: str | Path) -> bool:
    """최신 GitHub Release에서 아티팩트를 내려받아 dest_dir에 복원.

    반환:
        성공 시 True, 실패 시 False (예외를 올리지 않음)

    비고:
        - .zip/.tar.gz/.tgz/.gz 모두 처리
        - 압축 해제 결과가 '최상위 단일 폴더'일 경우, 그 폴더를 한 겹 평탄화하여
          폴더 내부의 파일/디렉터리를 dest_dir 바로 아래로 복사한다.
        - 복원 후 chunks.jsonl이 있고 .ready가 없으면 자동 생성(SSOT 보정)
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

    asset_name = str(asset.get("name") or "")
    _log(f"자산 다운로드: {asset_name}")
    data = _download_asset(asset)
    if not data:
        return False

    # 임시 디렉터리를 사용해 원자적 교체에 가깝게 복원
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1) 압축 해제 (.zip/.tar.gz/.tgz/.gz 자동 판별)
        ok = _extract_auto(asset_name, data, tmp)
        if not ok:
            return False

        # 2) '최상위 단일 폴더' 감지 → 평탄화 대상 루트 결정
        #    (예: tmp/maic-2025-08-29/chunks.jsonl  →  dest/chunks.jsonl)
        children = [p for p in tmp.iterdir() if p.name not in (".DS_Store",) and not p.name.startswith("__MACOSX")]
        src_root = tmp
        if len(children) == 1 and children[0].is_dir():
            src_root = children[0]
            _log(f"평탄화 적용: 최상위 폴더 '{src_root.name}' 내부를 루트로 승격")

        # 3) 복사(기존 동일 경로는 교체). '폴더 자체'가 아니라 '폴더 내부'를 복사한다.
        for p in src_root.iterdir():
            target = dest / p.name
            try:
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if p.is_dir():
                    shutil.copytree(p, target)
                else:
                    shutil.copy2(p, target)
            except Exception as e:
                _log(f"파일 복사 실패: {p.name} → {target.name}: {type(e).__name__}: {e}")
                return False

    # 4) SSOT 보정: chunks.jsonl만 존재하고 .ready가 없으면 생성
    try:
        chunks = dest / "chunks.jsonl"
        ready = dest / ".ready"
        if chunks.exists() and chunks.stat().st_size > 0 and not ready.exists():
            ready.write_text("ok", encoding="utf-8")
    except Exception:
        pass

    _log("복원이 완료되었습니다.")
    return True
# ===== [06] PUBLIC API: restore_latest =======================================  # [06] END


# ===== [07] PUBLIC API: get_latest_release ===================================  # [07] START
def get_latest_release(repo: str | None = None) -> Optional[dict]:
    """가장 최신 GitHub Release의 원본 JSON(dict)을 반환.
    - 성공: GitHub 'latest' 릴리스 JSON(dict) 반환(예: {'tag_name': 'v1.2.3', ...})
    - 실패/없음: None 반환 (예외는 올리지 않음; 로그만 남김)
    """
    r = (repo or _repo() or "").strip()
    if not r:
        _log("get_latest_release: GITHUB_REPO 미설정")
        return None
    try:
        return _latest_release(r)  # 내부에서 raise_for_status/예외 처리
    except Exception as e:
        _log(f"get_latest_release 오류: {type(e).__name__}: {e}")
        return None
# [07] END =====================================================================

