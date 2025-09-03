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


# [03] Release Publish: publish_backup() ========================================  # [03] START
def publish_backup(persist_dir: str | Path,
                   keep: int = 5) -> bool:
    """
    로컬 인덱스를 GitHub 릴리스에 백업한다.
    - 입력: persist_dir (예: ~/.maic/persist)
    - 업로드: chunks.jsonl.gz, manifest.json
    - 태그 규칙: index-YYYYMMDD-HHMMSS  (가능하면 manifest.build_id를 사용)
    - 보존 정책: 'index-' 접두 릴리스 중 최신 keep개만 보존(기본 5개)
    반환: 성공 True / 실패 False
    """
    # 표준 라이브러리만 사용
    import os
    import io
    import json
    import gzip
    import time
    import math
    import shutil
    import urllib.parse
    from pathlib import Path

    try:
        import requests  # 이미 프로젝트 의존성에 포함되어 있다고 가정
    except Exception:
        print("publish_backup: requests 모듈을 찾을 수 없습니다.")
        return False

    # ---- 유틸 -----------------------------------------------------------------
    def _as_path(p) -> Path:
        return p if isinstance(p, Path) else Path(str(p))

    def _read_text(p: Path) -> str | None:
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return None

    def _sha256_file(p: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with p.open("rb") as r:
            for chunk in iter(lambda: r.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _count_lines(p: Path, limit: int | None = None) -> int:
        # 큰 파일에서도 빠르게 동작하도록 버퍼링
        cnt = 0
        try:
            with p.open("rb") as f:
                for b in iter(lambda: f.read(1024 * 1024), b""):
                    cnt += b.count(b"\n")
                    if limit and cnt >= limit:
                        return cnt
        except Exception:
            return 0
        return cnt

    def _gzip_bytes(data: bytes) -> bytes:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(data)
        return buf.getvalue()

    def _git_headers(token: str) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "maic-backup-bot",
        }

    def _upload_headers(token: str, content_type: str) -> dict[str, str]:
        h = _git_headers(token)
        h["Content-Type"] = content_type
        return h

    def _get_env(name: str, default: str = "") -> str:
        v = os.getenv(name)
        return v if isinstance(v, str) and v.strip() else default

    # ---- 입력/환경 수집 --------------------------------------------------------
    base = _as_path(persist_dir)
    chunks = base / "chunks.jsonl"
    manifest = base / "manifest.json"

    if not chunks.exists() or chunks.stat().st_size == 0:
        print("publish_backup: chunks.jsonl 이 존재하지 않거나 비어 있습니다.")
        return False

    # 환경 변수 우선, 없으면 모듈 상수 시도
    token = _get_env("GITHUB_TOKEN")
    repo = _get_env("GITHUB_REPO")
    branch = _get_env("GITHUB_BRANCH", "main")

    if not token or not repo:
        # 로컬 상수에 의존(있을 수도, 없을 수도 있음)
        try:
            from src.backup.github_config import (  # 선택적
                GITHUB_TOKEN as _TK,
                GITHUB_REPO as _RP,
                GITHUB_BRANCH as _BR,
            )
            token = token or _TK
            repo = repo or _RP
            branch = branch or _BR or branch
        except Exception:
            pass

    if not token or not repo:
        print("publish_backup: GITHUB_TOKEN/GITHUB_REPO 설정을 확인해 주세요.")
        return False

    api_base = f"https://api.github.com/repos/{repo}"
    session = requests.Session()
    session.headers.update(_git_headers(token))

    # ---- manifest 구성(없으면 생성) --------------------------------------------
    # mode 표시는 환경변수/기존 manifest에서 가져옴(HQ 버튼 대응)
    mode = (_get_env("MAIC_INDEX_MODE", "STD") or "STD").upper()

    build_id = time.strftime("%Y%m%d-%H%M%S")  # 기본값
    manifest_obj: dict[str, object] = {}
    try:
        if manifest.exists():
            manifest_obj = json.loads(_read_text(manifest) or "{}")
            build_id = str(manifest_obj.get("build_id") or build_id)
            # 최신 스키마 보정
            manifest_obj["mode"] = str(manifest_obj.get("mode") or mode)
            manifest_obj["sha256"] = manifest_obj.get("sha256") or _sha256_file(chunks)
            manifest_obj["chunks"] = int(manifest_obj.get("chunks") or _count_lines(chunks))
            manifest_obj["file"] = "chunks.jsonl"
            manifest_obj["persist_dir"] = str(base)
            manifest_obj["version"] = int(manifest_obj.get("version") or 2)
        else:
            manifest_obj = {
                "build_id": build_id,
                "created_at": int(time.time()),
                "mode": mode,
                "file": "chunks.jsonl",
                "sha256": _sha256_file(chunks),
                "chunks": _count_lines(chunks),
                "persist_dir": str(base),
                "version": 2,
            }
            manifest.write_text(
                json.dumps(manifest_obj, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception as e:
        print(f"publish_backup: manifest 생성/보정 실패: {e}")
        return False

    tag = f"index-{build_id}"
    rel_name = f"{tag} ({mode})"

    # ---- 릴리스 생성 -----------------------------------------------------------
    try:
        payload = {
            "tag_name": tag,
            "name": rel_name,
            "target_commitish": branch,
            "body": (
                "Automated index backup\n"
                f"- mode: {mode}\n"
                f"- chunks: {manifest_obj.get('chunks')}\n"
                f"- sha256: {manifest_obj.get('sha256')}\n"
            ),
            "draft": False,
            "prerelease": False,
        }
        r = session.post(f"{api_base}/releases", json=payload, timeout=30)
        if r.status_code not in (201, 422):
            print(f"publish_backup: 릴리스 생성 실패: {r.status_code} {r.text}")
            return False

        # 422(Unprocessable)인 경우: 동일 태그가 이미 있을 수 있음 → 해당 릴리스 가져오기
        rel = r.json()
        if r.status_code == 422:
            rr = session.get(f"{api_base}/releases/tags/{tag}", timeout=15)
            if rr.status_code != 200:
                print(f"publish_backup: 기존 릴리스 조회 실패: {rr.status_code} {rr.text}")
                return False
            rel = rr.json()

        upload_url_tpl = rel.get("upload_url", "")
        upload_url = upload_url_tpl.split("{")[0]  # {?name,label} 제거
        rel_id = rel.get("id")
        if not upload_url or not rel_id:
            print("publish_backup: upload_url 또는 release id를 얻지 못했습니다.")
            return False
    except Exception as e:
        print(f"publish_backup: 릴리스 생성/조회 예외: {e}")
        return False

    # ---- 에셋 업로드(chunks.jsonl.gz, manifest.json) ---------------------------
    try:
        # gzip 압축
        gz_data = _gzip_bytes(chunks.read_bytes())
        asset_name = "chunks.jsonl.gz"
        q = urllib.parse.urlencode({"name": asset_name})
        urla = f"{upload_url}?{q}"
        ra = session.post(
            urla,
            data=gz_data,
            headers=_upload_headers(token, "application/gzip"),
            timeout=60,
        )
        # 이미 존재(422)하면 교체 위해 먼저 삭제 후 재업로드
        if ra.status_code == 422:
            # 기존 동일 이름 에셋 id 조회
            assets = session.get(f"{api_base}/releases/{rel_id}/assets", timeout=15).json()
            old = next((a for a in assets if a.get("name") == asset_name), None)
            if old:
                aid = old.get("id")
                session.delete(f"{api_base}/releases/assets/{aid}", timeout=15)
                ra = session.post(
                    urla,
                    data=gz_data,
                    headers=_upload_headers(token, "application/gzip"),
                    timeout=60,
                )
        if ra.status_code not in (201, 200):
            print(f"publish_backup: chunks 업로드 실패: {ra.status_code} {ra.text}")
            return False

        # manifest.json 업로드(텍스트)
        m_name = "manifest.json"
        qm = urllib.parse.urlencode({"name": m_name})
        urlm = f"{upload_url}?{qm}"
        rm = session.post(
            urlm,
            data=json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
            headers=_upload_headers(token, "application/json"),
            timeout=30,
        )
        if rm.status_code == 422:
            assets = session.get(f"{api_base}/releases/{rel_id}/assets", timeout=15).json()
            old = next((a for a in assets if a.get("name") == m_name), None)
            if old:
                aid = old.get("id")
                session.delete(f"{api_base}/releases/assets/{aid}", timeout=15)
                rm = session.post(
                    urlm,
                    data=json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
                    headers=_upload_headers(token, "application/json"),
                    timeout=30,
                )
        if rm.status_code not in (201, 200):
            print(f"publish_backup: manifest 업로드 실패: {rm.status_code} {rm.text}")
            return False
    except Exception as e:
        print(f"publish_backup: 에셋 업로드 예외: {e}")
        return False

    # ---- 보존 정책 적용(최근 keep개만 유지) ------------------------------------
    try:
        rels = []
        page = 1
        while True:
            rr = session.get(
                f"{api_base}/releases",
                params={"per_page": 100, "page": page},
                timeout=15,
            )
            if rr.status_code != 200:
                break
            batch = rr.json()
            if not isinstance(batch, list) or not batch:
                break
            rels.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        # index-* 태그만 필터
        index_rels = [
            r for r in rels
            if isinstance(r.get("tag_name"), str) and r.get("tag_name", "").startswith("index-")
        ]
        # 최신순 정렬(created_at 기준)
        index_rels.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # 보존 대상 제외하고 삭제 목록 산출
        to_delete = index_rels[keep:] if keep > 0 else index_rels
        for item in to_delete:
            rid = item.get("id")
            tname = item.get("tag_name", "")
            if not rid:
                continue
            # 릴리스 삭제
            session.delete(f"{api_base}/releases/{rid}", timeout=15)
            # 태그도 정리(실패해도 무시)
            if tname:
                tr = session.delete(f"{api_base}/git/refs/tags/{tname}", timeout=15)
                if tr.status_code not in (204, 200, 404):
                    print(f"publish_backup: 태그 삭제 실패: {tname} {tr.status_code}")
    except Exception as e:
        # 보존 정책 실패는 치명적이지 않음 → True 반환은 유지
        print(f"publish_backup: 보존 정책 적용 중 예외(무시): {e}")

    print(f"publish_backup: 완료 — tag={tag}, repo={repo}")
    return True
# [03] END ======================================================================



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


def get_latest_release(repo: Optional[str] = None) -> Optional[dict]:
    """
    PUBLIC API: 최신 GitHub 릴리스를 반환합니다.
    - repo 인자가 없으면 secrets/env의 GITHUB_REPO를 사용합니다.
    - 요청/파싱 실패 시 None을 반환합니다(예외 발생하지 않음).
    """
    target = (repo or _repo()).strip()
    rel = _latest_release(target)
    if rel is None:
        return None
    # 최소 필드 정규화(호출측 편의)
    if "tag_name" not in rel and "name" in rel:
        rel["tag_name"] = rel.get("name")
    return rel


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
# [04] END


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
        성공 시 True, 실패 시 False (예외는 올리지 않음)

    비고:
        - .zip/.tar.gz/.tgz/.gz 모두 처리
        - 압축 해제 결과가 '최상위 단일 폴더'일 경우, 그 폴더를 한 겹 평탄화하여
          폴더 내부의 파일/디렉터리를 dest_dir 바로 아래로 복사한다.
        - 이후 dest 내 산출물을 정리하여 chunks.jsonl을 루트로 모으고 .ready를 보정한다.
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
        children = [
            p
            for p in tmp.iterdir()
            if p.name not in (".DS_Store",) and not p.name.startswith("__MACOSX")
        ]
        src_root = tmp
        if len(children) == 1 and children[0].is_dir():
            src_root = children[0]
            _log("평탄화 적용: 최상위 폴더 내부를 루트로 승격")
            _log(f"승격 대상 폴더: '{src_root.name}'")

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
                _log("파일 복사 실패(일부 항목). 다음 라인에 상세 표시.")
                _log(f"원본: {p.name} → 대상: {target.name} — {type(e).__name__}: {e}")
                return False

    # 4) 산출물 정리(강화): dest 안에서 chunks.jsonl을 루트로 모으기
    def _size(p: Path) -> int:
        try:
            return p.stat().st_size
        except Exception:
            return 0

    def _decompress_gz(src: Path, dst: Path) -> bool:
        try:
            import gzip
            with gzip.open(src, "rb") as gf:
                data2 = gf.read()
            if not data2:
                return False
            dst.write_bytes(data2)
            return True
        except Exception as e:
            _log(f"gz 해제 실패: {type(e).__name__}: {e}")
            return False

    def _merge_dir_jsonl(chunk_dir: Path, out_file: Path) -> bool:
        """chunk_dir 안의 *.jsonl을 라인 보존으로 병합한다."""
        try:
            bytes_written = 0
            tmp_out = out_file.with_suffix(".jsonl.tmp")
            if tmp_out.exists():
                tmp_out.unlink()
            with tmp_out.open("wb") as w:
                for p in sorted(chunk_dir.glob("*.jsonl")):
                    try:
                        with p.open("rb") as r:
                            while True:
                                buf = r.read(1024 * 1024)
                                if not buf:
                                    break
                                w.write(buf)
                                bytes_written += len(buf)
                    except Exception:
                        continue
            if bytes_written > 0:
                if out_file.exists():
                    out_file.unlink()
                tmp_out.replace(out_file)
                return True
            tmp_out.unlink(missing_ok=True)
            return False
        except Exception as e:
            _log(f"chunks/ 병합 실패: {type(e).__name__}: {e}")
            return False

    target = dest / "chunks.jsonl"

    def _consolidate_to_target(root: Path, target_file: Path) -> bool:
        # 이미 유효하면 끝
        if target_file.exists() and _size(target_file) > 0:
            return True

        # a) 정확명 우선: chunks.jsonl / chunks.jsonl.gz (임의 깊이)
        try:
            exact = [p for p in root.rglob("chunks.jsonl") if _size(p) > 0]
        except Exception:
            exact = []
        if exact:
            best = max(exact, key=_size)
            shutil.copy2(best, target_file)
            _log(f"exact chunks.jsonl 사용: {best}")
            return True

        try:
            exact_gz = [p for p in root.rglob("chunks.jsonl.gz") if _size(p) > 0]
        except Exception:
            exact_gz = []
        if exact_gz:
            best_gz = max(exact_gz, key=_size)
            if _decompress_gz(best_gz, target_file):
                _log(f"exact chunks.jsonl.gz 해제: {best_gz}")
                return True

        # b) 디렉터리 병합: */chunks/*.jsonl
        try:
            chunk_dirs = [d for d in root.rglob("chunks") if d.is_dir()]
        except Exception:
            chunk_dirs = []
        for d in chunk_dirs:
            if _merge_dir_jsonl(d, target_file):
                _log(f"디렉터리 병합 사용: {d}")
                return True

        # c) 범용 파일: 임의의 *.jsonl / *.jsonl.gz 중 가장 큰 것 선택
        try:
            any_jsonl = [p for p in root.rglob("*.jsonl") if _size(p) > 0]
        except Exception:
            any_jsonl = []
        if any_jsonl:
            best_any = max(any_jsonl, key=_size)
            shutil.copy2(best_any, target_file)
            _log(f"임의 *.jsonl 사용: {best_any}")
            return True

        try:
            any_gz = [p for p in root.rglob("*.jsonl.gz") if _size(p) > 0]
        except Exception:
            any_gz = []
        if any_gz:
            best_any_gz = max(any_gz, key=_size)
            if _decompress_gz(best_any_gz, target_file):
                _log(f"임의 *.jsonl.gz 해제: {best_any_gz}")
                return True

        # 실패 시 0바이트 target이 있으면 제거
        if target_file.exists() and _size(target_file) == 0:
            target_file.unlink(missing_ok=True)
        return False

    ok_cons = _consolidate_to_target(dest, target)

    # 🔁 최종 폴백: 릴리스 자산이 chunks.jsonl.gz 단일 파일인 경우, 원본 바이트로 직접 해제
    if not ok_cons and asset_name.lower().endswith(".gz") and data:
        try:
            import gzip
            raw = gzip.decompress(data)
            if raw:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                _log("자산 바이트 직접 해제: chunks.jsonl 생성(폴백)")
                ok_cons = True
        except Exception as e:
            _log(f"폴백 해제 실패: {type(e).__name__}: {e}")

    if not ok_cons:
        _log("산출물 정리 실패: chunks.jsonl을 만들 수 없습니다.")
        # READY 보정 없이 종료
        return False

    # 5) SSOT 보정: chunks.jsonl만 존재하고 .ready가 없으면 생성
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


# ===== [07] PUBLIC API: publish_backup =======================================  # [07] START
def publish_backup(persist_dir: str | Path, tag_prefix: str = "index") -> dict | None:
    """
    현재 로컬 인덱스(PERSIST_DIR/chunks.jsonl)를 GitHub Release로 백업 발행.
    - 새 태그: {tag_prefix}-YYYYMMDD-HHMMSS-{shortid}
    - 자산: chunks.jsonl.gz (+ manifest.json 있으면 함께 업로드)
    반환: {"tag": "...", "release_id": int, "assets": [{"name":..., "size":...}, ...]} 또는 None
    """
    from pathlib import Path
    import os
    import io
    import gzip
    import json
    import datetime
    import requests
    import hashlib

    dest = Path(persist_dir).expanduser()
    src = dest / "chunks.jsonl"
    if not (src.exists() and src.stat().st_size > 0):
        _log("publish_backup: chunks.jsonl이 없거나 0B")
        return None

    repo = _repo()
    if not repo:
        _log("publish_backup: GITHUB_REPO 미설정")
        return None

    token = str(globals().get("GITHUB_TOKEN", "")).strip() or os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        _log("publish_backup: GITHUB_TOKEN 미설정")
        return None

    # sha1 → shortid
    h = hashlib.sha1()
    with src.open("rb") as r:
        for b in iter(lambda: r.read(1024 * 1024), b""):
            h.update(b)
    shortid = h.hexdigest()[:8]

    # 자산 gzip
    gz_name = "chunks.jsonl.gz"
    buf = io.BytesIO()
    with gzip.GzipFile(filename="chunks.jsonl", mode="wb", fileobj=buf) as z:
        z.write(src.read_bytes())
    data_bytes = buf.getvalue()

    # 릴리스 생성
    now = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    tag = f"{tag_prefix}-{now}-{shortid}"
    api = f"https://api.github.com/repos/{repo}/releases"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    body = ""
    mf = dest / "manifest.json"
    if mf.exists():
        try:
            body = mf.read_text(encoding="utf-8")[:4000]  # 본문 길이 제한 대비
        except Exception:
            body = ""

    payload = {"tag_name": tag, "name": tag, "body": body, "draft": False, "prerelease": False}
    try:
        res = requests.post(api, headers=headers, data=json.dumps(payload), timeout=30)
        if res.status_code >= 300:
            _log(f"publish_backup: 릴리스 생성 실패 {res.status_code} {res.text[:200]}")
            return None
        rel = res.json()
        upload_url = rel.get("upload_url", "")
        upload_url = upload_url.split("{", 1)[0]  # https://uploads.github.com/.../assets
        rid = int(rel.get("id") or 0)
    except Exception as e:
        _log(f"publish_backup: 요청 실패 — {type(e).__name__}: {e}")
        return None

    assets_meta = []

    # 자산 업로드 함수
    def _upload(name: str, content_type: str, data: bytes) -> bool:
        try:
            up_url = f"{upload_url}?name={name}"
            up_headers = {
                "Authorization": f"token {token}",
                "Content-Type": content_type,
                "Accept": "application/vnd.github+json",
            }
            res2 = requests.post(up_url, headers=up_headers, data=data, timeout=120)
            if res2.status_code >= 300:
                _log(f"publish_backup: {name} 업로드 실패 {res2.status_code} {res2.text[:200]}")
                return False
            assets_meta.append({"name": name, "size": len(data)})
            return True
        except Exception as e:
            _log(f"publish_backup: {name} 업로드 예외 — {type(e).__name__}: {e}")
            return False

    # chunks.jsonl.gz
    if not _upload(gz_name, "application/gzip", data_bytes):
        return None

    # manifest.json 동반 업로드(있으면)
    if mf.exists():
        try:
            _upload("manifest.json", "application/json", mf.read_bytes())
        except Exception:
            pass

    _log(f"백업 발행 완료: {tag} (assets: {[a['name'] for a in assets_meta]})")
    return {"tag": tag, "release_id": rid, "assets": assets_meta}
# ===== [07] PUBLIC API: publish_backup =======================================  # [07] END
