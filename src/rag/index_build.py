# src/rag/index_build.py  — 전체 교체본
# [01] 기본 설정 & 상수  # [01] START
from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 퍼시스트 디렉토리(인덱스/매니페스트 저장)
PERSIST_DIR = Path.home() / ".maic" / "persist"
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# 인덱싱 대상 확장자(감지/인덱싱 동일 규칙)
ALLOWED_EXTS = (".md", ".txt", ".pdf", ".csv", ".zip")

# manifest 경로
MANIFEST_PATH = PERSIST_DIR / "manifest.json"

# prepared 폴더 식별 (이름 또는 ID 직접 지정)
PREPARED_FOLDER_NAME = os.getenv("MAIC_PREPARED_FOLDER_NAME", "prepared")
PREPARED_FOLDER_ID = os.getenv("MAIC_PREPARED_FOLDER_ID")  # 있으면 이 ID 우선

# Google 인증
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# 최대 파일 크기(안전)
MAX_BYTES = 64 * 1024 * 1024  # 64MB
# [01] END

# [02] 공통 유틸  # [02] START
def _log(msg: str) -> None:
    try:
        import streamlit as st

        st.write(msg)
    except Exception:
        print(msg)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, obj: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _iter_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            out.append(p)
    return out


def _hash_path(p: Path) -> str:
    # 간단한 상대경로 해시(릴리스 아티팩트 이름에 활용)
    rel = str(p).encode("utf-8", errors="ignore")
    try:
        import hashlib

        return hashlib.sha256(rel).hexdigest()[:16]
    except Exception:
        return str(abs(hash(rel)))  # 폴백
# [02] END

# [03] GitHub 릴리스 백업 클라이언트  # [03] START
def _get_gh_conf() -> Optional[dict]:
    """환경변수 우선 → Streamlit secrets 보조로 GitHub 설정 로드."""
    token = os.getenv("GH_TOKEN")
    repo = os.getenv("GH_REPO")
    branch = os.getenv("GH_BRANCH", "main")
    if not (token and repo):
        try:
            import streamlit as st  # 실행 맥락에 없을 수 있음

            token = token or st.secrets.get("GH_TOKEN")
            repo = repo or st.secrets.get("GH_REPO")
            branch = os.getenv("GH_BRANCH", st.secrets.get("GH_BRANCH", "main"))
        except Exception:
            pass

    if token and repo:
        return {"token": str(token), "repo": str(repo), "branch": str(branch)}
    return None


def _gh_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"token {token}", "User-Agent": "maic/1.0"}


def _gh_api_get(url: str, headers: Dict[str, str]) -> Optional[dict]:
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def _gh_upload_release_asset(
    *,
    owner_repo: str,
    tag: str,
    file_name: str,
    content_bytes: bytes,
    headers: Dict[str, str],
) -> bool:
    """릴리스 자산 업로드(간단 버전)"""
    import urllib.request
    import urllib.error

    upload_url = f"https://uploads.github.com/repos/{owner_repo}/releases/tags/{tag}/assets?name={file_name}"
    try:
        req = urllib.request.Request(
            upload_url,
            data=content_bytes,
            headers={**headers, "Content-Type": "application/zip"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return 200 <= r.status < 300
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False
# [03] END

# [04] 인덱스 빌드(간단 스텁/데모용)  # [04] START
def _build_index_from_prepared_folder(folder: Path) -> Dict[str, Any]:
    """
    prepared 폴더의 파일을 간단 스캔하여 매니페스트/청크 JSON 생성(데모용).
    """
    files = _iter_files(folder)
    manifest: Dict[str, Any] = {"files": []}
    chunks: List[Dict[str, Any]] = []

    for p in files:
        stat = p.stat()
        manifest["files"].append(
            {"path": str(p), "bytes": stat.st_size, "mtime": int(stat.st_mtime)}
        )
        if p.suffix.lower() in (".md", ".txt", ".csv"):
            try:
                text = p.read_text(encoding="utf-8")
                chunks.append({"text": text[:1000], "meta": {"file_name": p.name}})
            except Exception:
                continue
    return {"manifest": manifest, "chunks": chunks}
# [04] END

# [05] ZIP 스냅샷 생성/복원  # [05] START
def _pack_snapshot(data: Dict[str, Any]) -> bytes:
    """
    manifest.json, chunks.jsonl 형태로 간단 ZIP 패키지 생성.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(data.get("manifest", {}), ensure_ascii=False))
        chunks = data.get("chunks") or []
        text = "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)
        zf.writestr("chunks.jsonl", text)
    buf.seek(0)
    return buf.read()


def _unpack_snapshot(blob: bytes) -> Dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
        out = {"manifest": {}, "chunks": []}
        try:
            out["manifest"] = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception:
            out["manifest"] = {}
        try:
            out["chunks"] = [json.loads(l) for l in zf.read("chunks.jsonl").decode("utf-8").splitlines() if l.strip()]
        except Exception:
            out["chunks"] = []
        return out
# [05] END

# [06] 빌드 엔트리포인트  # [06] START
def build_index_with_checkpoint(prepared_dir: Path) -> Dict[str, Any]:
    """
    prepared_dir에서 인덱스 데이터를 생성하고, 로컬에 기록한 뒤 ZIP 스냅샷을 반환.
    """
    data = _build_index_from_prepared_folder(prepared_dir)
    _write_json(MANIFEST_PATH, data.get("manifest", {}))
    return data
# [06] END

# [07] 로컬/릴리스 복원  # [07] START
def restore_latest_from_release(tag: str = "latest") -> Optional[Dict[str, Any]]:
    """
    릴리스에서 최신 스냅샷 ZIP을 받아 로컬에 복원.
    (여기서는 간단 스텁: 실제 복구는 오케스트레이터가 담당)
    """
    conf = _get_gh_conf()
    if not conf:
        return None
    owner_repo = conf["repo"]
    headers = _gh_headers(conf["token"])
    # 최신 릴리스 자산 조회
    api = f"https://api.github.com/repos/{owner_repo}/releases/tags/{tag}"
    meta = _gh_api_get(api, headers=headers) or {}
    assets = meta.get("assets") or []
    if not assets:
        return None

    # 첫 번째 ZIP 다운로드
    try:
        import urllib.request

        url = assets[0].get("browser_download_url")
        if not url:
            return None
        with urllib.request.urlopen(url, timeout=30) as r:
            blob = r.read()
        data = _unpack_snapshot(blob)
        _write_json(MANIFEST_PATH, data.get("manifest", {}))
        return data
    except Exception:
        return None
# [07] END

# [08] CLI (선택)  # [08] START
def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="MAIC index build (demo)")
    ap.add_argument("--prepared", type=str, default=str(Path.cwd() / "prepared"))
    args = ap.parse_args()

    folder = Path(args.prepared)
    if not folder.exists():
        _log(f"[error] not found: {folder}")
        return
    data = build_index_with_checkpoint(folder)
    _log(f"[ok] manifest files: {len(data.get('manifest', {}).get('files', []))}")
    _log(f"[ok] chunks: {len(data.get('chunks', []))}")


if __name__ == "__main__":
    _main()
# [08] END
