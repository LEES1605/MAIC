# src/rag/index_build.py — FULL REPLACEMENT
# [01] 기본 설정 & 상수  # [01] START
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import urllib.parse
import urllib.request

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

# GitHub Releases 사용 여부
USE_GITHUB_RELEASES = True

# 하위폴더 재귀 수집
DRIVE_RECURSIVE = True


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[index_build][{ts}] {msg}", flush=True)


# 공통 HTTP 유틸(타임아웃 포함)
def _gh_request(
    url: str,
    method: str = "GET",
    token: str = "",
    data: bytes | None = None,
    headers: dict | None = None,
) -> Tuple[int, bytes]:
    hdrs = {"User-Agent": "maic-indexer"}
    if token:
        hdrs["Authorization"] = f"token {token}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=10) as r:
        code = getattr(r, "status", 200)
        res = r.read()
    return code, res


def _get_gh_conf() -> Optional[dict]:
    """
    GH_TOKEN / GH_REPO 환경변수에서 GitHub 업로드/다운로드 설정을 읽는다.
    - GH_REPO 예: "OWNER/REPO"
    """
    repo = os.getenv("GH_REPO") or os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if repo and token:
        return {"repo": repo, "token": token}
    return None


# [01] END


# [03] Google Drive 클라이언트 & 헬퍼  # [03] START
def _drive_client():
    """Google Drive API v3 클라이언트 생성(서비스계정/ADC)."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    if GOOGLE_APPLICATION_CREDENTIALS and Path(GOOGLE_APPLICATION_CREDENTIALS).exists():
        creds = Credentials.from_service_account_file(
            GOOGLE_APPLICATION_CREDENTIALS,
            scopes=scopes,
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # ADC (Cloud Run/GCE 등)
    try:
        import google.auth

        creds, _ = google.auth.default(scopes=scopes)
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        # B904: 예외 체이닝
        raise RuntimeError(f"Drive 인증 실패: {e}") from e


def _find_folder_id(
    svc=None,
    prefer_id: Optional[str] = None,
    name: Optional[str] = None,
) -> Optional[str]:
    """
    폴더 ID를 환경변수 또는 이름으로 탐색.
    - svc가 None이면 내부에서 드라이브 클라이언트를 생성해 사용
    - orchestrator가 _find_folder_id(None)로 호출해도 안전하도록 폴백 지원
    """
    if prefer_id:
        return prefer_id

    if svc is None:
        try:
            svc = _drive_client()
        except Exception:
            return None

    target_name = name or PREPARED_FOLDER_NAME
    q = (
        f"name = '{target_name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    res = svc.files().list(q=q, fields="files(id, name)", pageSize=50).execute()
    files = res.get("files", [])
    if not files:
        q2 = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res2 = svc.files().list(q=q2, fields="files(id, name)", pageSize=1000).execute()
        for f in res2.get("files", []):
            if f.get("name", "").lower() == target_name.lower():
                return f.get("id")
        return None
    return files[0].get("id")


def _list_files_in_folder(svc, folder_id: str) -> List[Dict[str, Any]]:
    """prepared 폴더의 직속 파일 목록(페이지네이션 지원)."""
    q = (
        f"'{folder_id}' in parents and trashed=false and "
        "mimeType != 'application/vnd.google-apps.folder'"
    )
    fields = "nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum)"
    out: List[Dict[str, Any]] = []
    token: Optional[str] = None
    while True:
        res = (
            svc.files()
            .list(q=q, fields=fields, orderBy="modifiedTime desc", pageSize=1000, pageToken=token)
            .execute()
        )
        out.extend(res.get("files", []))
        token = res.get("nextPageToken")
        if not token:
            break
    return out


def _list_files_recursive(svc, root_folder_id: str) -> List[Dict[str, Any]]:
    """root 폴더 이하 전체 파일을 재귀적으로 수집(폴더 제외)."""
    fields = (
        "nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum, parents)"
    )

    def _iter_children(folder_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        token: Optional[str] = None
        q = f"'{folder_id}' in parents and trashed=false"
        while True:
            res = svc.files().list(q=q, fields=fields, pageSize=1000, pageToken=token).execute()
            out.extend(res.get("files", []))
            token = res.get("nextPageToken")
            if not token:
                break
        return out

    stack = [root_folder_id]
    files: List[Dict[str, Any]] = []
    while stack:
        fid = stack.pop()
        for it in _iter_children(fid):
            mt = it.get("mimeType", "")
            if mt == "application/vnd.google-apps.folder":
                stack.append(it.get("id"))
                continue
            files.append(it)
    return files


def _download_file_bytes(svc, file_id: str, mime_type: Optional[str] = None) -> bytes:  # noqa: ARG001
    """Drive 파일 바이트 다운로드 (Docs류는 export)."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseDownload

    meta = svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    m = meta.get("mimeType", "")
    is_gdoc = m.startswith("application/vnd.google-apps")
    try:
        if not is_gdoc:
            request = svc.files().get_media(fileId=file_id)
        else:
            export_mime = "text/plain"
            if "spreadsheet" in m:
                export_mime = "text/csv"
            if "presentation" in m:
                export_mime = "application/pdf"
            request = svc.files().export_media(fileId=file_id, mimeType=export_mime)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fd=fh, request=request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()
    except HttpError:
        return b""


def scan_drive_listing(svc, prepared_folder_id: str) -> List[Dict[str, Any]]:
    """prepared 폴더의 직속 파일 목록을 반환합니다. 실패 시 빈 리스트 반환."""
    try:
        if not svc or not prepared_folder_id:
            return []
        return _list_files_in_folder(svc, prepared_folder_id)
    except Exception:
        return []
# [03] END


# [04] 텍스트 추출기  # [04] START
def _extract_text_from_bytes(name: str, data: bytes) -> str:
    """텍스트/마크다운/CSV는 UTF-8, PDF는 PyPDF2로 추출."""
    if not data:
        return ""
    buf = data[:MAX_BYTES] if len(data) > MAX_BYTES else data
    lower = (name or "").lower()
    if lower.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(io.BytesIO(buf))
            texts: List[str] = []
            for p in reader.pages:
                try:
                    texts.append(p.extract_text() or "")
                except Exception:
                    texts.append("")
            return "\n".join(texts).strip()
        except Exception:
            return ""
    try:
        return buf.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_texts_from_zip(data: bytes, zip_name: str) -> List[Dict[str, str]]:  # noqa: ARG001
    """ZIP 내부에서 텍스트류만 꺼내 텍스트 추출."""
    out: List[Dict[str, str]] = []
    if not data:
        return out
    buf = data[:MAX_BYTES] if len(data) > MAX_BYTES else data
    try:
        with zipfile.ZipFile(io.BytesIO(buf)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                inner = info.filename
                if not any(inner.lower().endswith(ext) for ext in ALLOWED_EXTS if ext != ".zip"):
                    continue
                try:
                    b = zf.read(info)
                except Exception:
                    continue
                t = _extract_text_from_bytes(inner, b)
                if t.strip():
                    out.append({"name": inner, "text": t})
    except Exception:
        pass
    return out
# [04] END


# [05] 청크 분할  # [05] START
def _to_chunks(
    name: str,
    text: str,
    meta: Dict[str, Any],
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    t = text.strip()
    if not t:
        return chunks
    n = len(t)
    start = 0
    while start < n:
        end = min(n, start + chunk_size)
        seg = t[start:end]
        chunks.append(
            {
                "file_name": name,
                "text": seg,
                "meta": meta,
                "offset": start,
                "length": len(seg),
            }
        )
        if end >= n:
            break
        start = max(0, end - chunk_overlap)
    return chunks
# [05] END


# [06] 인덱스 빌드(Drive prepared)  # [06] START
def _build_from_prepared(
    svc,
    prepared_folder_id: str,
) -> Tuple[int, int, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """prepared 폴더(직속 또는 재귀)의 인덱싱."""
    files = (
        _list_files_recursive(svc, prepared_folder_id)
        if DRIVE_RECURSIVE
        else _list_files_in_folder(svc, prepared_folder_id)
    )
    docs_summary: List[Dict[str, Any]] = []
    chunks: List[Dict[str, Any]] = []

    for f in files:
        fid = f["id"]
        name = f.get("name", fid)
        mime = f.get("mimeType", "")
        low = name.lower()

        # 인덱싱 대상만
        if not any(low.endswith(ext) for ext in ALLOWED_EXTS):
            continue

        data = _download_file_bytes(svc, fid)

        # ZIP
        if low.endswith(".zip") or mime == "application/zip":
            extracted = _extract_texts_from_zip(data, name)
            for item in extracted:
                meta = {
                    "file_id": f"{fid}:{item['name']}",
                    "file_name": item["name"],
                    "mimeType": "text/plain",
                    "page_approx": None,
                }
                chunks.extend(_to_chunks(item["name"], item["text"], meta))
            docs_summary.append(
                {
                    "id": fid,
                    "name": name,
                    "mimeType": mime,
                    "size": f.get("size"),
                    "md5": f.get("md5Checksum"),
                    "expanded_from_zip": len(extracted),
                }
            )
            continue

        # 단일 파일
        text = _extract_text_from_bytes(name, data)
        if text.strip():
            meta = {
                "file_id": fid,
                "file_name": name,
                "mimeType": mime,
                "page_approx": None,
            }
            chunks.extend(_to_chunks(name, text, meta))

        docs_summary.append(
            {
                "id": fid,
                "name": name,
                "mimeType": mime,
                "size": f.get("size"),
                "md5": f.get("md5Checksum"),
            }
        )

    manifest = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "docs": docs_summary,
    }
    extra = {"processed_files": len(docs_summary), "generated_chunks": len(chunks)}
    return len(docs_summary), len(chunks), manifest, extra, chunks
# [06] END


# [07] 저장  # [07] START
def _write_manifest(manifest: Dict[str, Any]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"manifest 저장: {MANIFEST_PATH}")


def _write_chunks_jsonl(chunks: List[Dict[str, Any]]) -> None:
    out = PERSIST_DIR / "chunks.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in chunks:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    _log(f"chunks 저장: {out} (rows={len(chunks)})")
# [07] END


# [08] 변경 감지(diff)  # [08] START
def _ingestible(name: str) -> bool:
    n = (name or "").lower()
    return any(n.endswith(ext) for ext in ALLOWED_EXTS)


def diff_with_manifest(folder_id: str | None = None, limit: int = 5000) -> dict:
    """
    prepared 목록과 로컬 manifest.json 비교 → added/changed/removed.
    - 인덱싱 대상 확장자만 비교
    - 최초(no_manifest) 시 현재 대상 전부 added로 간주
    - DRIVE_RECURSIVE 설정 반영
    """
    out = {
        "ok": False,
        "reason": "",
        "stats": {"added": 0, "changed": 0, "removed": 0},
        "added": [],
        "changed": [],
        "removed": [],
    }
    try:
        svc = _drive_client()
        fid = folder_id or _find_folder_id(svc, prefer_id=PREPARED_FOLDER_ID, name=PREPARED_FOLDER_NAME)
        if not fid:
            out["reason"] = "no_prepared_id"
            return out

        cur_all = (
            _list_files_recursive(svc, fid) if DRIVE_RECURSIVE else _list_files_in_folder(svc, fid)
        )
        cur = [f for f in cur_all if _ingestible(f.get("name", ""))][:limit]
        cdocs = {f.get("id"): f for f in cur if f.get("id")}

        if not MANIFEST_PATH.exists():
            out.update(
                ok=True,
                reason="no_manifest",
                added=[f.get("name") for f in cur],
                stats={"added": len(cur), "changed": 0, "removed": 0},
            )
            return out

        man = json.loads(MANIFEST_PATH.read_text(encoding="utf-8") or "{}")
        mdocs_src = {d.get("id"): d for d in (man.get("docs") or []) if d.get("id")}
        mdocs = {i: d for i, d in mdocs_src.items() if _ingestible(d.get("name", ""))}

        ids_m, ids_c = set(mdocs.keys()), set(cdocs.keys())
        added_ids = list(ids_c - ids_m)
        removed_ids = list(ids_m - ids_c)
        common_ids = ids_m & ids_c

        changed_ids: List[str] = []
        for i in common_ids:
            m = mdocs[i]
            c = cdocs[i]
            md5_m, md5_c = m.get("md5"), c.get("md5Checksum")
            sz_m, sz_c = str(m.get("size")), str(c.get("size"))
            if (md5_m and md5_c and md5_m != md5_c) or (sz_m and sz_c and sz_m != sz_c):
                changed_ids.append(i)

        def _names(ids: List[str]) -> List[str]:
            out_names: List[str] = []
            for _id in ids:
                if _id in cdocs:
                    out_names.append(cdocs[_id].get("name"))
                elif _id in mdocs:
                    out_names.append(mdocs[_id].get("name"))
            return out_names

        out["ok"] = True
        out["added"], out["changed"], out["removed"] = (
            _names(added_ids),
            _names(changed_ids),
            _names(removed_ids),
        )
        out["stats"] = {
            "added": len(out["added"]),
            "changed": len(out["changed"]),
            "removed": len(out["removed"]),
        }
        return out
    except Exception as e:
        out["reason"] = f"{type(e).__name__}: {e}"
        return out
# [08] END


# [09U] GitHub 업로드 유틸  # [09U] START
def _zip_index_artifacts(zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        if MANIFEST_PATH.exists():
            z.write(MANIFEST_PATH, arcname="manifest.json")
        chunks_path = PERSIST_DIR / "chunks.jsonl"
        if chunks_path.exists():
            z.write(chunks_path, arcname="chunks.jsonl")
    return zip_path


def _github_create_or_get_release(conf: dict, tag: str, name: str, body: str = "") -> Optional[int]:
    repo, token = conf["repo"], conf["token"]
    url = "https://api.github.com/repos/{repo}/releases".format(repo=repo)
    payload = json.dumps(
        {"tag_name": tag, "name": name, "body": body, "draft": False, "prerelease": False}
    ).encode("utf-8")
    code, res = _gh_request(url, "POST", token, payload, {"Content-Type": "application/json"})
    if 200 <= code < 300:
        return json.loads(res.decode("utf-8")).get("id")

    # 이미 존재하면 GET으로 회수
    try:
        code, res = _gh_request(
            "https://api.github.com/repos/{repo}/releases/tags/{tag}".format(repo=repo, tag=tag),
            "GET",
            token,
        )
        if 200 <= code < 300:
            return json.loads(res.decode("utf-8")).get("id")
    except Exception:
        pass
    return None


def _github_delete_asset_if_exists(conf: dict, release_id: int, asset_name: str) -> None:
    repo, token = conf["repo"], conf["token"]
    code, res = _gh_request(
        "https://api.github.com/repos/{repo}/releases/{rid}/assets".format(repo=repo, rid=release_id),
        "GET",
        token,
    )
    if not (200 <= code < 300):
        return
    assets = json.loads(res.decode("utf-8"))
    for a in assets:
        if a.get("name") == asset_name:
            aid = a.get("id")
            try:
                _gh_request(
                    "https://api.github.com/repos/{repo}/releases/assets/{aid}".format(
                        repo=repo, aid=aid
                    ),
                    "DELETE",
                    token,
                )
            except Exception:
                pass


def upload_index_to_github_releases(note: str = "") -> Optional[str]:
    """manifest+chunks를 ZIP으로 묶어 Releases에 업로드."""
    if not USE_GITHUB_RELEASES:
        return None
    conf = _get_gh_conf()
    if not conf:
        _log("GitHub 설정 없음 → 업로드 생략")
        return None

    ts = datetime.now().strftime("%Y%m%d-%H%M")
    tag = f"index-{ts}"
    rel_name = f"MAIC index {ts}"
    rid = _github_create_or_get_release(conf, tag, rel_name, body=note or "MAIC auto snapshot")
    if not rid:
        _log("Release 생성/조회 실패 → 업로드 생략")
        return None

    out_dir = PERSIST_DIR / "releases"
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_name = f"index_{ts}.zip"
    latest_name = "index_latest.zip"
    snap_zip = _zip_index_artifacts(out_dir / snapshot_name)
    latest_zip = _zip_index_artifacts(out_dir / latest_name)
    del snap_zip, latest_zip  # 파일만 생성하면 충분

    repo, token = conf["repo"], conf["token"]
    up_base = "https://uploads.github.com/repos/{repo}/releases/{rid}/assets?name=".format(
        repo=repo, rid=rid
    )
    for fname in [snapshot_name, latest_name]:
        if fname == latest_name:
            _github_delete_asset_if_exists(conf, rid, latest_name)
        data = (out_dir / fname).read_bytes()
        _log(f"GitHub 업로드: {fname} ({len(data)} bytes)")
        _gh_request(
            up_base + urllib.parse.quote(fname),
            "POST",
            token,
            data,
            {"Content-Type": "application/zip"},
        )
    return snapshot_name
# [09U] END


# [09D] GitHub 최신 ZIP 복원  # [09D] START
def _parse_built_ts_from_manifest(path: Path) -> int:
    try:
        mj = json.loads(path.read_text(encoding="utf-8"))
        s = (mj.get("built_at") or "").strip()
        if not s:
            return 0
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp())
    except Exception:
        return 0


def _download_latest_release_zip() -> Optional[bytes]:
    conf = _get_gh_conf()
    if not (USE_GITHUB_RELEASES and conf):
        return None
    repo, token = conf["repo"], conf["token"]
    try:
        code, res = _gh_request(
            "https://api.github.com/repos/{repo}/releases/latest".format(repo=repo),
            "GET",
            token,
        )
        if not (200 <= code < 300):
            return None
        data = json.loads(res.decode("utf-8"))
        assets = data.get("assets", []) or []
        target = None
        for a in assets:
            if a.get("name") == "index_latest.zip":
                target = a
                break
        if not target and assets:
            assets_sorted = sorted(assets, key=lambda x: x.get("updated_at", ""), reverse=True)
            for a in assets_sorted:
                n = str(a.get("name", ""))
                if n.startswith("index_") and n.endswith(".zip"):
                    target = a
                    break
        if not target:
            return None
        url = target.get("browser_download_url")
        if not url:
            return None
        _log(f"GitHub 다운로드: {target.get('name')} …")
        code, blob = _gh_request(url, "GET", token)
        if 200 <= code < 300:
            return blob
    except Exception:
        return None
    return None


def restore_from_github_release_if_needed() -> bool:
    """로컬 인덱스 없거나 오래됐으면 Releases 최신 ZIP으로 복원."""
    if not USE_GITHUB_RELEASES:
        _log("GitHub 복원 비활성 → 스킵")
        return False

    man_exists = MANIFEST_PATH.exists() and MANIFEST_PATH.stat().st_size > 0
    chk_path = PERSIST_DIR / "chunks.jsonl"
    chk_exists = chk_path.exists() and chk_path.stat().st_size > 0
    local_ts = _parse_built_ts_from_manifest(MANIFEST_PATH) if man_exists else 0
    del chk_exists  # 현재 로직에서는 사용 안 함(미래 확장 보류)

    blob = _download_latest_release_zip()
    if not blob:
        _log("Releases 최신 ZIP 없음/다운 실패 → 복원 스킵")
        return False

    tmp = PERSIST_DIR / "_tmp_restore.zip"
    tmp.write_bytes(blob)
    try:
        with zipfile.ZipFile(tmp, "r") as z:
            z.extractall(PERSIST_DIR)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    new_ts = _parse_built_ts_from_manifest(MANIFEST_PATH)
    if new_ts and new_ts >= local_ts:
        _log(f"복원 완료: manifest/chunks 갱신 (built_at: {new_ts})")
        return True

    _log("복원했으나 더 오래된 스냅샷 → 유지")
    return False
# [09D] END


# [09] 전체 파이프라인 실행(빌드)  # [09] START
def run_index_pipeline(folder_id: str | None = None) -> Dict[str, Any]:
    """prepared에서 문서를 인덱싱하여 저장(+선택적으로 Releases 업로드)."""
    svc = _drive_client()
    fid = folder_id or _find_folder_id(svc, prefer_id=PREPARED_FOLDER_ID, name=PREPARED_FOLDER_NAME)
    if not fid:
        raise RuntimeError("prepared 폴더 ID를 찾을 수 없습니다.")

    n_files, n_chunks, manifest, extra, chunks = _build_from_prepared(svc, fid)
    _write_manifest(manifest)
    _write_chunks_jsonl(chunks)
    _log(f"인덱싱 완료: files={n_files}, chunks={n_chunks}")

    if USE_GITHUB_RELEASES and _get_gh_conf():
        try:
            snap = upload_index_to_github_releases(note=f"files={n_files}, chunks={n_chunks}")
            if snap:
                _log(f"Releases 업로드 완료: {snap}")
        except Exception as e:
            _log(f"Releases 업로드 실패: {e}")

    return {
        "files": n_files,
        "chunks": n_chunks,
        "manifest_path": str(MANIFEST_PATH),
        "chunks_path": str(PERSIST_DIR / "chunks.jsonl"),
        "extra": extra,
    }
# [09] END


# [10] CLI  # [10] START
def _cli() -> None:
    import argparse

    p = argparse.ArgumentParser(description="MAIC Index Builder (Drive prepared)")
    p.add_argument("--build", action="store_true", help="변경 여부와 무관하게 인덱싱 수행")
    p.add_argument("--diff", action="store_true", help="변경 감지만 출력")
    p.add_argument("--folder-id", type=str, default=None, help="prepared 폴더 ID 직접 지정")
    args = p.parse_args()

    if args.diff and not args.build:
        d = diff_with_manifest(folder_id=args.folder_id)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    if args.build:
        res = run_index_pipeline(folder_id=args.folder_id)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    d = diff_with_manifest(folder_id=args.folder_id)
    if not d.get("ok"):
        _log(f"변경 감지 실패: {d.get('reason')}")
        return

    stt = d.get("stats", {})
    if stt.get("added", 0) or stt.get("changed", 0):
        _log(
            "변경 감지됨: added={a} changed={c} → 인덱싱 수행".format(
                a=stt.get("added"),
                c=stt.get("changed"),
            )
        )
        run_index_pipeline(folder_id=args.folder_id)
    else:
        _log("변경 없음: Releases 최신 ZIP 자동 복원 시도")
        try:
            restored = restore_from_github_release_if_needed()
            if not restored:
                _log("복원 생략/실패: 로컬 인덱스 그대로 사용")
        except Exception as e:
            _log(f"Releases 복원 실패: {e}")


if __name__ == "__main__":
    _cli()
# [10] END


# [11] UI 호환 어댑터(API)  # [11] START
def _result(
    action: str,
    ok: bool,
    detail: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = {"ok": ok, "action": action, "detail": detail}
    if extra:
        out.update(extra)
    return out


def build_index_with_checkpoint(
    *,
    force: bool = False,
    prefer_release_restore: bool = True,
    folder_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    UI가 기대하는 인터페이스.
      - force=True: 무조건 빌드
      - force=False: diff→변경 있으면 빌드, 없으면 (옵션) Releases 복원
    반환 예:
      {"ok": True, "action": "build", "files": 12, "chunks": 340, ...}
      {"ok": True, "action": "restore", "restored": True}
      {"ok": True, "action": "skip"}
    """
    if force:
        res = run_index_pipeline(folder_id=folder_id)
        return _result(
            "build",
            True,
            "forced build",
            {"files": res.get("files"), "chunks": res.get("chunks"), "extra": res.get("extra")},
        )

    d = diff_with_manifest(folder_id=folder_id)
    if not d.get("ok"):
        return _result("diff-only", False, d.get("reason", "diff failed"))

    stt = d.get("stats", {})
    added = int(stt.get("added", 0) or 0)
    changed = int(stt.get("changed", 0) or 0)
    if added or changed:
        res = run_index_pipeline(folder_id=folder_id)
        return _result(
            "build",
            True,
            f"added={added}, changed={changed}",
            {"files": res.get("files"), "chunks": res.get("chunks"), "extra": res.get("extra")},
        )

    if prefer_release_restore:
        try:
            restored = restore_from_github_release_if_needed()
        except Exception as e:
            return _result("restore", False, f"restore failed: {e}")
        if restored:
            return _result("restore", True, "restored from latest release", {"restored": True})
    return _result("skip", True, "no changes", {"restored": False})


# 예전 이름 호환
def build_index(*, folder_id: Optional[str] = None) -> Dict[str, Any]:
    return build_index_with_checkpoint(force=True, folder_id=folder_id)


def ensure_index_ready(
    *,
    prefer_release_restore: bool = True,
    folder_id: Optional[str] = None,
) -> Dict[str, Any]:
    return build_index_with_checkpoint(
        force=False,
        prefer_release_restore=prefer_release_restore,
        folder_id=folder_id,
    )


def diff_status(*, folder_id: Optional[str] = None) -> Dict[str, Any]:
    return diff_with_manifest(folder_id=folder_id)
# [11] END


# [12] 빠른 사전 점검(quick_precheck)  # [12] START
def quick_precheck() -> dict:
    """
    UI에서 초기 상태 뱃지/버튼 표시 전에 호출하는 빠른 점검.
    반환 스키마(보수적):
      {
        "ok": bool,                    # 전체적으로 사용 가능 판단
        "drive_ok": bool,              # Drive 읽기 인증 성공
        "prepared_id": str | None,     # prepared 폴더 ID
        "local_index_ok": bool,        # 로컬 manifest/chunks 존재 여부
        "gh_ok": bool,                 # GitHub Releases 설정 존재 여부
        "recursive": bool,             # 하위폴더 재귀 인덱싱 설정값
        "detail": str                  # 간단 사유/메시지
      }
    """
    info = {
        "ok": False,
        "drive_ok": False,
        "prepared_id": None,
        "local_index_ok": False,
        "gh_ok": False,
        "recursive": bool(DRIVE_RECURSIVE),
        "detail": "",
    }

    # 1) 로컬 인덱스 존재 여부
    try:
        man_ok = MANIFEST_PATH.exists() and MANIFEST_PATH.stat().st_size > 0
        chunks_path = PERSIST_DIR / "chunks.jsonl"
        chk_ok = chunks_path.exists() and chunks_path.stat().st_size > 0
        info["local_index_ok"] = bool(man_ok and chk_ok)
    except Exception:
        info["local_index_ok"] = False

    # 2) GitHub 설정
    try:
        info["gh_ok"] = bool(USE_GITHUB_RELEASES and _get_gh_conf())
    except Exception:
        info["gh_ok"] = False

    # 3) Drive 인증 + prepared 폴더 ID
    try:
        svc = _drive_client()
        info["drive_ok"] = True
        fid = _find_folder_id(svc, prefer_id=PREPARED_FOLDER_ID, name=PREPARED_FOLDER_NAME)
        info["prepared_id"] = fid
        if not fid:
            info["detail"] = "prepared 폴더 ID를 찾지 못했습니다."
    except Exception as e:
        info["drive_ok"] = False
        info["detail"] = f"Drive 인증 실패: {e}"

    # 4) 종합 판단
    if info["drive_ok"] and info["prepared_id"]:
        if info["local_index_ok"] or info["gh_ok"]:
            info["ok"] = True
            if not info["detail"]:
                info["detail"] = "정상"
        else:
            info["detail"] = "인덱스 없음 및 GitHub 복원 설정 없음"
    return info
# [12] END
