# [01]===== src/backup/github_release.py — START =================================
from __future__ import annotations
import os, io, json, gzip, shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
import streamlit as st  # type: ignore

API = "https://api.github.com"

def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = st.secrets.get(name)  # type: ignore[attr-defined]
        if val is None: return os.getenv(name, default)
        if isinstance(val, (str,)): return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)

def _repo() -> str:
    return _secret("GITHUB_REPO", "LEES1605/MAIC") or "LEES1605/MAIC"

def _headers(binary: bool = False) -> Dict[str, str]:
    token = _secret("GITHUB_TOKEN") or ""
    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    if binary:
        h["Accept"] = "application/octet-stream"
    return h

# ── 업로드 유틸(기존) ────────────────────────────────────────────────────────
def upload_index_release(
    manifest_path: Path,
    chunks_jsonl_path: Path,
    include_zip: bool = False,
    keep: int = 2,
    build_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    manifest.json + chunks.jsonl.gz 업로드, 최신 keep개만 보존.
    """
    repo = _repo()
    tag  = f"index-{__import__('time').strftime('%Y%m%d-%H%M%S')}"
    name = f"MAIC Index {__import__('time').strftime('%Y-%m-%d %H:%M')}"
    body = json.dumps({
        "meta": build_meta or {},
    }, ensure_ascii=False, indent=2)

    # 1) 릴리스 생성
    res = requests.post(f"{API}/repos/{repo}/releases", headers=_headers(), json={
        "tag_name": tag, "name": name, "body": body, "draft": False, "prerelease": False
    })
    res.raise_for_status()
    release = res.json()
    upload_url = release["upload_url"].split("{")[0]

    # 2) 자산 업로드
    assets = []

    # manifest.json
    with open(manifest_path, "rb") as f:
        r = requests.post(
            f"{upload_url}?name=manifest.json", headers=_headers(binary=True), data=f.read()
        )
        r.raise_for_status(); assets.append("manifest.json")

    # chunks.jsonl.gz (필요 시 gz 생성)
    gz_path = chunks_jsonl_path.with_suffix(chunks_jsonl_path.suffix + ".gz")
    if not gz_path.exists() or gz_path.stat().st_mtime < chunks_jsonl_path.stat().st_mtime:
        with open(chunks_jsonl_path, "rb") as fr, gzip.open(gz_path, "wb", compresslevel=6) as fw:
            shutil.copyfileobj(fr, fw)
    with open(gz_path, "rb") as f:
        r = requests.post(
            f"{upload_url}?name=chunks.jsonl.gz", headers=_headers(binary=True), data=f.read()
        )
        r.raise_for_status(); assets.append("chunks.jsonl.gz")

    # (옵션) zip 자산
    if include_zip:
        zip_file = Path(PERSIST_DIR) / f"{tag}.zip"  # PERSIST_DIR가 없다면 스킵
        if zip_file.exists():
            with open(zip_file, "rb") as f:
                r = requests.post(
                    f"{upload_url}?name={zip_file.name}",
                    headers=_headers(binary=True), data=f.read()
                )
                r.raise_for_status(); assets.append(zip_file.name)

    # 3) keep 정책: 오래된 릴리스 삭제
    _apply_keep_policy(repo, keep)

    return {"ok": True, "tag": tag, "assets": assets}

def _apply_keep_policy(repo: str, keep: int) -> None:
    try:
        res = requests.get(f"{API}/repos/{repo}/releases", headers=_headers())
        res.raise_for_status()
        releases = res.json()
        for rel in releases[keep:]:
            try:
                requests.delete(f"{API}/repos/{repo}/releases/{rel['id']}", headers=_headers())
                # 태그도 삭제
                tag = rel.get("tag_name")
                if tag:
                    requests.delete(f"{API}/repos/{repo}/git/refs/tags/{tag}", headers=_headers())
            except Exception:
                pass
    except Exception:
        pass

# ── 조회/복원 유틸(신규) ────────────────────────────────────────────────────
def get_latest_release() -> Optional[Dict[str, Any]]:
    repo = _repo()
    res = requests.get(f"{API}/repos/{repo}/releases/latest", headers=_headers())
    if res.status_code == 404:
        return None
    res.raise_for_status()
    return res.json()

def _find_asset(release: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for a in release.get("assets", []) or []:
        if a.get("name") == name:
            return a
    return None

def _download_asset(asset: Dict[str, Any]) -> bytes:
    # assets_url 대신 "url"(assets API)로 Accept: application/octet-stream
    url = asset.get("url")
    r = requests.get(url, headers=_headers(binary=True), allow_redirects=True)
    r.raise_for_status()
    return r.content

def fetch_manifest_from_release(release: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    a = _find_asset(release, "manifest.json")
    if not a: return None
    data = _download_asset(a)
    try:
        return json.loads(data.decode("utf-8", errors="ignore"))
    except Exception:
        return None

def restore_latest(dest_dir: Path) -> bool:
    """
    최신 릴리스의 manifest.json, chunks.jsonl.gz를 내려받아 로컬 persist에 복원.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    rel = get_latest_release()
    if not rel: return False

    a_manifest = _find_asset(rel, "manifest.json")
    a_chunks_gz = _find_asset(rel, "chunks.jsonl.gz")
    if not (a_manifest and a_chunks_gz): return False

    # manifest
    m_bytes = _download_asset(a_manifest)
    (dest_dir / "manifest.json").write_bytes(m_bytes)

    # chunks.gz → chunks.jsonl
    gz_bytes = _download_asset(a_chunks_gz)
    (dest_dir / "chunks.jsonl.gz").write_bytes(gz_bytes)
    try:
        with gzip.open(io.BytesIO(gz_bytes), "rb") as fr:
            (dest_dir / "chunks.jsonl").write_bytes(fr.read())
    except Exception:
        # gz 해제가 안 되면 gz 파일만 남겨두고 실패 처리
        return False

    # .ready 마커는 호출측에서 찍음
    return True
# [01]===== src/backup/github_release.py — END ===================================
