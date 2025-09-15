# ========================= [01] imports & constants — START =========================
from __future__ import annotations

import io
import json
import os
import stat
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib import error as _urlerr
from urllib import parse as _urlp
from urllib import request as _urlq

API_BASE = "https://api.github.com"
UPLOAD_BASE = "https://uploads.github.com"
# ========================== [01] imports & constants — END ==========================



# ========================= [02] logging & env helpers — START =======================
def _log(msg: str) -> None:
    """Non-sensitive console log. ASCII only."""
    try:
        print(f"[github_release] {msg}")
    except Exception:
        pass


def _get_env(name: str, default: str = "") -> str:
    """Read env first; try Streamlit secrets if available."""
    v = os.getenv(name, "")
    if v:
        return v
    # optional: streamlit secrets (safe and best-effort)
    try:
        import streamlit as st  # type: ignore[import-not-found]
        s = st.secrets.get(name)
        if isinstance(s, str) and s:
            return s
    except Exception:
        pass
    return default


def _resolve_owner_repo() -> Tuple[str, str]:
    """
    Resolve (owner, repo) from common env/secrets.
    Priority:
      1) GITHUB_REPO = "owner/repo"
      2) GH_OWNER + GH_REPO
      3) GITHUB_OWNER + GITHUB_REPO_NAME
    """
    combo = _get_env("GITHUB_REPO", "")
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        return o.strip(), r.strip()

    ow = _get_env("GH_OWNER", "") or _get_env("GITHUB_OWNER", "")
    rp = _get_env("GH_REPO", "") or _get_env("GITHUB_REPO_NAME", "")
    return ow.strip(), rp.strip()


def _repo() -> str:
    """Return 'owner/repo' or empty string."""
    ow, rp = _resolve_owner_repo()
    if ow and rp:
        return f"{ow}/{rp}"
    return ""


def _branch() -> str:
    """Best-effort current branch for tag target."""
    # CI: GITHUB_REF_NAME exists on GitHub Actions
    ref = os.getenv("GITHUB_REF_NAME", "")
    if ref:
        return ref
    # default
    return "main"


def _headers() -> Dict[str, str]:
    """Default GitHub API headers with token if present."""
    tok = _get_env("GH_TOKEN") or _get_env("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"token {tok}"
    return h


def _upload_headers(content_type: str) -> Dict[str, str]:
    h = _headers()
    h["Content-Type"] = content_type
    return h
# ========================== [02] logging & env helpers — END ========================


# ========================= [03] http helpers (urllib) — START =======================
@dataclass
class HttpResp:
    status_code: int
    text: str
    data: Optional[Dict[str, Any]] = None
    content: Optional[bytes] = None


def _http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None,
               headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> HttpResp:
    data_bytes: Optional[bytes] = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = dict(headers or {})
        headers["Content-Type"] = "application/json"

    req = _urlq.Request(url, data=data_bytes, method=method.upper())
    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        with _urlq.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            txt = raw.decode("utf-8", "ignore")
            try:
                obj = json.loads(txt)
            except Exception:
                obj = None
            return HttpResp(status_code=getattr(resp, "status", 200), text=txt, data=obj)
    except _urlerr.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return HttpResp(status_code=e.code, text=body, data=None)
    except Exception as e:
        return HttpResp(status_code=599, text=str(e), data=None)


def _http_bin(method: str, url: str, data: Optional[bytes] = None,
              headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> HttpResp:
    req = _urlq.Request(url, data=data, method=method.upper())
    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        with _urlq.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return HttpResp(status_code=getattr(resp, "status", 200), text="", content=raw)
    except _urlerr.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return HttpResp(status_code=e.code, text=body, content=None)
    except Exception as e:
        return HttpResp(status_code=599, text=str(e), content=None)
# ========================== [03] http helpers (urllib) — END ========================


# ========================= [04] release discovery — START ===========================
def _latest_release(repo: str) -> Optional[Dict[str, Any]]:
    """Return latest release JSON or None."""
    if not repo:
        _log("GITHUB_REPO is empty.")
        return None
    url = f"{API_BASE}/repos/{repo}/releases/latest"
    r = _http_json("GET", url, headers=_headers(), timeout=20)
    if r.status_code == 200 and isinstance(r.data, dict):
        return r.data
    _log(f"latest release query failed: {r.status_code}")
    return None


def _pick_asset(rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick best asset: prefer index_*.zip, then .tar.gz, then chunks.jsonl(.gz)."""
    assets = rel.get("assets") or []
    best = None
    for a in assets:
        n = str(a.get("name") or "")
        if n.startswith("index_") and n.endswith(".zip"):
            return a
    for a in assets:
        n = str(a.get("name") or "")
        if n.startswith("index_") and (n.endswith(".tar.gz") or n.endswith(".tgz")):
            return a
    for a in assets:
        n = str(a.get("name") or "")
        if n.endswith("chunks.jsonl.gz") or n.endswith("chunks.jsonl"):
            best = a
            break
    return best


def _download_asset(asset: Dict[str, Any]) -> Optional[Tuple[str, bytes]]:
    """
    Download asset bytes.
    For assets API, use 'Accept: application/octet-stream' when needed.
    Return (name, bytes) or None.
    """
    name = str(asset.get("name") or "")
    url = str(asset.get("browser_download_url") or asset.get("url") or "")
    if not url:
        return None

    hdrs = _headers()
    # If it's the assets API URL, switch Accept
    if "releases/assets/" in url and "browser_download_url" not in asset:
        hdrs = dict(hdrs)
        hdrs["Accept"] = "application/octet-stream"

    rr = _http_bin("GET", url, headers=hdrs, timeout=60)
    if rr.status_code in (200, 302) and rr.content is not None:
        return name, rr.content
    _log(f"asset download failed: {rr.status_code}")
    return None
# ========================== [04] release discovery — END ============================
# ========================= [05] extraction helpers — START ==========================
def _is_safe_member(base: Path, target: Path) -> bool:
    """Prevent path traversal and absolute extraction."""
    try:
        b = base.resolve()
        t = target.resolve()
        # dest 자체거나 하위여야 함
        return (t == b) or (str(t).startswith(str(b) + os.sep))
    except Exception:
        return False


def _safe_extract_zip(zdata: bytes, dest_dir: Path) -> bool:
    """
    Safely extract ZIP bytes into dest_dir.
    - 경로 탈출 방지, 파일 수/총 바이트 상한, 디렉터리/일반파일만 허용
    """
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        max_files = 10000
        max_bytes = 512 * 1024 * 1024  # 512MB
        total = 0

        with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
            members = zf.infolist()
            if len(members) > max_files:
                _log(f"zip blocked: too many members ({len(members)})")
                return False

            for m in members:
                name = m.filename
                if not name:
                    continue

                # 디렉터리?
                if name.endswith("/"):
                    target_dir = (dest_dir / name).resolve()
                    if not _is_safe_member(dest_dir, target_dir):
                        _log(f"zip path blocked: {name}")
                        return False
                    target_dir.mkdir(parents=True, exist_ok=True)
                    continue

                target = (dest_dir / name).resolve()
                if not _is_safe_member(dest_dir, target):
                    _log(f"zip path blocked: {name}")
                    return False

                data = zf.read(m)
                total += len(data)
                if total > max_bytes:
                    _log("zip blocked: size budget exceeded")
                    return False

                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as out:
                    out.write(data)
        return True
    except Exception as e:
        _log(f"zip extract failed: {e}")
        return False


def _safe_extract_tar(tdata: bytes, dest_dir: Path) -> bool:
    """
    Safely extract TAR/TGZ bytes into dest_dir.
    - 경로 탈출 방지(절대/상위 경로 금지)
    - 링크/디바이스 항목 차단(issym/islnk/isdev)
    - 디렉터리/일반파일만 허용
    - 파일 수/총 바이트 상한
    """
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        max_files = 10000
        max_bytes = 512 * 1024 * 1024  # 512MB
        total = 0

        with tarfile.open(fileobj=io.BytesIO(tdata), mode="r:*") as tf:
            members = tf.getmembers()
            if len(members) > max_files:
                _log(f"tar blocked: too many members ({len(members)})")
                return False

            for m in members:
                name = m.name or ""
                if not name:
                    continue

                # 링크/디바이스 차단
                if m.issym() or m.islnk() or m.isdev():
                    _log(f"tar blocked: link/dev entry {name}")
                    return False

                target = (dest_dir / name).resolve()
                if not _is_safe_member(dest_dir, target):
                    _log(f"tar path blocked: {name}")
                    return False

                if m.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                if not m.isfile():
                    _log(f"tar blocked: unsupported type {name}")
                    return False

                f = tf.extractfile(m)
                if f is None:
                    _log(f"tar blocked: unreadable file {name}")
                    return False
                data = f.read() or b""
                total += len(data)
                if total > max_bytes:
                    _log("tar blocked: size budget exceeded")
                    return False

                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as out:
                    out.write(data)
        return True
    except Exception as e:
        _log(f"tar extract failed: {e}")
        return False


def _write_bytes(path: Path, data: bytes) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return True
    except Exception as e:
        _log(f"write failed: {e}")
        return False


def _find_chunks(root: Path) -> Optional[Path]:
    """Find chunks.jsonl possibly nested."""
    try:
        # prefer root first
        p = root / "chunks.jsonl"
        if p.exists() and p.stat().st_size > 0:
            return p
        # nested
        for cand in root.rglob("chunks.jsonl"):
            if cand.stat().st_size > 0:
                return cand
    except Exception as e:
        _log(f"find_chunks failed: {e}")
    return None
# ========================== [05] extraction helpers — END ===========================

# ========================= [06] PUBLIC API: restore_latest — START ===================
def restore_latest(dest_dir: str | Path, repo: Optional[str] = None) -> bool:
    """
    Restore latest index artifact into dest_dir.
    - Supports index_*.zip / *.tar.gz / chunks.jsonl(.gz)
    - Marks '.ready' when chunks.jsonl exists
    """
    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    target_repo = (repo or _repo()).strip()
    if not target_repo:
        _log("restore_latest: repo is empty.")
        return False

    rel = _latest_release(target_repo)
    if not rel:
        return False

    asset = _pick_asset(rel)
    if not asset:
        _log("restore_latest: no suitable asset.")
        return False

    got = _download_asset(asset)
    if not got:
        return False
    name, data = got

    ok = False
    lname = name.lower()
    if lname.endswith(".zip"):
        ok = _safe_extract_zip(data, dest)
    elif lname.endswith(".tar.gz") or lname.endswith(".tgz"):
        ok = _safe_extract_tar(data, dest)
    elif lname.endswith(".jsonl.gz"):
        # naive gunzip
        try:
            import gzip  # stdlib
            chunks = dest / "chunks.jsonl"
            with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gz:
                raw = gz.read()
            ok = _write_bytes(chunks, raw)
        except Exception as e:
            _log(f"gunzip failed: {e}")
            ok = False
    elif lname.endswith(".jsonl"):
        ok = _write_bytes(dest / "chunks.jsonl", data)
    else:
        _log(f"restore_latest: unsupported asset {name}")
        ok = False

    if not ok:
        return False

    # flatten when artifact created a top folder
    chunks = _find_chunks(dest)
    if chunks and chunks.parent != dest:
        # move file into dest
        try:
            target = dest / "chunks.jsonl"
            target.write_bytes(chunks.read_bytes())
            _log(f"flatten: adopted chunks from {chunks.parent.name}")
        except Exception as e:
            _log(f"flatten failed: {e}")
            return False

    # mark ready
    try:
        (dest / ".ready").write_text("ok", encoding="utf-8")
    except Exception as e:
        _log(f"mark ready failed: {e}")

    _log("restore_latest: done.")
    return True
# ========================== [06] PUBLIC API: restore_latest — END ====================


# ========================= [07] PUBLIC API: publish_backup — START ===================
def _zip_dir(src: Path, out_zip: Path) -> bool:
    try:
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(str(src)):
                for fn in files:
                    p = Path(root) / fn
                    arc = p.relative_to(src)
                    zf.write(str(p), arcname=str(arc))
        return True
    except Exception as e:
        _log(f"zip build failed: {e}")
        return False


def publish_backup(persist_dir: str | Path, repo: Optional[str] = None,
                   tag: Optional[str] = None, name: Optional[str] = None,
                   body: str = "Automated MAIC index") -> bool:
    """
    Zip persist_dir and upload as release asset.
    - Creates release when missing.
    - Uses token from GH_TOKEN/GITHUB_TOKEN.
    """
    base = Path(persist_dir).expanduser().resolve()
    if not base.exists():
        _log("publish_backup: persist_dir missing.")
        return False

    target_repo = (repo or _repo()).strip()
    if not target_repo:
        _log("publish_backup: repo is empty.")
        return False

    # Build zip
    backups = base / "backups"
    zpath = backups / f"index_{int(time.time())}.zip"
    if not _zip_dir(base, zpath):
        return False

    # Create or get release
    tag = tag or f"index-{int(time.time())}"
    rel_name = name or tag

    # Try to fetch by tag
    ow, rp = _resolve_owner_repo()
    get_url = f"{API_BASE}/repos/{ow}/{rp}/releases/tags/{_urlp.quote(tag)}"
    r = _http_json("GET", get_url, headers=_headers(), timeout=20)
    if r.status_code != 200:
        # create release
        payload = {
            "tag_name": tag,
            "name": rel_name,
            "target_commitish": _branch(),
            "body": body,
        }
        r = _http_json("POST", f"{API_BASE}/repos/{ow}/{rp}/releases",
                       payload=payload, headers=_headers(), timeout=30)
        if r.status_code not in (201, 200):
            _log(f"publish_backup: create release failed {r.status_code}")
            return False

    rel = r.data or {}
    rid = rel.get("id")
    if not rid:
        _log("publish_backup: missing release id.")
        return False

    # Upload asset
    up_url = (
        f"{UPLOAD_BASE}/repos/{ow}/{rp}/releases/{rid}/assets"
        f"?name={_urlp.quote(zpath.name)}"
    )
    up = _http_bin("POST", up_url, data=zpath.read_bytes(),
                   headers=_upload_headers("application/zip"), timeout=180)
    if up.status_code not in (201, 200):
        # If asset exists (422), attempt to delete then re-upload
        if up.status_code == 422:
            # list assets
            la = _http_json("GET",
                            f"{API_BASE}/repos/{ow}/{rp}/releases/{rid}/assets",
                            headers=_headers(), timeout=20)
            if la.status_code == 200 and isinstance(la.data, list):
                same = next((a for a in la.data if a.get("name") == zpath.name), None)
                if same and same.get("id"):
                    aid = same["id"]
                    _http_json("DELETE",
                               f"{API_BASE}/repos/{ow}/{rp}/releases/assets/{aid}",
                               headers=_headers(), timeout=20)
                    # retry upload
                    up = _http_bin("POST", up_url, data=zpath.read_bytes(),
                                   headers=_upload_headers("application/zip"),
                                   timeout=180)
        if up.status_code not in (201, 200):
            _log(f"publish_backup: upload failed {up.status_code}")
            return False

    _log(f"publish_backup: done tag={tag}")
    return True
# ========================== [07] PUBLIC API: publish_backup — END ====================


# ========================= [08] module exports — START ==============================
__all__ = ["restore_latest", "publish_backup"]
# ========================== [08] module exports — END ===============================
