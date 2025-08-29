# ===================== src/backup/github_release.py — START ==================
from __future__ import annotations
import os, io, json, gzip, shutil, time
from pathlib import Path
from typing import Any, Dict, Optional, List
import requests

try:
    import streamlit as st  # type: ignore
except Exception:
    st = None

API = "https://api.github.com"

def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = st.secrets.get(name) if st else None  # type: ignore
        if val is None:
            return os.getenv(name, default)
        if isinstance(val, str):
            return val
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

def _log(msg: str) -> None:
    try:
        if st: st.write(msg)  # type: ignore
    except Exception:
        pass
    print(msg)

# ── Upload release ───────────────────────────────────────────────────────────
def upload_index_release(
    manifest_path: Path,
    chunks_jsonl_path: Path,
    include_zip: bool = False,
    keep: int = 2,
    build_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    repo = _repo()
    tag  = f"index-{time.strftime('%Y%m%d-%H%M%S')}"
    name = f"MAIC Index {time.strftime('%Y-%m-%d %H:%M')}"
    body = json.dumps({"meta": build_meta or {}}, ensure_ascii=False, indent=2)

    _log(f"[release] creating: {repo} tag={tag}")
    res = requests.post(f"{API}/repos/{repo}/releases", headers=_headers(), json={
        "tag_name": tag, "name": name, "body": body, "draft": False, "prerelease": False
    })
    res.raise_for_status()
    release = res.json()
    upload_url = release["upload_url"].split("{")[0]

    assets: List[str] = []

    # manifest.json
    _log("[release] uploading asset: manifest.json")
    with open(manifest_path, "rb") as f:
        r = requests.post(f"{upload_url}?name=manifest.json", headers=_headers(True), data=f.read())
        r.raise_for_status(); assets.append("manifest.json")

    # chunks.jsonl.gz
    gz_path = chunks_jsonl_path.with_suffix(chunks_jsonl_path.suffix + ".gz")
    if not gz_path.exists() or gz_path.stat().st_mtime < chunks_jsonl_path.stat().st_mtime:
        _log("[release] gzipping chunks.jsonl → chunks.jsonl.gz")
        with open(chunks_jsonl_path, "rb") as fr, gzip.open(gz_path, "wb", compresslevel=6) as fw:
            shutil.copyfileobj(fr, fw)
    _log("[release] uploading asset: chunks.jsonl.gz")
    with open(gz_path, "rb") as f:
        r = requests.post(f"{upload_url}?name=chunks.jsonl.gz", headers=_headers(True), data=f.read())
        r.raise_for_status(); assets.append("chunks.jsonl.gz")

    # (optional) additional zip
    if include_zip:
        zip_path = chunks_jsonl_path.parent / f"{tag}.zip"
        if zip_path.exists():
            _log(f"[release] uploading asset: {zip_path.name}")
            with open(zip_path, "rb") as f:
                r = requests.post(f"{upload_url}?name={zip_path.name}", headers=_headers(True), data=f.read())
                r.raise_for_status(); assets.append(zip_path.name)

    # keep policy
    _apply_keep_policy(repo, keep)

    _log(f"[release] ✅ done: {tag} / {assets}")
    return {"ok": True, "tag": tag, "assets": assets}

def _apply_keep_policy(repo: str, keep: int) -> None:
    try:
        res = requests.get(f"{API}/repos/{repo}/releases", headers=_headers())
        res.raise_for_status()
        releases = res.json()
        if len(releases) > keep:
            for rel in releases[keep:]:
                rid = rel.get("id"); tag = rel.get("tag_name")
                _log(f"[release] deleting old release: {tag} ({rid})")
                try:
                    requests.delete(f"{API}/repos/{repo}/releases/{rid}", headers=_headers())
                except Exception as e:
                    _log(f"[release][warn] delete release failed: {e}")
                if tag:
                    try:
                        requests.delete(f"{API}/repos/{repo}/git/refs/tags/{tag}", headers=_headers())
                    except Exception as e:
                        _log(f"[release][warn] delete tag failed: {e}")
    except Exception as e:
        _log(f"[release][warn] keep-policy failed: {e}")

# ── Fetch/restore ────────────────────────────────────────────────────────────
def get_latest_release() -> Optional[Dict[str, Any]]:
    repo = _repo()
    r = requests.get(f"{API}/repos/{repo}/releases/latest", headers=_headers())
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def _find_asset(release: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for a in release.get("assets", []) or []:
        if a.get("name") == name:
            return a
    return None

def _download_asset(asset: Dict[str, Any]) -> bytes:
    url = asset.get("url")
    r = requests.get(url, headers=_headers(True), allow_redirects=True, timeout=60)
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
    dest_dir.mkdir(parents=True, exist_ok=True)
    rel = get_latest_release()
    if not rel: 
        _log("[restore] no releases")
        return False

    a_m = _find_asset(rel, "manifest.json")
    a_c = _find_asset(rel, "chunks.jsonl.gz")
    if not (a_m and a_c):
        _log("[restore] missing assets in latest release")
        return False

    # manifest
    m_bytes = _download_asset(a_m)
    (dest_dir / "manifest.json").write_bytes(m_bytes)

    # chunks.gz → chunks.jsonl
    gz_bytes = _download_asset(a_c)
    (dest_dir / "chunks.jsonl.gz").write_bytes(gz_bytes)
    try:
        import io as _io
        with gzip.open(_io.BytesIO(gz_bytes), "rb") as fr:
            (dest_dir / "chunks.jsonl").write_bytes(fr.read())
    except Exception as e:
        _log(f"[restore][warn] gunzip failed: {e}")
        return False

    return True
# ====================== src/backup/github_release.py — END ===================
