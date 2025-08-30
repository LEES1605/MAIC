# ==================== src/rag/index_build.py — START =========================

# [01] Imports & Paths — START
from __future__ import annotations
import os, io, json, gzip, shutil, zipfile, time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

# 외부
import streamlit as st  # type: ignore
from google.oauth2 import service_account
from googleapiclient.discovery import build as gbuild
from googleapiclient.http import MediaIoBaseDownload

# 내부 설정 경로
try:
    from src.config import PERSIST_DIR as _PERSIST_DIR, APP_DATA_DIR as _APP_DATA_DIR
except Exception:
    _PERSIST_DIR = str(Path.home() / ".maic" / "persist")
    _APP_DATA_DIR = str(Path.home() / ".maic")

PERSIST_DIR = Path(_PERSIST_DIR).expanduser()
# 호환성 보존용(미사용): 과거 백업 경로 (Drive 백업 업로드 제거됨)
BACKUP_DIR  = (Path(_APP_DATA_DIR).expanduser() / "backup")

PERSIST_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
# [01] Imports & Paths — END
# ============================================================================


# [02] Small utils (secrets/time/progress) — START
def _read_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """st.secrets → env → default 순으로 읽기."""
    try:
        val = st.secrets.get(key)  # type: ignore[attr-defined]
        if val is None:
            return os.getenv(key, default)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(key, default)

def _now_tag() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())

def _msg(update_msg: Callable[[str], None], s: str) -> None:
    try: update_msg(str(s))
    except Exception: pass

def _pct(update_pct: Callable[[int, Optional[str]], None], v: int, m: Optional[str] = None) -> None:
    try: update_pct(int(v), m)
    except Exception: pass
# [02] Small utils (secrets/time/progress) — END
# ============================================================================


# [03] Google Drive auth (Service Account only) — START
def _drive_client():
    """Service Account 자격으로 Drive v3 클라이언트 생성."""
    raw = st.secrets.get("gcp_service_account") if hasattr(st, "secrets") else None  # type: ignore
    if isinstance(raw, str):
        info = json.loads(raw)
    elif isinstance(raw, dict):
        info = dict(raw)
    else:
        raise RuntimeError("gcp_service_account 시크릿이 없습니다.")

    scopes = st.secrets.get("GDRIVE_SCOPES") if hasattr(st, "secrets") else None  # type: ignore
    if isinstance(scopes, str):
        try: scopes = json.loads(scopes)
        except Exception: scopes = [scopes]
    if not scopes:
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return gbuild("drive", "v3", credentials=creds, cache_discovery=False)
# [03] Google Drive auth (Service Account only) — END
# ============================================================================


# [04] Drive helpers (ids/list/download) — START
def _find_folder_id(kind: str, *, fallback: Optional[str] = None) -> Optional[str]:
    key = {
        "PREPARED": "GDRIVE_PREPARED_FOLDER_ID",
        "BACKUP":   "GDRIVE_BACKUP_FOLDER_ID",  # 미사용(정책상 제거), 호환 키만 남김
        "DEFAULT":  "GDRIVE_PREPARED_FOLDER_ID",
    }.get(kind.upper(), "GDRIVE_PREPARED_FOLDER_ID")
    return _read_secret(key, fallback)

def _list_files_in_folder(svc, folder_id: str) -> List[Dict[str, Any]]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id, name, mimeType, modifiedTime, size, md5Checksum)"
    res = svc.files().list(q=q, fields=fields, orderBy="modifiedTime desc", pageSize=1000).execute()
    return res.get("files", [])

def _download_file_bytes(svc, file_id: str) -> bytes:
    meta = svc.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime = meta.get("mimeType", "")
    name = meta.get("name", file_id)

    # Google Docs Editors → export
    if mime.startswith("application/vnd.google-apps."):
        subtype = mime.split(".")[-1]
        export_map = {
            "document":     "text/plain",
            "spreadsheet":  "text/csv",
            "presentation": "text/plain",
        }
        exp = export_map.get(subtype)
        if not exp:
            print(f"[drive][info] skip unsupported google-apps file: {name} ({mime})")
            return b""
        try:
            data = svc.files().export(fileId=file_id, mimeType=exp).execute()
            if isinstance(data, str):
                data = data.encode("utf-8", errors="ignore")
            print(f"[drive] exported {name} as {exp}")
            return data
        except Exception as e:
            print(f"[drive][warn] export failed for {name} ({mime}): {type(e).__name__}: {e}")
            return b""

    # 일반 바이너리 다운로드
    try:
        req = svc.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            status, done = dl.next_chunk()
        return buf.getvalue()
    except Exception as e:
        print(f"[drive][warn] get_media failed for {name} ({mime}): {type(e).__name__}: {e}")
        return b""
# [04] Drive helpers (ids/list/download) — END
# ============================================================================


# [05] Local store helpers — START
def _persist_write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _persist_write_jsonl(rows: Iterable[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _gzip_file(src: Path, dst: Optional[Path] = None, compresslevel: int = 6) -> Path:
    if dst is None:
        dst = src.with_suffix(src.suffix + ".gz")
    with src.open("rb") as fr, gzip.open(dst, "wb", compresslevel=compresslevel) as fw:
        shutil.copyfileobj(fr, fw)
    return dst
# [05] Local store helpers — END
# ============================================================================


# [06] Text & chunk builders (ZIP 지원 포함) — START
def _extract_text_from_bytes(name: str, data: bytes) -> str:
    if not data:
        return ""
    # 64MB 상한
    if len(data) > 64 * 1024 * 1024:
        data = data[:64 * 1024 * 1024]
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def _extract_texts_from_zip(zip_bytes: bytes, zip_name: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not zip_bytes:
        return out
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            inner = info.filename
            inner_lower = inner.lower()
            if not (inner_lower.endswith(".txt") or inner_lower.endswith(".md")
                    or inner_lower.endswith(".csv") or inner_lower.endswith(".pdf")):
                continue
            try:
                data = z.read(info)
            except Exception:
                continue

            text = ""
            if inner_lower.endswith(".pdf"):
                try:
                    from PyPDF2 import PdfReader  # type: ignore
                    import io as _io
                    reader = PdfReader(_io.BytesIO(data))
                    pages = []
                    for p in reader.pages:
                        try:
                            pages.append(p.extract_text() or "")
                        except Exception:
                            pages.append("")
                    text = "\n".join(pages)
                except Exception:
                    text = ""
            else:
                text = _extract_text_from_bytes(inner, data)

            if not text.strip():
                continue
            out.append({"name": f"{zip_name}::{inner}", "text": text})
    return out

def _to_chunks(name: str, text: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        out.append({"text": line, "meta": {**meta, "line_index": i}})
    return out
# [06] Text & chunk builders (ZIP 지원 포함) — END
# ============================================================================


# [07] Quality report — START
def _quality_report(docs: List[Dict[str, Any]], chunks_rows: List[Dict[str, Any]], *,
                    extra_counts: Dict[str, Any]) -> Dict[str, Any]:
    meta_fields = {"file_name": 0, "file_id": 0, "mimeType": 0, "page_approx": 0}
    for c in chunks_rows:
        m = c.get("meta", {})
        if "file_name" in m:   meta_fields["file_name"] += 1
        if "file_id"   in m:   meta_fields["file_id"]   += 1
        if "mimeType"  in m:   meta_fields["mimeType"]  += 1
        if "page_approx" in m: meta_fields["page_approx"] += 1
    return {
        "stats": {
            "documents": len(docs),
            "chunks": len(chunks_rows),
            **{f"meta_has_{k}": v for k, v in meta_fields.items()},
        },
        "extra": extra_counts or {},
    }
# [07] Quality report — END
# ============================================================================


# [08] RESERVED — Drive backup upload helpers (REMOVED) — START
# 이 구획은 과거 Drive 백업 업로드 헬퍼가 있었던 자리입니다.
# 정책에 따라 완전히 제거되었습니다(쓰기 권한/동작 없음).
# [08] RESERVED — Drive backup upload helpers (REMOVED) — END
# ============================================================================


# [09] Build core (scan prepared → chunks/manifest) — START
def _build_from_prepared(svc, prepared_folder_id: str) -> Tuple[int, int, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    files = _list_files_in_folder(svc, prepared_folder_id)
    docs_summary: List[Dict[str, Any]] = []
    chunk_rows: List[Dict[str, Any]] = []

    for f in files:
        fid = f["id"]; name = f.get("name", fid); mime = f.get("mimeType", "")
        data = _download_file_bytes(svc, fid)

        # ZIP이면 내부 텍스트류만 펼쳐서 처리
        if (mime == "application/zip") or name.lower().endswith(".zip"):
            extracted = _extract_texts_from_zip(data, name)
            for item in extracted:
                meta = {"file_id": f"{fid}:{item['name']}", "file_name": item["name"], "mimeType": "text/plain", "page_approx": None}
                chunk_rows.extend(_to_chunks(item["name"], item["text"], meta))
            docs_summary.append({"id": fid, "name": name, "mimeType": mime,
                                 "size": f.get("size"), "md5": f.get("md5Checksum"),
                                 "expanded_from_zip": len(extracted)})
            continue

        text = _extract_text_from_bytes(name, data)
        meta = {"file_id": fid, "file_name": name, "mimeType": mime, "page_approx": None}
        chunk_rows.extend(_to_chunks(name, text, meta))
        docs_summary.append({"id": fid, "name": name, "mimeType": mime,
                             "size": f.get("size"), "md5": f.get("md5Checksum")})

    manifest = {"built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "docs": docs_summary}
    extra = {"processed_files": len(docs_summary), "generated_chunks": len(chunk_rows)}
    return len(docs_summary), len(chunk_rows), manifest, extra, chunk_rows

def _resolve_prepared_id(svc, gdrive_folder_id: str) -> str:
    prepared_id = _find_folder_id("PREPARED", fallback=gdrive_folder_id)
    if not prepared_id:
        raise KeyError("prepared 폴더 ID를 찾지 못했습니다.")
    return prepared_id

# (호환용) 과거 시그니처 유지: (prepared_id, backup_id) 반환하되 backup_id=None
def _resolve_ids(svc, gdrive_folder_id: str) -> Tuple[str, Optional[str]]:
    return _resolve_prepared_id(svc, gdrive_folder_id), None
# [09] Build core (scan prepared → chunks/manifest) — END
# ============================================================================


# [10] Public entry: build_index_with_checkpoint — START
def build_index_with_checkpoint(
    update_pct: Callable[[int, Optional[str]], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,
    gcp_creds: Mapping[str, object],
    persist_dir: str,
    remote_manifest: Dict[str, Dict[str, object]],
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """prepared 폴더에서 자료를 읽어 chunks.jsonl/manifest.json 생성 후
    정책에 따라 GitHub Releases에 게시한다. (Drive 백업 업로드 경로 제거됨)
    """
    def pct(v: int, m: Optional[str] = None): _pct(update_pct, v, m)
    def msg(s: str): _msg(update_msg, s)

    msg("🔐 Connecting Google Drive (service account)…")
    svc = _drive_client()
    pct(5, "drive-ready")

    prepared_id = _resolve_prepared_id(svc, gdrive_folder_id)

    msg("📦 Scanning prepared folder and building chunks…")
    processed, chunks_cnt, manifest, stats, chunk_rows = _build_from_prepared(svc, prepared_id)
    pct(70, f"processed={processed}, chunks={chunks_cnt}")

    if should_stop and should_stop():
        return {"ok": False, "stopped": True}

    # write local
    msg("🧮 Writing manifest/chunks locally…")
    out_dir = PERSIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    chunks_path   = out_dir / "chunks.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(chunks_path, "w", encoding="utf-8") as f:
        for r in chunk_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # quality report
    msg("📊 Building quality report…")
    report = _quality_report(manifest.get("docs", []), chunk_rows, extra_counts=stats)
    pct(85, "report-ready")

    # GitHub Releases upload (항상 수행 — 릴리스 기반 복구 정책)
    try:
        from src.backup.github_release import upload_index_release
        # ensure gzip alongside chunks.jsonl
        gz_path = chunks_path.with_suffix(chunks_path.suffix + ".gz")
        if (not gz_path.exists()) or (gz_path.stat().st_mtime < chunks_path.stat().st_mtime):
            with open(chunks_path, "rb") as fr, gzip.open(gz_path, "wb", compresslevel=6) as fw:
                shutil.copyfileobj(fr, fw)

        msg("🚀 Publishing index to GitHub Releases…")
        res = upload_index_release(
            manifest_path=manifest_path,
            chunks_jsonl_path=chunks_path,
            include_zip=False,  # ZIP은 필요 시 다른 경로로
            keep=2,
            build_meta={
                "processed_files": processed,
                "generated_chunks": chunks_cnt,
                "prepared_folder_id": prepared_id,
            },
        )
        msg(f"✅ GitHub Releases 완료: {res.get('tag')} / {res.get('assets')}")
    except Exception as e:
        msg(f"⚠️ GitHub 업로드 실패: {type(e).__name__}: {e}")

    pct(100, "done")
    return {
        "ok": True,
        "processed_files": processed,
        "generated_chunks": chunks_cnt,
        "stats": stats,
        "report": report,
        # 정책상 Drive 백업 업로드 제거 → 항상 None
        "backup_zip_id": None,
        "prepared_folder_id": prepared_id,
        "backup_folder_id": None,
        "auth_mode": "service-account",
        "persist_dir": str(PERSIST_DIR),
    }
# [10] Public entry: build_index_with_checkpoint — END
# ============================================================================


# [11] Compatibility shims (for UI & prompts loader) — START
def quick_precheck() -> dict:
    """로컬 persist 상태 간단 점검(임포트용 안전 함수)."""
    try:
        persist = str(PERSIST_DIR)
        ready = (PERSIST_DIR / "chunks.jsonl").exists() or (PERSIST_DIR / ".ready").exists()
        return {"ok": True, "persist_dir": persist, "ready": bool(ready)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

def scan_drive_listing(folder_id: str | None = None, limit: int = 50) -> list[dict]:
    """prepared 폴더의 최신 파일 일부를 서비스계정으로 조회."""
    try:
        svc = _drive_client()
        fid = folder_id or _find_folder_id("PREPARED")
        if not fid:
            return []
        q = f"'{fid}' in parents and trashed=false"
        fields = "files(id, name, mimeType, modifiedTime, size, md5Checksum)"
        res = svc.files().list(q=q, fields=fields, orderBy="modifiedTime desc", pageSize=limit).execute()
        return res.get("files", [])
    except Exception:
        return []

def diff_with_manifest(folder_id: str | None = None, limit: int = 1000) -> dict:
    """
    prepared 폴더 목록과 로컬 manifest.json을 비교하여
    added/changed/removed 통계를 반환한다.
    실패/비정상 상황에서도 항상 동일 스키마를 보장한다.
    """
    # 항상 반환할 기본 골격 (UI 안전)
    out = {
        "ok": False,
        "reason": "",
        "stats": {"added": 0, "changed": 0, "removed": 0},
        "added": [],
        "changed": [],
        "removed": [],
    }

    try:
        mpath = PERSIST_DIR / "manifest.json"
        if not mpath.exists():
            out["reason"] = "no_manifest"
            return out

        man = json.loads(mpath.read_text(encoding="utf-8") or "{}")
        mdocs = {d.get("id"): d for d in (man.get("docs") or []) if d.get("id")}

        svc = _drive_client()
        fid = folder_id or _find_folder_id("PREPARED")
        if not fid:
            out["reason"] = "no_prepared_id"
            return out

        cur = _list_files_in_folder(svc, fid)[:limit]
        cdocs = {f.get("id"): f for f in cur if f.get("id")}

        ids_m = set(mdocs.keys()); ids_c = set(cdocs.keys())
        added   = list(ids_c - ids_m)
        removed = list(ids_m - ids_c)
        common  = ids_m & ids_c

        changed: List[str] = []
        for i in common:
            m = mdocs[i]; c = cdocs[i]
            md5_m, md5_c = m.get("md5"), c.get("md5Checksum")
            sz_m,  sz_c  = str(m.get("size")), str(c.get("size"))
            if (md5_m and md5_c and md5_m != md5_c) or (sz_m and sz_c and sz_m != sz_c):
                changed.append(i)

        def _names(ids: List[str]) -> List[str]:
            out_names: List[str] = []
            for _id in ids:
                if _id in cdocs:
                    out_names.append(cdocs[_id].get("name"))
                elif _id in mdocs:
                    out_names.append(mdocs[_id].get("name"))
            return out_names

        out["ok"] = True
        out["added"]   = _names(added)
        out["changed"] = _names(changed)
        out["removed"] = _names(removed)
        out["stats"] = {
            "added": len(out["added"]),
            "changed": len(out["changed"]),
            "removed": len(out["removed"]),
        }
        return out

    except Exception as e:
        out["reason"] = f"{type(e).__name__}: {e}"
        return out

def _drive_service():
    """Compatibility alias for prompt_modes: returns Drive service or None."""
    try:
        return _drive_client()
    except Exception:
        return None
# [11] Compatibility shims (for UI & prompts loader) — END
# ============================================================================


# ===================== src/rag/index_build.py — END ==========================
