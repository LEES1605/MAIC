# [01] START
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
import io
import json
import os
import shutil
import tarfile
import time
import zipfile

# ---- constants --------------------------------------------------------------
API = "https://api.github.com"


# ---- logging (safe, no external deps) --------------------------------------
def _log(msg: str) -> None:
    """Minimal logger (stdout only, secrets must not be printed)."""
    try:
        print(f"[github_release] {msg}")
    except Exception:
        pass


# ---- environment helpers ---------------------------------------------------
def _get_env(key: str, default: str = "") -> str:
    """Read from env; optionally fall back to Streamlit secrets when available."""
    val = os.getenv(key, default)
    if val:
        return val
    # Optional: streamlit secrets, but do not hard-import at module import time
    try:
        import streamlit as st  # type: ignore
        v = st.secrets.get(key)
        if isinstance(v, str):
            return v
    except Exception:
        pass
    return default


def _headers() -> Dict[str, str]:
    tok = (
        _get_env("GH_TOKEN")
        or _get_env("GITHUB_TOKEN")
        or ""
    )
    hdr = {"Accept": "application/vnd.github+json"}
    if tok:
        hdr["Authorization"] = f"token {tok}"
    return hdr


def _upload_headers(content_type: str) -> Dict[str, str]:
    hdr = _headers()
    hdr["Content-Type"] = content_type
    return hdr


def _repo() -> str:
    """
    Resolve owner/repo string.
    Priority:
      1) GITHUB_REPO ("owner/repo")
      2) GH_OWNER + GH_REPO
      3) GITHUB_OWNER + GITHUB_REPO_NAME
    """
    r = _get_env("GITHUB_REPO", "")
    if r and "/" in r:
        return r
    o = _get_env("GH_OWNER", "") or _get_env("GITHUB_OWNER", "")
    n = _get_env("GH_REPO", "") or _get_env("GITHUB_REPO_NAME", "")
    if o and n:
        return f"{o.strip()}/{n.strip()}"
    return ""


def _branch() -> str:
    return (
        _get_env("GITHUB_REF_NAME", "")
        or _get_env("BRANCH_NAME", "")
        or "main"
    )


def _size(p: Path) -> int:
    try:
        return int(p.stat().st_size)
    except Exception:
        return 0


# [01] END

# [02] START
# ---- tar/zip extraction with path safety -----------------------------------
def _safe_extractall(
    tf: tarfile.TarFile,
    dest_dir: Path,
    members: Iterable[tarfile.TarInfo] | None = None,
) -> None:
    base = dest_dir.resolve()
    for m in (members or tf.getmembers()):
        # Block absolute paths and path traversal
        name = m.name.lstrip("/")
        target = (base / name).resolve()
        if not str(target).startswith(str(base)):
            raise RuntimeError(f"blocked path: {m.name}")
        tf.extract(m, base)


def _extract_zip(data: bytes, dest: Path) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                # basic safety: no absolute or parent traversal
                name = info.filename.lstrip("/")
                target = (dest / name).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise RuntimeError(f"blocked path: {info.filename}")
            zf.extractall(dest)
        return True
    except Exception as e:
        _log(f"unzip failed: {type(e).__name__}: {e}")
        return False


def _extract_tar_gz(data: bytes, dest: Path) -> bool:
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            _safe_extractall(tf, dest, None)
        return True
    except Exception as e:
        _log(f"untar failed: {type(e).__name__}: {e}")
        return False


def _decompress_gz(src: Path, dst: Path) -> bool:
    try:
        import gzip

        with gzip.open(src, "rb") as rf, open(dst, "wb") as wf:
            shutil.copyfileobj(rf, wf)
        return True
    except Exception as e:
        _log(f"gunzip failed: {type(e).__name__}: {e}")
        return False
# [02] END

# [03] START
# ---- release queries --------------------------------------------------------
def _latest_release(repo: str) -> Optional[Dict[str, Any]]:
    if not repo:
        _log("GITHUB_REPO is not set")
        return None
    import requests  # local import

    url = f"{API}/repos/{repo}/releases/latest"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"latest release fetch failed: {type(e).__name__}: {e}")
        return None


def _pick_best_asset(rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    assets = rel.get("assets") or []
    # prefer index_*.zip, then chunks.jsonl(.gz), then any .zip
    def _score(a: Dict[str, Any]) -> Tuple[int, int]:
        name = str(a.get("name") or "").lower()
        if name.startswith("index_") and name.endswith(".zip"):
            return (3, len(name))
        if name.endswith("chunks.jsonl") or name.endswith("chunks.jsonl.gz"):
            return (2, len(name))
        if name.endswith(".zip") or name.endswith(".tar.gz"):
            return (1, len(name))
        return (0, len(name))

    if not assets:
        return None
    return max(assets, key=_score)


def _download_asset(asset: Dict[str, Any]) -> Optional[bytes]:
    import requests  # local import

    # Prefer browser_download_url when present
    dl = asset.get("browser_download_url")
    try:
        if dl:
            r = requests.get(dl, headers=_headers(), timeout=60)
            if r.status_code == 200:
                return r.content
        # Fallback: API asset url requires octet-stream
        url = asset.get("url")
        if url:
            hdrs = dict(_headers())
            hdrs["Accept"] = "application/octet-stream"
            r = requests.get(url, headers=hdrs, timeout=60)
            if r.status_code == 200:
                return r.content
    except Exception as e:
        _log(f"asset download failed: {type(e).__name__}: {e}")
    return None
# [03] END

# [04] START
# ---- content merge helpers --------------------------------------------------
def _merge_dir_jsonl(src_dir: Path, target_file: Path) -> bool:
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "wb") as wf:
            for p in sorted(src_dir.rglob("*.jsonl")):
                with open(p, "rb") as rf:
                    shutil.copyfileobj(rf, wf)
        return True
    except Exception as e:
        _log(f"merge dir jsonl failed: {type(e).__name__}: {e}")
        return False
# [04] END

# [05] START
# ---- public: restore latest -------------------------------------------------
def restore_latest(dest_dir: str | Path, *, flatten_single_folder: bool = True) -> bool:
    """
    Download the latest release asset and restore into dest_dir.

    Strategy:
      1) Find latest release.
      2) Pick best asset (index_*.zip preferred).
      3) Extract into a temp dir under dest_dir.
      4) If a single top-level folder exists, optionally flatten it.
      5) Try to materialize chunks.jsonl:
         - direct file in archive
         - chunks.jsonl.gz, gunzip
         - merge any */chunks/ subdir
      6) Mark .ready.
    """
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    repo = _repo()
    if not repo:
        _log("restore_latest: repo is not configured")
        return False

    rel = _latest_release(repo)
    if not rel:
        return False

    asset = _pick_best_asset(rel)
    if not asset:
        _log("restore_latest: no downloadable asset on release")
        return False

    name = str(asset.get("name") or "")
    _log(f"downloading asset: {name}")
    data = _download_asset(asset)
    if not data:
        return False

    tmp = dest / f"__restore_{int(time.time())}"
    tmp.mkdir(parents=True, exist_ok=True)

    ok_extract = False
    if name.endswith(".zip"):
        ok_extract = _extract_zip(data, tmp)
    elif name.endswith(".tar.gz"):
        ok_extract = _extract_tar_gz(data, tmp)
    else:
        # raw bytes: maybe chunks.jsonl(.gz)
        try:
            target = tmp / name
            target.write_bytes(data)
            ok_extract = True
        except Exception as e:
            _log(f"write raw asset failed: {type(e).__name__}: {e}")
            ok_extract = False

    if not ok_extract:
        return False

    # flatten single top folder
    src_root = tmp
    children = [p for p in tmp.iterdir() if p.name != "__MACOSX"]
    if flatten_single_folder and len(children) == 1 and children[0].is_dir():
        src_root = children[0]
        _log(f"flatten: using {src_root.name} as root")

    # try to materialize chunks.jsonl
    target_chunks = dest / "chunks.jsonl"
    ok_cons = False

    # case A: explicit chunks.jsonl
    any_jsonl = list(src_root.rglob("chunks.jsonl"))
    if any_jsonl:
        best = max(any_jsonl, key=_size)
        shutil.copy2(best, target_chunks)
        _log(f"used chunks.jsonl: {best}")
        ok_cons = True

    # case B: chunks.jsonl.gz
    if not ok_cons:
        any_gz = list(src_root.rglob("chunks.jsonl.gz"))
        if any_gz:
            best_gz = max(any_gz, key=_size)
            ok_cons = _decompress_gz(best_gz, target_chunks)
            if ok_cons:
                _log(f"used chunks.jsonl.gz: {best_gz}")

    # case C: chunks directory
    if not ok_cons:
        chunk_dirs = [d for d in src_root.rglob("*") if d.is_dir() and d.name == "chunks"]
        for d in chunk_dirs:
            if _merge_dir_jsonl(d, target_chunks):
                _log(f"used chunks dir: {d}")
                ok_cons = True
                break

    # case D: any .jsonl as fallback
    if not ok_cons:
        any_jsonl2 = [p for p in src_root.rglob("*.jsonl")]
        if any_jsonl2:
            best_any = max(any_jsonl2, key=_size)
            shutil.copy2(best_any, target_chunks)
            _log(f"used fallback jsonl: {best_any}")
            ok_cons = True

    if not ok_cons:
        _log("failed to create chunks.jsonl")
        return False

    # mark ready
    try:
        (dest / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass

    _log("restore complete")
    return True
# [05] END

# [06] START
# ---- public: publish backup -------------------------------------------------
def publish_backup(dest_dir: str | Path) -> bool:
    """
    Upload chunks.jsonl and manifest.json to GitHub release as assets.
    - Requires GH_TOKEN or GITHUB_TOKEN, and repo config.
    - Creates a release if tag does not exist.
    - Replaces assets with the same name.
    """
    import requests  # local import
    from urllib.parse import quote

    chunks = Path(dest_dir) / "chunks.jsonl"
    if not chunks.exists() or _size(chunks) == 0:
        _log("publish_backup: chunks.jsonl is missing or empty")
        return False

    repo = _repo()
    if not repo:
        _log("publish_backup: repo is not configured")
        return False

    tag = f"index-{time.strftime('%Y%m%d-%H%M%S')}"
    rel_name = tag
    session = requests.Session()
    session.headers.update(_headers())

    # ensure release
    r = session.get(f"{API}/repos/{repo}/releases/tags/{quote(tag)}", timeout=15)
    if r.status_code == 404:
        payload = {
            "tag_name": tag,
            "name": rel_name,
            "target_commitish": _branch(),
            "body": "Automated index backup",
        }
        r = session.post(f"{API}/repos/{repo}/releases", json=payload, timeout=30)
        if r.status_code not in (201, 422):
            _log(f"create release failed: {r.status_code} {r.text}")
            return False
        if r.status_code == 422:
            # possibly created concurrently; fetch again
            r = session.get(
                f"{API}/repos/{repo}/releases/tags/{quote(tag)}", timeout=15
            )
    rel = r.json()
    rid = rel.get("id")
    upload_url = rel.get("upload_url", "").split("{", 1)[0]
    if not rid or not upload_url:
        _log("publish_backup: missing release id or upload_url")
        return False

    # upload chunks.jsonl (gzip for size)
    import gzip

    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb") as z:
        z.write(chunks.read_bytes())
    asset_name = "chunks.jsonl.gz"
    url = f"{upload_url}?name={quote(asset_name)}"
    ra = session.post(
        url,
        data=gz.getvalue(),
        headers=_upload_headers("application/gzip"),
        timeout=60,
    )
    if ra.status_code == 422:
        # delete old asset and retry
        assets = session.get(f"{API}/repos/{repo}/releases/{rid}/assets", timeout=15).json()
        old = next((a for a in assets if a.get("name") == asset_name), None)
        if old and old.get("id"):
            aid = old["id"]
            session.delete(f"{API}/repos/{repo}/releases/assets/{aid}", timeout=15)
            ra = session.post(
                url,
                data=gz.getvalue(),
                headers=_upload_headers("application/gzip"),
                timeout=60,
            )
    if ra.status_code not in (201, 200):
        _log(f"upload chunks failed: {ra.status_code} {ra.text}")
        return False

    # upload manifest.json (minimal)
    manifest = {
        "build_id": time.strftime("%Y%m%d-%H%M%S"),
        "mode": _get_env("MAIC_INDEX_MODE", "STD"),
        "persist": str(Path(dest_dir).resolve()),
        "files": ["chunks.jsonl.gz"],
    }
    m_name = "manifest.json"
    url2 = f"{upload_url}?name={quote(m_name)}"
    rm = session.post(
        url2,
        data=json.dumps(manifest).encode("utf-8"),
        headers=_upload_headers("application/json"),
        timeout=30,
    )
    if rm.status_code == 422:
        assets = session.get(f"{API}/repos/{repo}/releases/{rid}/assets", timeout=15).json()
        old = next((a for a in assets if a.get("name") == m_name), None)
        if old and old.get("id"):
            aid = old["id"]
            session.delete(f"{API}/repos/{repo}/releases/assets/{aid}", timeout=15)
            rm = session.post(
                url2,
                data=json.dumps(manifest).encode("utf-8"),
                headers=_upload_headers("application/json"),
                timeout=30,
            )
    if rm.status_code not in (201, 200):
        _log(f"upload manifest failed: {rm.status_code} {rm.text}")
        return False

    _log(f"publish complete: tag={tag}, repo={repo}")
    return True
# [06] END
