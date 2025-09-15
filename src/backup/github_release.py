# ============================ [01] imports & constants — START ============================
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

API = "https://api.github.com"
# ============================= [01] imports & constants — END =============================


# ============================ [02] env & header helpers — START ===========================
def _log(msg: str) -> None:
    """모듈 내부 표준 로거(민감정보 금지)."""
    try:
        print(f"[backup] {msg}")
    except Exception:
        pass


def _get_env(name: str, default: str = "") -> str:
    v = os.getenv(name, default)
    return (v or "").strip()


def _token() -> str:
    return _get_env("GH_TOKEN") or _get_env("GITHUB_TOKEN")


def _repo() -> str:
    """
    owner/repo 문자열 계산.
    우선순위: GITHUB_REPO → (GH_OWNER|GITHUB_OWNER) + (GH_REPO|GITHUB_REPO_NAME)
    """
    combo = _get_env("GITHUB_REPO")
    if combo and "/" in combo:
        return combo

    owner = _get_env("GH_OWNER") or _get_env("GITHUB_OWNER")
    repo = _get_env("GH_REPO") or _get_env("GITHUB_REPO_NAME")
    if owner and repo:
        return f"{owner}/{repo}"
    return ""


def _branch() -> str:
    return _get_env("GITHUB_REF_NAME") or "main"


def _headers() -> Dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MAIC-backup/0.1",
    }
    t = _token()
    if t:
        h["Authorization"] = f"token {t}"
    return h


def _upload_headers(content_type: str) -> Dict[str, str]:
    h = dict(_headers())
    if content_type:
        h["Content-Type"] = content_type
    return h
# ============================= [02] env & header helpers — END ============================


# ================================ [03] http helpers — START ===============================
def _use_requests():
    try:
        import requests  # type: ignore
        return requests
    except Exception:
        return None


def _http_json(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Tuple[int, Any]:
    """requests 우선, 실패 시 urllib 폴백."""
    rq = _use_requests()
    if rq is not None:
        try:
            r = rq.request(method, url, headers=headers, json=payload, timeout=timeout)
            ct = r.headers.get("content-type", "")
            if "json" in ct.lower():
                return r.status_code, r.json()
            return r.status_code, {"_raw": r.text}
        except Exception as e:
            return 0, {"_error": str(e)}

    from urllib import error, request

    data_b = None
    if payload is not None:
        data_b = json.dumps(payload).encode("utf-8")
        headers = dict(headers or {})
        headers.setdefault("Content-Type", "application/json")

    req = request.Request(url, data=data_b, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode("utf-8", "ignore")
            try:
                return 200, json.loads(txt)
            except Exception:
                return 200, {"_raw": txt}
    except error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "ignore")
        except Exception:
            detail = ""
        return e.code, {"_error": f"HTTP {e.code}", "detail": detail}
    except Exception as e:
        return 0, {"_error": "network_error", "detail": str(e)}


def _http_bytes(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> bytes:
    rq = _use_requests()
    if rq is not None:
        try:
            r = rq.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception:
            return b""

    from urllib import request
    req = request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return b""
# ================================= [03] http helpers — END ================================


# ============================== [04] archive helpers — START ==============================
def _safe_extractall_tar(
    tf: tarfile.TarFile,
    dest_dir: Path,
    members: Iterable[tarfile.TarInfo] | None = None,
) -> None:
    """
    tar 안전 추출: 절대경로/상위탈출/심링크 차단.
    """
    dest_dir = Path(dest_dir).resolve()
    items = list(members) if members is not None else list(tf.getmembers())

    for m in items:
        name = m.name
        if not name:
            continue
        if name.startswith("/") or ".." in Path(name).parts:
            continue
        if getattr(m, "issym", lambda: False)() or getattr(m, "islnk", lambda: False)():
            continue
        target = dest_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        tf.extract(m, path=dest_dir)


def _extract_zip_bytes(data: bytes, dest: Path) -> bool:
    try:
        with io.BytesIO(data) as bio, zipfile.ZipFile(bio) as zf:
            # 경로 탈출 방지
            for n in zf.namelist():
                if n.startswith("/") or ".." in Path(n).parts:
                    continue
            zf.extractall(dest)
        return True
    except Exception as e:
        _log(f"unzip failed: {e}")
        return False


def _decompress_gz(src: Path, target: Path) -> bool:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(src, "rb") as rf, open(target, "wb") as wf:
            shutil.copyfileobj(rf, wf)
        return True
    except Exception as e:
        _log(f"gz decompress failed: {e}")
        return False


def _merge_dir_jsonl(dir_path: Path, target_file: Path) -> bool:
    """디렉터리 내부의 *.jsonl(.gz)들을 합쳐 단일 jsonl 생성."""
    cands = list(dir_path.glob("*.jsonl")) + list(dir_path.glob("*.jsonl.gz"))
    cands.sort(key=lambda p: p.name)

    if not cands:
        return False

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with target_file.open("wb") as wf:
            for p in cands:
                if p.suffix == ".gz":
                    with gzip.open(p, "rb") as rf:
                        shutil.copyfileobj(rf, wf)
                else:
                    with p.open("rb") as rf:
                        shutil.copyfileobj(rf, wf)
        return True
    except Exception as e:
        _log(f"merge dir jsonl failed: {e}")
        return False
# =============================== [04] archive helpers — END ===============================


# =============================== [05] release helpers — START =============================
def _latest_release(repo: str) -> Optional[Dict[str, Any]]:
    """가장 최신 릴리스 정보를 조회. 실패 시 None."""
    if not repo:
        _log("GITHUB_REPO가 설정되지 않았습니다.")
        return None
    code, body = _http_json("GET", f"{API}/repos/{repo}/releases/latest", _headers())
    if code == 200 and isinstance(body, dict):
        return body
    _log(f"latest release query failed: code={code}")
    return None


def _pick_best_asset(rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """다운로드 우선순위: index_*.zip > chunks.jsonl.gz > chunks.jsonl > 기타 zip."""
    assets = list(rel.get("assets") or [])

    def _name(a: Dict[str, Any]) -> str:
        return str(a.get("name") or "").lower()

    for a in assets:
        n = _name(a)
        if n.startswith("index_") and n.endswith(".zip"):
            return a
    for a in assets:
        n = _name(a)
        if n.endswith("chunks.jsonl.gz"):
            return a
    for a in assets:
        n = _name(a)
        if n.endswith("chunks.jsonl"):
            return a
    for a in assets:
        n = _name(a)
        if n.endswith(".zip"):
            return a
    return assets[0] if assets else None


def _download_asset(asset: Dict[str, Any], repo: str) -> Optional[bytes]:
    """자산 바이트 다운로드. browser_download_url 선호."""
    url = str(asset.get("browser_download_url") or "")
    hdrs = dict(_headers())
    if not url:
        aid = asset.get("id")
        if aid:
            url = f"{API}/repos/{repo}/releases/assets/{aid}"
            hdrs["Accept"] = "application/octet-stream"
    if not url:
        return None
    data = _http_bytes(url, hdrs)
    return data if data else None
# ================================ [05] release helpers — END ==============================


# ======================= [06] PUBLIC API: restore_latest — START ==========================
def restore_latest(dest_dir: str | Path) -> bool:
    """
    최신 릴리스에서 인덱스 산출물을 내려받아 복원합니다.
    - 우선 zip(index_*.zip) 추출 → 루트에 chunks.jsonl 없으면 하위 탐색
    - 다음 후보: chunks.jsonl.gz → 해제, chunks.jsonl → 복사
    - 성공 시 .ready 생성
    """
    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    repo = _repo()
    if not repo:
        _log("restore_latest: GITHUB_REPO 미설정")
        return False

    rel = _latest_release(repo)
    if rel is None:
        return False

    asset = _pick_best_asset(rel)
    if not asset:
        _log("restore_latest: 릴리스에 다운로드 가능한 자산이 없습니다.")
        return False

    name = str(asset.get("name") or "")
    _log(f"restore_latest: 선택 자산 = {name}")

    blob = _download_asset(asset, repo)
    if not blob:
        _log("restore_latest: 자산 다운로드 실패")
        return False

    # 1) zip 계열
    if name.endswith(".zip"):
        if not _extract_zip_bytes(blob, dest):
            return False
    # 2) tar.gz 계열
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        try:
            with io.BytesIO(blob) as bio, tarfile.open(fileobj=bio, mode="r:gz") as tf:
                _safe_extractall_tar(tf, dest)
        except Exception as e:
            _log(f"restore_latest: tar.gz 해제 실패: {e}")
            return False
    # 3) chunks.jsonl(.gz) 단일 파일
    elif name.endswith(".jsonl.gz"):
        tmp = dest / "__chunks.jsonl.gz"
        tmp.write_bytes(blob)
        if not _decompress_gz(tmp, dest / "chunks.jsonl"):
            return False
        try:
            tmp.unlink()
        except Exception:
            pass
    elif name.endswith(".jsonl"):
        (dest / "chunks.jsonl").write_bytes(blob)
    else:
        # 기타 확장자는 지원하지 않음
        _log("restore_latest: 지원하지 않는 자산 형식")
        return False

    # 산출물 보정: 루트에 없으면 하위 검색 후 승격 복사
    cj = dest / "chunks.jsonl"
    if not (cj.exists() and cj.stat().st_size > 0):
        try:
            cand = next(dest.glob("**/chunks.jsonl"))
            if cand != cj:
                target = cj
                target.write_bytes(cand.read_bytes())
        except StopIteration:
            _log("restore_latest: chunks.jsonl을 찾을 수 없습니다.")
            return False

    # ready 마킹
    try:
        (dest / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass

    _log("restore_latest: 완료")
    return True
# ======================== [06] PUBLIC API: restore_latest — END ===========================


# ======================= [07] PUBLIC API: publish_backup — START ==========================
def publish_backup(
    persist_dir: str | Path,
    *,
    keep_last_n: int = 5,
    tag_prefix: str = "index",
) -> bool:
    """
    persist_dir의 chunks.jsonl을 릴리스 자산으로 업로드합니다.
    - tag: {tag_prefix}-{YYYYmmdd-HHMMSS}
    - assets: chunks.jsonl.gz, manifest.json
    - keep_last_n 이후 릴리스는 보존 정책에 따라 정리(베스트에 가까운 구현)
    """
    p = Path(persist_dir).expanduser().resolve()
    chunks = p / "chunks.jsonl"
    if not chunks.exists() or chunks.stat().st_size == 0:
        _log("publish_backup: chunks.jsonl 이 없거나 비어 있습니다.")
        return False

    repo = _repo()
    if not repo:
        _log("publish_backup: GITHUB_REPO 미설정")
        return False

    mode = (_get_env("MAIC_INDEX_MODE", "STD") or "STD").upper()
    build_id = time.strftime("%Y%m%d-%H%M%S")
    tag = f"{tag_prefix}-{build_id}"
    manifest = {
        "mode": mode,
        "build_id": build_id,
        "branch": _branch(),
        "size_bytes": int(chunks.stat().st_size),
    }

    # release 생성 또는 조회
    status, body = _http_json(
        "POST",
        f"{API}/repos/{repo}/releases",
        _headers(),
        {
            "tag_name": tag,
            "name": tag,
            "target_commitish": _branch(),
            "body": "Automated index backup",
            "draft": False,
            "prerelease": False,
        },
        timeout=30,
    )
    if status not in (201, 422):
        _log(f"publish_backup: 릴리스 생성 실패: code={status}")
        return False

    if status == 422:
        # 이미 존재 → 조회
        st2, body2 = _http_json(
            "GET", f"{API}/repos/{repo}/releases/tags/{tag}", _headers(), None, 15
        )
        if st2 != 200 or not isinstance(body2, dict):
            _log(f"publish_backup: 기존 릴리스 조회 실패: code={st2}")
            return False
        rel_id = body2.get("id")
    else:
        rel_id = body.get("id")

    if not rel_id:
        _log("publish_backup: release id 없음")
        return False

    # 업로드 준비: gzip, manifest
    gz_buf = io.BytesIO()
    with open(chunks, "rb") as rf, gzip.GzipFile(fileobj=gz_buf, mode="wb") as gz:
        shutil.copyfileobj(rf, gz)
    data_gz = gz_buf.getvalue()
    man_bytes = json.dumps(manifest, ensure_ascii=False).encode("utf-8")

    # 업로드
    from urllib import parse, request

    def _upload(name: str, data: bytes, content_type: str) -> Tuple[int, Any]:
        url = (
            f"https://uploads.github.com/repos/{repo}/releases/{rel_id}/assets"
            f"?name={parse.quote(name)}"
        )
        req = request.Request(url, data=data, method="POST")
        hdrs = _upload_headers(content_type)
        for k, v in hdrs.items():
            req.add_header(k, v)
        try:
            with request.urlopen(req, timeout=120) as resp:
                txt = resp.read().decode("utf-8", "ignore")
                try:
                    return 201, json.loads(txt)
                except Exception:
                    return 201, {"_raw": txt}
        except Exception as e:
            return 0, {"_error": str(e)}

    s1, _ = _upload("chunks.jsonl.gz", data_gz, "application/gzip")
    if s1 != 201:
        _log(f"publish_backup: chunks 업로드 실패: code={s1}")
        return False

    s2, _ = _upload("manifest.json", man_bytes, "application/json")
    if s2 != 201:
        _log(f"publish_backup: manifest 업로드 실패: code={s2}")
        return False

    # 보존 정책: 오래된 릴리스 정리(최대 keep_last_n 유지)
    try:
        st3, rels = _http_json(
            "GET",
            f"{API}/repos/{repo}/releases",
            _headers(),
            None,
            timeout=20,
        )
        if st3 == 200 and isinstance(rels, list):
            # index- 접두 태그만 대상으로 정렬
            idx_rels = [
                r for r in rels if str(r.get("tag_name") or "").startswith(f"{tag_prefix}-")
            ]
            idx_rels.sort(
                key=lambda r: str(r.get("created_at") or ""),
                reverse=True,
            )
            for r in idx_rels[keep_last_n:]:
                rid = r.get("id")
                tname = r.get("tag_name")
                if rid:
                    _http_json(
                        "DELETE",
                        f"{API}/repos/{repo}/releases/{rid}",
                        _headers(),
                        None,
                        timeout=15,
                    )
                if tname:
                    _http_json(
                        "DELETE",
                        f"{API}/repos/{repo}/git/refs/tags/{tname}",
                        _headers(),
                        None,
                        timeout=15,
                    )
    except Exception as e:
        _log(f"publish_backup: 보존 정책 예외(무시): {e}")

    _log(f"publish_backup: 완료 — tag={tag}, repo={repo}")
    return True
# ======================== [07] PUBLIC API: publish_backup — END ===========================
