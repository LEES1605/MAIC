# File: src/backup/github_release.py
# [1] imports_and_constants - START
from __future__ import annotations

import gzip
import io
import json
import os
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

API = "https://api.github.com"
# [1] imports_and_constants - END


# [2] logging_and_env_helpers - START
def _log(msg: str) -> None:
    """Simple, safe logger. No secrets."""
    try:
        print(f"[backup] {msg}")
    except Exception:
        pass


def _get_env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    if isinstance(v, str) and v:
        return v
    return default


def _token() -> str:
    """Try core secret helper first, then env."""
    try:
        from src.core.secret import token as _tok  # type: ignore[attr-defined]
        t = _tok()
        if isinstance(t, str) and t:
            return t
    except Exception:
        pass
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = _get_env(k, "")
        if v:
            return v
    return ""


def _resolve_owner_repo() -> Tuple[str, str]:
    """Resolve owner/repo from secrets or env."""
    # Prefer core resolver if available
    try:
        from src.core.secret import (  # type: ignore[attr-defined]
            resolve_owner_repo as _res,
        )
        ow, rp = _res()
        if ow and rp:
            return ow, rp
    except Exception:
        pass

    combo = _get_env("GITHUB_REPO", "")
    if combo and "/" in combo:
        ow, rp = combo.split("/", 1)
        return ow.strip(), rp.strip()

    ow = _get_env("GH_OWNER", "") or _get_env("GITHUB_OWNER", "")
    rp = _get_env("GH_REPO", "") or _get_env("GITHUB_REPO_NAME", "")
    return (ow or "", rp or "")


def _repo() -> str:
    ow, rp = _resolve_owner_repo()
    return f"{ow}/{rp}" if ow and rp else ""


def _branch() -> str:
    return _get_env("GITHUB_REF_NAME", "main")


def _headers() -> Dict[str, str]:
    t = _token()
    h = {"Accept": "application/vnd.github+json"}
    if t:
        h["Authorization"] = f"token {t}"
    return h


def _upload_headers(content_type: str) -> Dict[str, str]:
    h = dict(_headers())
    if content_type:
        h["Content-Type"] = content_type
    return h
# [2] logging_and_env_helpers - END


# [3] http_helpers - START
def _get_json(url: str) -> Optional[Dict[str, Any]]:
    """GET url and parse JSON. Use requests if present, else urllib."""
    try:
        import requests  # type: ignore
        r = requests.get(url, headers=_headers(), timeout=20)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]
    except Exception:
        try:
            from urllib import request, error
            req = request.Request(url, headers=_headers())
            with request.urlopen(req, timeout=20) as resp:
                txt = resp.read().decode("utf-8", "ignore")
                return json.loads(txt)
        except Exception:
            return None


def _get_bytes(url: str) -> Optional[bytes]:
    """GET url and return bytes."""
    try:
        import requests  # type: ignore
        r = requests.get(url, headers=_headers(), timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        try:
            from urllib import request
            req = request.Request(url, headers=_headers())
            with request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception:
            return None
# [3] http_helpers - END


# [4] release_and_asset_selection - START
def _latest_release(repo: str) -> Optional[Dict[str, Any]]:
    if not repo:
        _log("latest_release: empty repo")
        return None
    url = f"{API}/repos/{repo}/releases/latest"
    return _get_json(url)


def _pick_best_asset(rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Heuristics:
      1) index_*.zip
      2) chunks.jsonl.gz
      3) chunks.jsonl
      4) *.zip
      5) *.tar.gz / *.tgz
    """
    assets = rel.get("assets") or []
    if not isinstance(assets, list):
        return None

    def _name(a: Dict[str, Any]) -> str:
        return str(a.get("name") or "")

    # 1) index_*.zip
    cand = [a for a in assets if _name(a).startswith("index_") and _name(a).endswith(".zip")]
    if cand:
        return cand[0]

    # 2) chunks.jsonl.gz
    cand = [a for a in assets if _name(a) == "chunks.jsonl.gz"]
    if cand:
        return cand[0]

    # 3) chunks.jsonl
    cand = [a for a in assets if _name(a) == "chunks.jsonl"]
    if cand:
        return cand[0]

    # 4) any .zip
    cand = [a for a in assets if _name(a).endswith(".zip")]
    if cand:
        return cand[0]

    # 5) tarballs
    cand = [a for a in assets if _name(a).endswith(".tar.gz") or _name(a).endswith(".tgz")]
    if cand:
        return cand[0]

    return assets[0] if assets else None
# [4] release_and_asset_selection - END


# [5] asset_download_and_extract - START
def _download_asset(asset: Dict[str, Any]) -> Optional[bytes]:
    """
    Try browser_download_url first.
    If missing, use API assets/:id with octet-stream Accept.
    """
    bdu = str(asset.get("browser_download_url") or "")
    if bdu:
        return _get_bytes(bdu)

    aid = asset.get("id")
    if aid is None:
        return None
    url = f"{API}/repos/{_repo()}/releases/assets/{aid}"
    try:
        import requests  # type: ignore
        hdrs = dict(_headers())
        hdrs["Accept"] = "application/octet-stream"
        r = requests.get(url, headers=hdrs, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception:
        try:
            from urllib import request
            req = request.Request(url, headers={"Accept": "application/octet-stream", **_headers()})
            with request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception:
            return None


def _safe_extract_zip(data: bytes, dest: Path) -> bool:
    dest = dest.resolve()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for m in zf.infolist():
                # path traversal guard
                target = (dest / m.filename).resolve()
                if not str(target).startswith(str(dest)):
                    raise RuntimeError("unsafe zip path")
            zf.extractall(dest)
        return True
    except Exception as e:
        _log(f"zip extract failed: {e}")
        return False


def _safe_extract_targz(data: bytes, dest: Path) -> bool:
    dest = dest.resolve()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                target = (dest / m.name).resolve()
                if not str(target).startswith(str(dest)):
                    raise RuntimeError("unsafe tar path")
            tf.extractall(dest)
        return True
    except Exception as e:
        _log(f"targz extract failed: {e}")
        return False


def _decompress_gz(src: Path, dst: Path) -> bool:
    try:
        with gzip.open(src, "rb") as rf, open(dst, "wb") as wf:
            while True:
                chunk = rf.read(64 * 1024)
                if not chunk:
                    break
                wf.write(chunk)
        return True
    except Exception as e:
        _log(f"gz decompress failed: {e}")
        return False


def _merge_dir_jsonl(src_dir: Path, dst: Path) -> bool:
    """
    Merge all *.jsonl under src_dir (one level) into dst.
    Files are concatenated in name order.
    """
    try:
        parts = sorted([p for p in src_dir.glob("*.jsonl") if p.is_file()], key=lambda p: p.name)
        if not parts:
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "wb") as wf:
            for p in parts:
                with open(p, "rb") as rf:
                    while True:
                        b = rf.read(256 * 1024)
                        if not b:
                            break
                        wf.write(b)
        return True
    except Exception as e:
        _log(f"jsonl merge failed: {e}")
        return False
# [5] asset_download_and_extract - END


# [6] restore_latest_public_api - START
def restore_latest(dest_dir: str | Path) -> bool:
    """
    Restore latest index release into dest_dir.
    Returns True on success.
    """
    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    repo = _repo()
    if not repo:
        _log("restore_latest: repo is empty")
        return False

    rel = _latest_release(repo)
    if not rel:
        _log("restore_latest: no release")
        return False

    asset = _pick_best_asset(rel)
    if not asset:
        _log("restore_latest: no asset")
        return False

    name = str(asset.get("name") or "")
    _log(f"restore_latest: asset={name}")

    data = _download_asset(asset)
    if not data:
        _log("restore_latest: download failed")
        return False

    ok = False
    if name.endswith(".zip"):
        ok = _safe_extract_zip(data, dest)
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        ok = _safe_extract_targz(data, dest)
    elif name.endswith(".jsonl.gz"):
        tmp = dest / "chunks.jsonl.gz"
        tmp.write_bytes(data)
        ok = _decompress_gz(tmp, dest / "chunks.jsonl")
    elif name.endswith(".jsonl"):
        (dest / "chunks.jsonl").write_bytes(data)
        ok = True
    else:
        # try zip as fallback
        ok = _safe_extract_zip(data, dest)

    if not ok:
        _log("restore_latest: extract failed")
        return False

    # locate chunks.jsonl possibly under a subfolder
    cj = dest / "chunks.jsonl"
    if not cj.exists() or cj.stat().st_size == 0:
        try:
            found = next(dest.glob("**/chunks.jsonl"))
            if found and found != cj:
                # adopt subfolder as root (copy file up)
                (dest / "chunks.jsonl").write_bytes(found.read_bytes())
                _log(f"restore_latest: adopted {found.parent}")
        except StopIteration:
            pass

    if not cj.exists() or cj.stat().st_size == 0:
        # try to merge from directory named chunks
        d = dest / "chunks"
        if d.exists() and d.is_dir():
            if not _merge_dir_jsonl(d, cj):
                _log("restore_latest: merge from chunks/ failed")
                return False

    # mark ready
    ready = dest / ".ready"
    try:
        ready.write_text("ok", encoding="utf-8")
    except Exception:
        pass

    _log("restore_latest: done")
    return True
# [6] restore_latest_public_api - END


# [7] optional_publish_api - START
def publish_backup(persist_dir: str | Path, keep_last: int = 3) -> bool:
    """
    Publish current chunks.jsonl and manifest to a GitHub release.
    This is optional; safe no-op on missing token or repo.
    """
    t = _token()
    repo = _repo()
    if not (t and repo):
        _log("publish_backup: missing token or repo")
        return False

    p = Path(persist_dir).expanduser().resolve()
    cj = p / "chunks.jsonl"
    if not cj.exists() or cj.stat().st_size == 0:
        _log("publish_backup: chunks.jsonl missing")
        return False

    import tempfile
    tag = f"index-{int(time.time())}"
    zip_name = f"{tag}.zip"
    with tempfile.TemporaryDirectory() as tmpd:
        zpath = Path(tmpd) / zip_name
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(str(p)):
                for fn in files:
                    fp = Path(root) / fn
                    rel = fp.relative_to(p)
                    zf.write(str(fp), arcname=str(rel))

        # create or get release by tag
        import urllib.parse as up
        get_url = f"{API}/repos/{repo}/releases/tags/{up.quote(tag)}"
        rel = _get_json(get_url)
        if not rel:
            payload = json.dumps(
                {
                    "tag_name": tag,
                    "name": tag,
                    "target_commitish": _branch(),
                    "body": "MAIC index backup",
                }
            ).encode("utf-8")
            try:
                import requests  # type: ignore
                r = requests.post(
                    f"{API}/repos/{repo}/releases",
                    headers=_upload_headers("application/json"),
                    data=payload,
                    timeout=30,
                )
                rel = r.json()
            except Exception:
                rel = _get_json(f"{API}/repos/{repo}/releases")

        rid = rel.get("id") if isinstance(rel, dict) else None
        if not rid:
            _log("publish_backup: release id missing")
            return False

        # upload asset
        try:
            from urllib import request
            up_url = (
                f"https://uploads.github.com/repos/{repo}/releases/{rid}/assets"
                f"?name={zip_name}"
            )
            req = request.Request(
                up_url,
                data=zpath.read_bytes(),
                headers=_upload_headers("application/zip"),
                method="POST",
            )
            with request.urlopen(req, timeout=180) as resp:
                _ = resp.read()
        except Exception as e:
            _log(f"publish_backup: upload failed: {e}")
            return False

    # retention: best effort
    try:
        rels = _get_json(f"{API}/repos/{repo}/releases") or {}
        lst = rels if isinstance(rels, list) else []
        if len(lst) > keep_last:
            # delete older ones
            for r in lst[keep_last:]:
                rid = r.get("id")
                tname = r.get("tag_name")
                if not rid:
                    continue
                from urllib import request
                request.Request(
                    f"{API}/repos/{repo}/releases/{rid}", headers=_headers(), method="DELETE"
                )
                if tname:
                    request.Request(
                        f"{API}/repos/{repo}/git/refs/tags/{tname}",
                        headers=_headers(),
                        method="DELETE",
                    )
    except Exception:
        pass

    _log(f"publish_backup: complete tag={tag}")
    return True
# [7] optional_publish_api - END
