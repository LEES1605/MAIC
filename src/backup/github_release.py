# ========================== [01] imports & constants — START ==========================
from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import time
import zipfile
from gzip import GzipFile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

API = "https://api.github.com"

# 금칙문자 규정: 유니코드 말줄임표(…) 금지. ASCII "..."만 사용.
# =========================== [01] imports & constants — END ===========================


# =============================== [02] logging — START =================================
def _log(msg: str) -> None:
    """stderr/runner 콘솔로만 간단히 출력(민감정보 금지)."""
    try:
        print(f"[backup] {msg}")
    except Exception:
        pass
# ================================ [02] logging — END ==================================


# ============================== [03] env helpers — START ===============================
def _get_env(name: str, default: str = "") -> str:
    v = os.getenv(name, default)
    return v if isinstance(v, str) else default


def _headers() -> Dict[str, str]:
    tok = _get_env("GH_TOKEN") or _get_env("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"token {tok}"
    return h


def _upload_headers(content_type: str) -> Dict[str, str]:
    h = dict(_headers())
    if content_type:
        h["Content-Type"] = content_type
    return h


def _branch() -> str:
    return _get_env("GITHUB_REF_NAME", "main")


def _repo() -> str:
    """owner/repo 문자열을 환경변수/조합으로 해석."""
    combo = _get_env("GITHUB_REPO")
    if combo and "/" in combo:
        return combo.strip()
    owner = _get_env("GH_OWNER") or _get_env("GITHUB_OWNER")
    repo = _get_env("GH_REPO") or _get_env("GITHUB_REPO_NAME")
    return f"{owner}/{repo}".strip("/ ")
# =============================== [03] env helpers — END ================================


# ====================== [04] safe extract & decompress — START ========================
def _safe_extractall(tf: tarfile.TarFile, dest_dir: Path,
                     members: Iterable[tarfile.TarInfo] | None = None) -> None:
    """tarfile.extractall 대체: 절대경로/상위탈출/링크 차단."""
    dest = Path(dest_dir).resolve()
    for m in (members or tf.getmembers()):
        name = Path(m.name)
        if name.is_absolute():
            continue
        target = (dest / name).resolve()
        if not str(target).startswith(str(dest)):
            continue
        # 심볼릭/하드 링크 차단
        if getattr(m, "issym", False) and m.issym():
            continue
        if getattr(m, "islnk", False) and m.islnk():
            continue
        tf.extract(m, dest)


def _decompress_gz(gz_path: Path, target_file: Path) -> bool:
    try:
        with open(gz_path, "rb") as rf, open(target_file, "wb") as wf:
            with GzipFile(fileobj=rf) as gzf:
                shutil.copyfileobj(gzf, wf)
        return True
    except Exception as e:
        _log(f"gz decompress failed: {type(e).__name__}: {e}")
        return False
# ======================= [04] safe extract & decompress — END =========================


# ============================== [05] release API — START ==============================
def _latest_release(repo: str) -> Optional[Dict[str, Any]]:
    if not repo:
        _log("GITHUB_REPO is not set.")
        return None
    import urllib.request as rq
    import urllib.error as er

    url = f"{API}/repos/{repo}/releases/latest"
    req = rq.Request(url, headers=_headers())
    try:
        with rq.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except er.HTTPError as e:
        _log(f"latest release http error: {e.code}")
        return None
    except Exception as e:
        _log(f"latest release error: {type(e).__name__}: {e}")
        return None


def get_latest_release(repo: str | None = None) -> Optional[Dict[str, Any]]:
    return _latest_release((repo or _repo()).strip())
# =============================== [05] release API — END ===============================


# =========================== [06] asset download — START ==============================
def _download_asset(asset: Dict[str, Any]) -> Optional[bytes]:
    import urllib.request as rq
    import urllib.error as er

    # 우선순위: browser_download_url → api url(assets/:id)
    dl = str(asset.get("browser_download_url") or "")
    if dl:
        req = rq.Request(dl, headers=_headers())
        try:
            with rq.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            _log(f"download via browser url failed: {e}")
            return None

    url = str(asset.get("url") or "")
    if not url:
        return None
    req = rq.Request(url, headers={**_headers(), "Accept": "application/octet-stream"})
    try:
        with rq.urlopen(req, timeout=60) as resp:
            return resp.read()
    except er.HTTPError as e:
        _log(f"asset api http error: {e.code}")
    except Exception as e:
        _log(f"asset download error: {e}")
    return None
# ============================ [06] asset download — END ===============================


# ============================= [07] pick asset — START ================================
def _size_of_asset(a: Dict[str, Any]) -> int:
    try:
        return int(a.get("size") or 0)
    except Exception:
        return 0


def _pick_best_asset(rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """index_*.zip 가장 선호, 없으면 .jsonl(.gz) 크기 최대를 선택."""
    assets = list(rel.get("assets") or [])
    if not assets:
        return None

    zips = [a for a in assets if str(a.get("name") or "").endswith(".zip")]
    zips = [a for a in zips if str(a.get("name") or "").startswith("index_")]
    if zips:
        return max(zips, key=_size_of_asset)

    jsonl = [a for a in assets if str(a.get("name") or "").endswith(".jsonl")]
    if jsonl:
        return max(jsonl, key=_size_of_asset)

    gz = [a for a in assets if str(a.get("name") or "").endswith(".jsonl.gz")]
    if gz:
        return max(gz, key=_size_of_asset)

    return max(assets, key=_size_of_asset)
# ============================== [07] pick asset — END =================================


# =========================== [08] restore_latest — START ==============================
def restore_latest(dest_dir: str | os.PathLike[str]) -> bool:
    """최신 릴리스의 인덱스 자산을 받아 dest_dir에 복원."""
    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    repo = _repo()
    if not repo:
        _log("restore_latest: GITHUB_REPO missing")
        return False

    rel = _latest_release(repo)
    if not rel:
        _log("restore_latest: no latest release")
        return False

    asset = _pick_best_asset(rel)
    if not asset:
        _log("restore_latest: no downloadable asset")
        return False

    data = _download_asset(asset)
    if not data:
        _log("restore_latest: failed to download asset")
        return False

    # 임시 저장
    name = str(asset.get("name") or "index_asset")
    tmp = dest / f"__restore_{int(time.time())}_{name}"
    tmp.write_bytes(data)

    # 압축 포맷별 해제
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(tmp, "r") as zf:
                zf.extractall(dest)
        elif name.endswith(".tar.gz"):
            with tarfile.open(tmp, "r:gz") as tf:
                _safe_extractall(tf, dest)
        elif name.endswith(".jsonl.gz"):
            target = dest / "chunks.jsonl"
            if not _decompress_gz(tmp, target):
                return False
        elif name.endswith(".jsonl"):
            target = dest / "chunks.jsonl"
            target.write_bytes(data)
        else:
            # 알 수 없는 포맷: 원본 남김
            _log(f"restore_latest: unknown format {name}")
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    # 평탄화: 하위 폴더에만 결과가 있는 경우 감지
    cj = dest / "chunks.jsonl"
    if not (cj.exists() and cj.stat().st_size > 0):
        try:
            cand = next(dest.glob("**/chunks.jsonl"))
            if cand != cj:
                # 내부 구조를 루트로 승격 (파일 단위 복사)
                src_root = cand.parent
                for p in src_root.rglob("*"):
                    relp = p.relative_to(src_root)
                    target = dest / relp
                    if p.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, target)
        except StopIteration:
            pass

    _log("restore_latest: done")
    return True
# ============================ [08] restore_latest — END ===============================


# =========================== [09] publish_backup — START ==============================
def publish_backup(persist_dir: str | os.PathLike[str]) -> bool:
    """
    persist_dir 내의 chunks.jsonl(필수)과 manifest(json)를 릴리스에 업로드.
    - 릴리스 태그: index-YYYYmmdd-HHMMSS
    """
    import urllib.request as rq
    import urllib.parse as ps
    import urllib.error as er

    chunks = Path(persist_dir).expanduser().resolve() / "chunks.jsonl"
    if not (chunks.exists() and chunks.stat().st_size > 0):
        _log("publish_backup: chunks.jsonl missing or empty")
        return False

    repo = _repo()
    tok = _get_env("GH_TOKEN") or _get_env("GITHUB_TOKEN")
    if not (repo and tok):
        _log("publish_backup: GH token or repo missing")
        return False

    tag = f"index-{time.strftime('%Y%m%d-%H%M%S')}"
    rel_name = tag
    manifest_obj: Dict[str, Any] = {
        "mode": (_get_env("MAIC_INDEX_MODE", "STD") or "STD").upper(),
        "build_id": time.strftime("%Y%m%d-%H%M%S"),
        "ready": True,
    }

    # 릴리스 생성 또는 조회
    try:
        # /releases/tags/:tag 조회
        url_get = f"{API}/repos/{repo}/releases/tags/{ps.quote(tag)}"
        req = rq.Request(url_get, headers=_headers())
        try:
            with rq.urlopen(req, timeout=15) as resp:
                rel = json.loads(resp.read().decode("utf-8", "ignore"))
        except er.HTTPError as e:
            if e.code != 404:
                _log(f"publish_backup: get release http {e.code}")
                return False
            # 생성
            payload = json.dumps(
                {"tag_name": tag, "name": rel_name, "target_commitish": _branch()}
            ).encode("utf-8")
            reqc = rq.Request(
                f"{API}/repos/{repo}/releases",
                data=payload,
                headers=_upload_headers("application/json"),
                method="POST",
            )
            with rq.urlopen(reqc, timeout=30) as resp:
                rel = json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception as e:
        _log(f"publish_backup: create/get release failed: {e}")
        return False

    rel_id = rel.get("id")
    if not rel_id:
        _log("publish_backup: no release id")
        return False

    # assets 업로드
    up_base = f"https://uploads.github.com/repos/{repo}/releases/{rel_id}/assets"

    def _upload(name: str, data: bytes, ctype: str) -> bool:
        url = f"{up_base}?name={ps.quote(name)}"
        req = rq.Request(url, data=data, headers=_upload_headers(ctype), method="POST")
        try:
            with rq.urlopen(req, timeout=180) as resp:
                resp.read()
            return True
        except er.HTTPError as e:
            # 이미 있는 경우(422) 삭제 후 재시도
            if e.code == 422:
                # 목록 조회
                req_l = rq.Request(f"{API}/repos/{repo}/releases/{rel_id}/assets",
                                   headers=_headers())
                with rq.urlopen(req_l, timeout=15) as rs:
                    assets = json.loads(rs.read().decode("utf-8", "ignore"))
                old = next((a for a in assets if a.get("name") == name), None)
                if old:
                    aid = old.get("id")
                    if aid:
                        rq.Request(
                            f"{API}/repos/{repo}/releases/assets/{aid}",
                            headers=_headers(),
                            method="DELETE",
                        )
                # 재시도
                req2 = rq.Request(url, data=data,
                                  headers=_upload_headers(ctype), method="POST")
                with rq.urlopen(req2, timeout=180) as rs2:
                    rs2.read()
                return True
            _log(f"publish_backup: upload {name} http {e.code}")
            return False
        except Exception as ex:
            _log(f"publish_backup: upload {name} failed: {ex}")
            return False

    # chunks 업로드
    if not _upload("chunks.jsonl.gz", _gzip_bytes(chunks.read_bytes()), "application/gzip"):
        return False
    # manifest 업로드
    if not _upload("manifest.json",
                   json.dumps(manifest_obj, ensure_ascii=False).encode("utf-8"),
                   "application/json"):
        return False

    _log(f"publish_backup: complete — tag={tag}")
    return True


def _gzip_bytes(raw: bytes) -> bytes:
    buf = io.BytesIO()
    with GzipFile(fileobj=buf, mode="wb") as gzf:
        gzf.write(raw)
    return buf.getvalue()
# ============================ [09] publish_backup — END ===============================
