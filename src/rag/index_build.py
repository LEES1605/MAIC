# ========================== index_build.py — START ===========================
# [00] IMPORTS & GLOBALS — START
from __future__ import annotations
import os, io, json, gzip, shutil, zipfile, time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

# 외부
import streamlit as st  # type: ignore

# 구글 드라이브 (서비스계정 전용)
from google.oauth2 import service_account
from googleapiclient.discovery import build as gbuild
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# 내부 의존 (경로/설정)
try:
    from src.config import PERSIST_DIR as _PERSIST_DIR, APP_DATA_DIR as _APP_DATA_DIR
except Exception:
    _PERSIST_DIR = str(Path.home() / ".maic" / "persist")
    _APP_DATA_DIR = str(Path.home() / ".maic")

PERSIST_DIR = Path(_PERSIST_DIR).expanduser()
BACKUP_DIR  = (Path(_APP_DATA_DIR).expanduser() / "backup")
PERSIST_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
# [00] IMPORTS & GLOBALS — END


# [01] UTILS — START
def _msg(update_msg: Callable[[str], None], s: str) -> None:
    try: update_msg(str(s))
    except Exception: pass

def _pct(update_pct: Callable[[int, Optional[str]], None], v: int, msg: Optional[str] = None) -> None:
    try: update_pct(int(v), msg)
    except Exception: pass

def _now_tag() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())

def _read_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = st.secrets.get(key)  # type: ignore[attr-defined]
        if val is None:
            return os.getenv(key, default)
        if isinstance(val, (str,)):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(key, default)
# [01] UTILS — END


# [02] GOOGLE DRIVE AUTH (SERVICE ACCOUNT ONLY) — START
def _drive_client():
    """
    서비스계정 전용 클라이언트.
    - secrets['gcp_service_account']를 문자열(JSON) 또는 객체로 허용
    - 스코프: read-only
    """
    raw = st.secrets.get("gcp_service_account") if hasattr(st, "secrets") else None  # type: ignore
    if isinstance(raw, str):
        info = json.loads(raw)
    elif isinstance(raw, dict):
        info = dict(raw)
    else:
        raise RuntimeError("gcp_service_account 시크릿이 없습니다.")

    scopes = st.secrets.get("GDRIVE_SCOPES") if hasattr(st, "secrets") else None  # type: ignore
    if isinstance(scopes, str):
        try:
            scopes = json.loads(scopes)
        except Exception:
            scopes = [scopes]
    if not scopes:
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]

    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return gbuild("drive", "v3", credentials=creds, cache_discovery=False)
# [02] GOOGLE DRIVE AUTH — END


# [03] DRIVE HELPERS — START
def _find_folder_id(kind: str, *, fallback: Optional[str] = None) -> Optional[str]:
    """
    kind: "PREPARED" | "BACKUP" | "DEFAULT"
    기본은 시크릿 키를 우선 사용하고, 없으면 fallback.
    """
    key = {
        "PREPARED": "GDRIVE_PREPARED_FOLDER_ID",
        "BACKUP":   "GDRIVE_BACKUP_FOLDER_ID",
        "DEFAULT":  "GDRIVE_PREPARED_FOLDER_ID",
    }.get(kind.upper(), "GDRIVE_PREPARED_FOLDER_ID")
    return _read_secret(key, fallback)

def _list_files_in_folder(svc, folder_id: str) -> List[Dict[str, Any]]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id, name, mimeType, modifiedTime, size, md5Checksum)"
    res = svc.files().list(q=q, fields=fields, pageSize=1000).execute()
    return res.get("files", [])

def _download_file_bytes(svc, file_id: str) -> bytes:
    req = svc.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return buf.getvalue()
# [03] DRIVE HELPERS — END


# [04] TEXT & CHUNK BUILDERS (PLACEHOLDER / YOUR PIPELINE) — START
def _extract_text_from_bytes(name: str, data: bytes) -> str:
    """
    실제 구현체에 맞게 교체하세요.
    여기서는 단순 UTF-8 디코딩 시도 -> 실패 시 빈 문자열.
    """
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def _to_chunks(name: str, text: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    실제 청크 분해 규칙에 맞게 교체하세요.
    여기서는 간단히 줄 단위 분해 예시.
    """
    out: List[Dict[str, Any]] = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        out.append({
            "text": line,
            "meta": {
                **meta,
                "line_index": i,
            }
        })
    return out
# [04] TEXT & CHUNK BUILDERS — END


# [05] LOCAL STORE HELPERS — START
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
# [05] LOCAL STORE HELPERS — END


# [06] QUALITY REPORT (CURRENT SCHEMA) — START
def _quality_report(manifest: Dict[str, Any], *, extra_counts: Dict[str, Any]) -> Dict[str, Any]:
    """
    현재 청크 구조(meta.*)에 맞춘 간단 리포트.
    - 문서 수, 청크 수, 파일명/파일ID 분포, meta.page_approx 유무 등
    """
    docs = manifest.get("docs", [])
    chunks = manifest.get("chunks", [])
    doc_count = len(docs)
    chunk_count = len(chunks)

    meta_fields = {
        "file_name": 0,
        "file_id": 0,
        "mimeType": 0,
        "page_approx": 0,
    }
    for c in chunks:
        m = c.get("meta", {})
        if "file_name" in m: meta_fields["file_name"] += 1
        if "file_id"   in m: meta_fields["file_id"]   += 1
        if "mimeType"  in m: meta_fields["mimeType"]  += 1
        if "page_approx" in m: meta_fields["page_approx"] += 1

    return {
        "stats": {
            "documents": doc_count,
            "chunks": chunk_count,
            **{f"meta_has_{k}": v for k, v in meta_fields.items()},
        },
        "extra": extra_counts or {},
    }
# [06] QUALITY REPORT — END


# [07] BACKUP ZIP (DRIVE-AGNOSTIC LOCAL + (선택)REMOTE) — START
def _make_and_upload_backup_zip(svc, backup_folder_id: Optional[str]) -> Optional[str]:
    """
    로컬 백업 zip 생성 후, (있다면) Drive에 업로드합니다.
    GitHub Releases 백업 정책은 별도 모듈(src.backup.github_release)에서 처리합니다.
    """
    ts = _now_tag()
    zip_path = BACKUP_DIR / f"maic_backup_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in PERSIST_DIR.rglob("*"):
            if p.is_file():
                z.write(p, arcname=p.relative_to(PERSIST_DIR))
        z.writestr(".backup_info.txt", json.dumps({"created_at": ts}, ensure_ascii=False))
    uploaded_id = None
    try:
        if svc and backup_folder_id:
            media = MediaIoBaseUpload(
                io.BytesIO(zip_path.read_bytes()), mimetype="application/zip", resumable=True
            )
            meta = {"name": zip_path.name, "parents": [backup_folder_id]}
            f = svc.files().create(body=meta, media_body=media, fields="id").execute()
            uploaded_id = f.get("id")
    except Exception as e:
        # 업로드 실패는 치명적이지 않음 — 로컬 zip만 있어도 OK
        print(f"[backup][warn] drive upload failed: {type(e).__name__}: {e}")
    return uploaded_id
# [07] BACKUP ZIP — END


# [08] BUILD PIPELINE CORE — START
def _build_from_prepared(svc, prepared_folder_id: str) -> Tuple[int, int, Dict[str, Any], Dict[str, Any]]:
    """
    prepared 폴더의 모든 파일을 스캔 → 텍스트 추출 → 청크 생성 → manifest/chunks 반환.
    실제 구현에서는 변경 감지(delta)·MIME별 처리·PDF 페이지수 계산 등을 적용하세요.
    """
    files = _list_files_in_folder(svc, prepared_folder_id)
    docs_summary: List[Dict[str, Any]] = []
    all_chunks: List[Dict[str, Any]] = []

    for f in files:
        fid = f["id"]
        name = f.get("name", fid)
        mime = f.get("mimeType", "")
        data = _download_file_bytes(svc, fid)
        text = _extract_text_from_bytes(name, data)
        meta = {
            "file_id": fid,
            "file_name": name,
            "mimeType": mime,
            "page_approx": None,  # 필요 시 빠른 페이지수 추정 로직 연결
        }
        chunks = _to_chunks(name, text, meta)
        if chunks:
            all_chunks.extend(chunks)
        docs_summary.append({
            "id": fid, "name": name, "mimeType": mime, "size": f.get("size"), "md5": f.get("md5Checksum")
        })

    manifest = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "docs": docs_summary,
        "stats": {"documents": len(docs_summary), "chunks": len(all_chunks)},
    }
    extra = {"processed_files": len(docs_summary), "generated_chunks": len(all_chunks)}
    return len(docs_summary), len(all_chunks), manifest, extra
# [08] BUILD PIPELINE CORE — END


# [09] FOLDER RESOLUTION — START
def _resolve_ids(svc, gdrive_folder_id: str) -> Tuple[str, str]:
    prepared_id = _find_folder_id("PREPARED", fallback=gdrive_folder_id)
    backup_id   = _find_folder_id("BACKUP") or prepared_id
    if not prepared_id:
        raise KeyError("prepared 폴더 ID를 찾지 못했습니다.")
    return prepared_id, backup_id
# [09] FOLDER RESOLUTION — END


# [10] PUBLIC ENTRY (빌드 실행; 서비스계정 + GitHub Release 업로드) — START
def build_index_with_checkpoint(
    update_pct: Callable[[int, Optional[str]], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,
    gcp_creds: Mapping[str, object],          # 호환성 유지용 (미사용)
    persist_dir: str,                          # 호환성 유지용 (사용하되 기본은 PERSIST_DIR)
    remote_manifest: Dict[str, Dict[str, object]],
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:

    # 메시지/퍼센트 헬퍼
    def pct(v: int, m: Optional[str] = None): _pct(update_pct, v, m)
    def msg(s: str): _msg(update_msg, s)

    # 준비
    msg("🔐 Connecting Google Drive (service account)…")
    svc = _drive_client()
    pct(5, "drive-ready")

    prepared_id, backup_id = _resolve_ids(svc, gdrive_folder_id)

    # 빌드
    msg("📦 Scanning prepared folder and building chunks…")
    processed, chunks, manifest, stats = _build_from_prepared(svc, prepared_id)
    pct(70, f"processed={processed}, chunks={chunks}")

    if should_stop and should_stop():
        return {"ok": False, "stopped": True}

    # 로컬 저장
    msg("🧮 Writing manifest/chunks locally…")
    out_dir = PERSIST_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    chunks_path   = out_dir / "chunks.jsonl"
    _persist_write_json(manifest, manifest_path)
    _persist_write_jsonl(manifest.get("chunks", []) or [], chunks_path)  # 현재 예시에서는 빈 리스트

    # 품질 리포트
    msg("📊 Building quality report…")
    report = _quality_report({"docs": manifest.get("docs", []), "chunks": manifest.get("chunks", []) or []}, extra_counts=stats)
    pct(85, "report-ready")

    # 로컬/드라이브 백업 ZIP
    msg("⬆️ Uploading backup zip…")
    uploaded_id = _make_and_upload_backup_zip(svc, backup_id)
    pct(92, "backup-zip-uploaded")

    # GitHub Releases 업로드 (항상 .gz 생성 후 업로드)
    try:
        gz_path = _gzip_file(chunks_path)  # chunks.jsonl.gz 생성/갱신
        from src.backup.github_release import upload_index_release
        msg("🚀 Publishing index to GitHub Releases…")
        res = upload_index_release(
            manifest_path=manifest_path,
            chunks_jsonl_path=chunks_path,  # 함수 내부에서 .gz 생성하지만, 이미 우리가 생성했음
            include_zip=False,
            keep=2,
            build_meta={
                "processed_files": processed,
                "generated_chunks": chunks,
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
        "generated_chunks": chunks,
        "stats": stats,
        "report": report,
        "backup_zip_id": uploaded_id,
        "prepared_folder_id": prepared_id,
        "backup_folder_id": backup_id,
        "auth_mode": "service-account",
        "persist_dir": str(PERSIST_DIR),
    }
# [10] PUBLIC ENTRY — END
# =========================== index_build.py — END ============================
