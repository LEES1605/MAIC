# ======================== [01] imports & constants — START ========================
from __future__ import annotations

import gzip
import io
import json
import os
import shutil
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ASCII only. No unicode ellipsis or special quotes.
API: str = "https://api.github.com"
UA: str = "MAIC-backup-client/1.0"
# ========================= [01] imports & constants — END =========================


# ===================== [02] logging & env helpers — START ========================
def _log(msg: str) -> None:
    """Minimal stdout logger. Do not print secrets."""
    try:
        print(f"[github_release] {msg}")
    except Exception:
        pass


def _get_env(name: str, default: str = "") -> str:
    """ENV first. If missing, try src.core.secret.get(name)."""
    val = os.getenv(name, "")
    if val:
        return val
    try:
        # optional dependency; must not fail hard
        from src.core import secret as _sec  # type: ignore[import-not-found]
        v2 = _sec.get(name, default)  # type: ignore[attr-defined]
        if isinstance(v2, str) and v2:
            return v2
    except Exception:
        return default
    return default


def _token() -> str:
    return _get_env("GH_TOKEN") or _get_env("GITHUB_TOKEN")


def _resolve_owner_repo() -> Tuple[str, str]:
    """
    Resolve owner/repo using:
      1) GITHUB_REPO = 'owner/repo'
      2) (GH_OWNER|GITHUB_OWNER) + (GH_REPO|GITHUB_REPO_NAME)
    """
    combo = _get_env("GITHUB_REPO")
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        return o.strip(), r.strip()
    owner = _get_env("GH_OWNER") or _get_env("GITHUB_OWNER")
    repo = _get_env("GH_REPO") or _get_env("GITHUB_REPO_NAME")
    return owner.strip(), repo.strip()


def _repo() -> str:
    o, r = _resolve_owner_repo()
    return f"{o}/{r}" if o and r else ""


def _branch() -> str:
    """
    Prefer CI provided branch name.
    Fallback to 'main'.
    """
    return _get_env("GITHUB_REF_NAME", "main") or "main"


def _headers() -> Dict[str, str]:
    hdr = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    tok = _token()
    if tok:
        hdr["Authorization"] = f"token {tok}"
    return hdr


def _upload_headers(content_type: str) -> Dict[str, str]:
    hdr = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    tok = _token()
    if tok:
        hdr["Authorization"] = f"token {tok}"
    if content_type:
        hdr["Content-Type"] = content_type
    return hdr
# ====================== [02] logging & env helpers — END =========================


# ====================== [03] fs, safety, extractors — START ======================
def _ensure_dir(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _norm_join(base: Path, member: str) -> Path:
    """
    Safe join that prevents path traversal.
    Reject absolute and parent-escaping members.
    """
    rel = Path(member)
    if rel.is_absolute():
        raise ValueError("absolute path not allowed")
    norm = (base / rel).resolve()
    if not str(norm).startswith(str(base.resolve())):
        raise ValueError("path traversal detected")
    return norm


def _safe_extractall_tar(tf: tarfile.TarFile, dest_dir: Path,
                         members: Iterable[tarfile.TarInfo] | None = None) -> None:
    """
    Extract tar members safely:
      - block absolute paths and parent traversal
      - skip symlink and hardlink entries
    """
    base = dest_dir.resolve()
    for m in (members or tf.getmembers()):
        name = m.name or ""
        if m.islnk() or m.issym():
            # skip links
            continue
        target = _norm_join(base, name)
        if m.isdir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            _ensure_dir(target.parent)
            with tf.extractfile(m) as src, open(target, "wb") as out:
                if src:
                    shutil.copyfileobj(src, out)


def _is_zip_symlink(zinfo: zipfile.ZipInfo) -> bool:
    """
    Detect symlink entry on Unix zip archives using external_attr.
    """
    # upper 16 bits contain Unix mode
    mode = (zinfo.external_attr >> 16) & 0o777777
    return (mode & 0o170000) == 0o120000  # S_IFLNK


def _safe_extractall_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    base = dest_dir.resolve()
    for zinfo in zf.infolist():
        name = zinfo.filename
        if not name or name.endswith("/"):
            # directory or empty entry
            try:
                _norm_join(base, name.rstrip("/"))
                (base / name).mkdir(parents=True, exist_ok=True)
            except Exception:
                continue
            continue
        if _is_zip_symlink(zinfo):
            # skip symlinks
            continue
        try:
            target = _norm_join(base, name)
        except Exception:
            continue
        _ensure_dir(target.parent)
        with zf.open(zinfo, "r") as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def _decompress_gz(gz_path: Path, out_path: Path) -> bool:
    try:
        with gzip.open(gz_path, "rb") as g, open(out_path, "wb") as o:
            shutil.copyfileobj(g, o)
        return True
    except Exception as e:
        _log(f"gz decompress failed: {type(e).__name__}: {e}")
        return False


def _merge_dir_jsonl(folder: Path, target_file: Path) -> bool:
    """
    Merge all *.jsonl files under a folder into one file.
    """
    files = sorted(folder.rglob("*.jsonl"))
    if not files:
        return False
    try:
        _ensure_dir(target_file.parent)
        with open(target_file, "wb") as out:
            for p in files:
                with open(p, "rb") as f:
                    shutil.copyfileobj(f, out)
        return True
    except Exception as e:
        _log(f"merge jsonl failed: {type(e).__name__}: {e}")
        return False


def _size(p: Path) -> int:
    try:
        return int(p.stat().st_size)
    except Exception:
        return 0
# ======================= [03] fs, safety, extractors — END =======================


# ======================== [04] GitHub API helpers — START ========================
def _latest_release(repo: str) -> Optional[Dict[str, Any]]:
    """
    Query /repos/{repo}/releases/latest.
    """
    if not repo:
        _log("GITHUB_REPO is not set")
        return None
    try:
        import requests  # lazy import
    except Exception:
        _log("requests module is missing")
        return None
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
    if not assets:
        return None
    # prefer index_*.zip, else first zip, else first tar.gz, else any jsonl(.gz)
    def name_of(a: Dict[str, Any]) -> str:
        return str(a.get("name") or "")

    def score(a: Dict[str, Any]) -> Tuple[int, int]:
        n = name_of(a).lower()
        if n.startswith("index_") and n.endswith(".zip"):
            return (4, -len(n))
        if n.endswith(".zip"):
            return (3, -len(n))
        if n.endswith(".tar.gz"):
            return (2, -len(n))
        if n.endswith(".jsonl") or n.endswith(".jsonl.gz"):
            return (1, -len(n))
        return (0, -len(n))

    assets_sorted = sorted(assets, key=score, reverse=True)
    return assets_sorted[0] if assets_sorted else None


def _download_asset(asset: Dict[str, Any]) -> Optional[bytes]:
    """
    Download asset content. Use browser_download_url when present; otherwise use API url
    with octet-stream accept header.
    """
    try:
        import requests
    except Exception:
        _log("requests module is missing")
        return None

    bdl = asset.get("browser_download_url")
    if bdl:
        try:
            r = requests.get(str(bdl), headers=_headers(), timeout=60)
            if r.status_code == 200:
                return r.content
        except Exception as e:
            _log(f"asset download failed: {type(e).__name__}: {e}")
            return None

    api_url = asset.get("url")
    if not api_url:
        return None
    try:
        hdrs = dict(_headers())
        hdrs["Accept"] = "application/octet-stream"
        r = requests.get(str(api_url), headers=hdrs, timeout=60)
        if r.status_code == 200:
            return r.content
    except Exception as e:
        _log(f"asset api download failed: {type(e).__name__}: {e}")
    return None
# ========================= [04] GitHub API helpers — END =========================


# ========================= [05] restore_latest — START ==========================
def restore_latest(dest_dir: str | Path) -> bool:
    """
    Download the latest release asset that looks like index, then restore into dest_dir.

    Steps:
      1) fetch latest release
      2) pick best asset (index_*.zip preferred)
      3) download and extract safely
      4) flatten single top-level dir if exists
      5) materialize chunks.jsonl (merge or decompress if needed)
      6) mark ready
    """
    dest = Path(dest_dir).expanduser().resolve()
    _ensure_dir(dest)

    repo = _repo()
    if not repo:
        _log("restore_latest: repo is not resolved")
        return False

    rel = _latest_release(repo)
    if not rel:
        _log("restore_latest: no latest release")
        return False

    asset = _pick_best_asset(rel)
    if not asset:
        _log("restore_latest: no downloadable asset in release")
        return False

    data = _download_asset(asset)
    if not data:
        _log("restore_latest: asset download returned empty")
        return False

    # Write to a temp path
    tmp_root = dest / f"__restore_{int(time.time())}"
    _ensure_dir(tmp_root)
    tmp_file = tmp_root / "asset.bin"
    try:
        tmp_file.write_bytes(data)
    except Exception as e:
        _log(f"restore_latest: write temp failed: {e}")
        return False

    # Extract by type
    try:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(tmp_file, "r") as zf:
                _safe_extractall_zip(zf, tmp_root)
        elif name.endswith(".tar.gz"):
            with tarfile.open(tmp_file, "r:gz") as tf:
                _safe_extractall_tar(tf, tmp_root, None)
        elif name.endswith(".jsonl.gz"):
            ok = _decompress_gz(tmp_file, dest / "chunks.jsonl")
            if not ok:
                return False
        elif name.endswith(".jsonl"):
            # direct file
            shutil.copy2(tmp_file, dest / "chunks.jsonl")
        else:
            # Try zip anyway
            try:
                with zipfile.ZipFile(tmp_file, "r") as zf:
                    _safe_extractall_zip(zf, tmp_root)
            except Exception:
                pass
    except Exception as e:
        _log(f"restore_latest: extract failed: {e}")
        return False

    # If we extracted directory content, pick best folder as root
    chunks_file = dest / "chunks.jsonl"
    if not (chunks_file.exists() and _size(chunks_file) > 0):
        # choose a folder that contains index content
        candidates = list(tmp_root.iterdir())
        src_root = tmp_root
        if len(candidates) == 1 and candidates[0].is_dir():
            src_root = candidates[0]

        # If chunks.jsonl is not at top, try common locations
        best = None
        for p in src_root.rglob("chunks.jsonl"):
            best = p
            break
        if best:
            _ensure_dir(dest)
            shutil.copy2(best, dest / "chunks.jsonl")
        else:
            # Try .gz then chunks/ directory
            gz = next(src_root.rglob("chunks.jsonl.gz"), None)
            if gz and _decompress_gz(gz, dest / "chunks.jsonl"):
                pass
            else:
                cdir = next(src_root.rglob("chunks"), None)
                if cdir and cdir.is_dir():
                    _merge_dir_jsonl(cdir, dest / "chunks.jsonl")

    # Mark ready via core if available
    try:
        from src.core.index_probe import mark_ready as _mark  # type: ignore
        _mark(dest)
    except Exception:
        try:
            (dest / ".ready").write_text("ok", encoding="utf-8")
        except Exception:
            pass

    # Clean up tmp
    try:
        shutil.rmtree(tmp_root, ignore_errors=True)
    except Exception:
        pass

    ok = (dest / "chunks.jsonl").exists() and _size(dest / "chunks.jsonl") > 0
    if ok:
        _log("restore_latest: completed")
    else:
        _log("restore_latest: chunks.jsonl is missing or empty")
    return ok
# ========================== [05] restore_latest — END ===========================


# ========================= [06] publish_backup — START ==========================
def publish_backup(persist_dir: str | Path,
                   tag: Optional[str] = None,
                   keep_last: int = 5) -> bool:
    """
    Create or get a release, then upload chunks.jsonl.gz and manifest.json.

    The function is resilient:
      - If requests is missing, returns False without raising.
      - If token or repo is missing, returns False.
    """
    try:
        import requests  # lazy import
    except Exception:
        _log("publish_backup: requests module is missing")
        return False

    persist = Path(persist_dir).expanduser().resolve()
    chunks = persist / "chunks.jsonl"
    if not chunks.exists() or _size(chunks) == 0:
        _log("publish_backup: chunks.jsonl is missing or empty")
        return False

    repo = _repo()
    if not repo:
        _log("publish_backup: repo is not resolved")
        return False

    mode = (_get_env("MAIC_INDEX_MODE", "STD") or "STD").upper()
    build_id = time.strftime("%Y%m%d-%H%M%S")
    rel_tag = tag or f"index-{build_id}"
    rel_name = rel_tag

    manifest_obj: Dict[str, Any] = {
        "build_id": build_id,
        "mode": mode,
        "repo": repo,
        "branch": _branch(),
        "size_bytes": _size(chunks),
        "persist": str(persist),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    session = requests.Session()
    session.headers.update(_headers())

    # Create or get release
    release: Dict[str, Any]
    try:
        r = session.post(
            f"{API}/repos/{repo}/releases",
            json={
                "tag_name": rel_tag,
                "name": rel_name,
                "target_commitish": _branch(),
                "body": "Automated MAIC index backup",
            },
            timeout=30,
        )
        if r.status_code not in (201, 422):
            _log(f"publish_backup: release create failed: {r.status_code} {r.text}")
            return False
        if r.status_code == 201:
            release = r.json()
        else:
            rr = session.get(
                f"{API}/repos/{repo}/releases/tags/{rel_tag}", timeout=15
            )
            if rr.status_code != 200:
                _log(
                    "publish_backup: release lookup failed: "
                    f"{rr.status_code} {rr.text}"
                )
                return False
            release = rr.json()
    except Exception as e:
        _log(f"publish_backup: release create/lookup error: {e}")
        return False

    upload_url = release.get("upload_url", "")
    rel_id = release.get("id")
    if not upload_url or not rel_id:
        _log("publish_backup: missing upload_url or id")
        return False

    # Upload chunks.jsonl.gz
    try:
        gz = io.BytesIO()
        with open(chunks, "rb") as f, gzip.GzipFile(fileobj=gz, mode="wb") as g:
            shutil.copyfileobj(f, g)
        gz.seek(0)
        asset_name = "chunks.jsonl.gz"
        urla = (
            f"https://uploads.github.com/repos/{repo}/releases/{rel_id}/assets"
            f"?name={asset_name}"
        )
        ra = session.post(
            urla,
            data=gz.getvalue(),
            headers=_upload_headers("application/gzip"),
            timeout=60,
        )
        if ra.status_code == 422:
            # asset exists: delete and retry once
            assets = session.get(
                f"{API}/repos/{repo}/releases/{rel_id}/assets", timeout=15
            ).json()
            old = next((a for a in assets if a.get("name") == asset_name), None)
            if old and old.get("id"):
                session.delete(
                    f"{API}/repos/{repo}/releases/assets/{old['id']}", timeout=15
                )
                ra = session.post(
                    urla,
                    data=gz.getvalue(),
                    headers=_upload_headers("application/gzip"),
                    timeout=60,
                )
        if ra.status_code not in (201, 200):
            _log(f"publish_backup: chunks upload failed: {ra.status_code} {ra.text}")
            return False
    except Exception as e:
        _log(f"publish_backup: chunks upload error: {e}")
        return False

    # Upload manifest.json
    try:
        m_name = "manifest.json"
        urlm = (
            f"https://uploads.github.com/repos/{repo}/releases/{rel_id}/assets"
            f"?name={m_name}"
        )
        rb = session.post(
            urlm,
            data=json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
            headers=_upload_headers("application/json"),
            timeout=30,
        )
        if rb.status_code == 422:
            assets = session.get(
                f"{API}/repos/{repo}/releases/{rel_id}/assets", timeout=15
            ).json()
            old = next((a for a in assets if a.get("name") == m_name), None)
            if old and old.get("id"):
                session.delete(
                    f"{API}/repos/{repo}/releases/assets/{old['id']}", timeout=15
                )
                rb = session.post(
                    urlm,
                    data=json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
                    headers=_upload_headers("application/json"),
                    timeout=30,
                )
        if rb.status_code not in (201, 200):
            _log(f"publish_backup: manifest upload failed: {rb.status_code} {rb.text}")
            return False
    except Exception as e:
        _log(f"publish_backup: manifest upload error: {e}")
        return False

    # Retention: keep last N index-* releases
    try:
        page = 1
        all_rel: List[Dict[str, Any]] = []
        while True:
            rr = session.get(
                f"{API}/repos/{repo}/releases",
                params={"per_page": 100, "page": page},
                timeout=15,
            )
            if rr.status_code != 200:
                break
            batch = rr.json() or []
            if not batch:
                break
            all_rel.extend(batch)
            page += 1

        index_rel = [
            r for r in all_rel if str(r.get("tag_name") or "").startswith("index-")
        ]
        index_rel.sort(
            key=lambda r: str(r.get("created_at") or ""), reverse=True
        )
        for r in index_rel[keep_last:]:
            rid = r.get("id")
            tname = r.get("tag_name")
            if rid:
                session.delete(f"{API}/repos/{repo}/releases/{rid}", timeout=15)
            if tname:
                session.delete(
                    f"{API}/repos/{repo}/git/refs/tags/{tname}", timeout=15
                )
    except Exception as e:
        _log(f"publish_backup: retention error (ignored): {e}")

    _log(f"publish_backup: done, tag={rel_tag}, repo={repo}")
    return True
# ========================== [06] publish_backup — END ===========================


# ============================ [07] module api — START ============================
__all__ = [
    "restore_latest",
    "publish_backup",
]
# ============================= [07] module api — END =============================
