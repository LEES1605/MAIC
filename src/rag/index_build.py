# ===== [01] IMPORTS & CONSTANTS =============================================
from __future__ import annotations

import io, os, json, time, hashlib, zipfile
from pathlib import Path
from typing import Callable, Dict, Mapping, Any, List, Tuple, Optional

import streamlit as st

REQ_FILES = ["chunks.jsonl", "manifest.json", "quality_report.json"]

# 로컬 저장 경로 기본값 (src/config가 있으면 우선 사용)
try:
    from src.config import APP_DATA_DIR as _APP
    from src.config import PERSIST_DIR as _PERSIST
    from src.config import MANIFEST_PATH as _MANIFEST
    from src.config import QUALITY_REPORT_PATH as _QRP
    APP_DATA_DIR = Path(_APP)
    PERSIST_DIR = Path(_PERSIST)
    MANIFEST_PATH = Path(_MANIFEST)
    QUALITY_REPORT_PATH = Path(_QRP)
except Exception:
    APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR") or (Path.home() / ".maic"))
    PERSIST_DIR = APP_DATA_DIR / "persist"
    MANIFEST_PATH = APP_DATA_DIR / "manifest.json"
    QUALITY_REPORT_PATH = APP_DATA_DIR / "quality_report.json"

PERSIST_DIR.mkdir(parents=True, exist_ok=True)
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ===== [02] SECRETS & AUTH (USER OAUTH 우선, SA 폴백) ========================
# - 개인용 드라이브: OAuth 사용자 토큰으로 접근
#   필수 키: GDRIVE_OAUTH_CLIENT_ID, GDRIVE_OAUTH_CLIENT_SECRET, GDRIVE_OAUTH_REFRESH_TOKEN
# - 없으면 서비스계정 JSON을 사용(공유로 권한 부여된 폴더만 접근 가능)

def _flatten_secrets(obj: Any, prefix: str = "") -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    try:
        from collections.abc import Mapping as _Map
        if isinstance(obj, _Map):
            for k, v in obj.items():
                p = f"{prefix}.{k}" if prefix else str(k)
                out.extend(_flatten_secrets(v, p))
        else:
            out.append((prefix, obj))
    except Exception:
        out.append((prefix, obj))
    return out

def _get_drive_credentials():
    """OAuth 사용자 자격을 먼저 시도, 실패 시 서비스계정으로 폴백."""
    # 1) USER OAUTH (개인 드라이브)
    cid   = st.secrets.get("GDRIVE_OAUTH_CLIENT_ID") or st.secrets.get("GOOGLE_OAUTH_CLIENT_ID")
    csec  = st.secrets.get("GDRIVE_OAUTH_CLIENT_SECRET") or st.secrets.get("GOOGLE_OAUTH_CLIENT_SECRET")
    r_tok = st.secrets.get("GDRIVE_OAUTH_REFRESH_TOKEN") or st.secrets.get("GOOGLE_OAUTH_REFRESH_TOKEN")
    t_uri = st.secrets.get("GDRIVE_OAUTH_TOKEN_URI") or "https://oauth2.googleapis.com/token"
    if cid and csec and r_tok:
        try:
            from google.oauth2.credentials import Credentials as UserCredentials
            creds = UserCredentials(
                None,
                refresh_token=str(r_tok),
                client_id=str(cid),
                client_secret=str(csec),
                token_uri=str(t_uri),
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            return creds
        except Exception as e:
            # OAuth 자격 생성 실패 시, 서비스계정으로 폴백 시도
            pass

    # 2) SERVICE ACCOUNT (공유 필요)
    #    흔한 키들 먼저 본 뒤, 전체 시크릿을 훑어 service_account JSON 자동 탐색
    candidates = (
        "GDRIVE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "SERVICE_ACCOUNT_JSON",
        "gdrive_service_account_json",
        "service_account_json",
        "GCP_SERVICE_ACCOUNT",
        "gcp_service_account",
    )
    raw = None
    for k in candidates:
        if k in st.secrets and str(st.secrets[k]).strip():
            raw = st.secrets[k]; break
    if raw is None:
        for _, v in _flatten_secrets(st.secrets):
            try:
                from collections.abc import Mapping as _Map
                if isinstance(v, _Map) and v.get("type") == "service_account" and "client_email" in v and "private_key" in v:
                    raw = v; break
                if isinstance(v, str) and '"type": "service_account"' in v:
                    raw = v; break
            except Exception:
                pass
    if raw is None:
        raise KeyError(
            "Drive 자격정보를 찾지 못했습니다. "
            "(OAuth: GDRIVE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN 또는 "
            "Service Account JSON 중 하나가 필요)"
        )

    info = json.loads(raw) if isinstance(raw, str) else dict(raw)
    from google.oauth2.service_account import Credentials as SACredentials
    return SACredentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"])

def _find_folder_id(kind: str, fallback: Optional[str] = None) -> Optional[str]:
    """
    kind: 'PREPARED' | 'BACKUP' | 'DEFAULT'
    - PREPARED: 수업자료/문법서가 있는 폴더 (my-ai-teacher-data/prepared)
    - BACKUP  : 최적화 후 업로드하는 ZIP 보관 폴더 (my-ai-teacher-data/backup_zip)
    - DEFAULT : 일반 기본 폴더 ID
    """
    key_sets = {
        "PREPARED": ("GDRIVE_PREPARED_FOLDER_ID", "PREPARED_FOLDER_ID"),
        "BACKUP": ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID"),
        "DEFAULT": ("GDRIVE_FOLDER_ID",),
    }
    for key in key_sets.get(kind, ()):
        if key in st.secrets and str(st.secrets[key]).strip():
            return str(st.secrets[key]).strip()

    # 중첩 섹션 안까지 전수조사
    for path, val in _flatten_secrets(st.secrets):
        if isinstance(val, (str, int)) and "FOLDER_ID" in path.upper() and str(val).strip():
            up = path.upper()
            if kind == "PREPARED" and "PREPARED" in up:
                return str(val).strip()
            if kind == "BACKUP" and "BACKUP" in up:
                return str(val).strip()
            if kind == "DEFAULT" and "GDRIVE_FOLDER_ID" in up:
                return str(val).strip()
    return fallback


# ===== [03] DRIVE CLIENT & FILE LIST ========================================
def _drive_client():
    """사용자 OAuth 또는 서비스계정으로 Drive 클라이언트를 생성."""
    try:
        from googleapiclient.discovery import build
    except Exception as e:
        raise RuntimeError("google-api-python-client 패키지가 필요합니다.") from e
    creds = _get_drive_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _list_files(service, folder_id: str) -> List[Dict[str, Any]]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id,name,mimeType,modifiedTime,md5Checksum,size),nextPageToken"
    files, token = [], None
    while True:
        resp = service.files().list(q=q, fields=fields, pageToken=token, pageSize=1000).execute()
        files.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    files.sort(key=lambda x: x.get("name", ""))
    return files

def _find_latest_zip(service, folder_id: str):
    q = f"'{folder_id}' in parents and trashed=false and mimeType='application/zip'"
    resp = service.files().list(q=q, orderBy="modifiedTime desc",
                                fields="files(id,name,modifiedTime,size)", pageSize=1).execute()
    f = resp.get("files", [])
    return f[0] if f else None

def _download_file_bytes(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    req = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    done = False
    downloader = MediaIoBaseDownload(buf, req)
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf.read()

def _download_file_to(service, file_id: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(_download_file_bytes(service, file_id))

def _upload_zip(service, folder_id: str, path: Path, name: str) -> str:
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(path), mimetype="application/zip", resumable=False)
    meta = {"name": name, "parents": [folder_id], "mimeType": "application/zip"}
    created = service.files().create(body=meta, media_body=media, fields="id").execute()
    return created.get("id")


# ===== [04] CONTENT EXTRACTORS (TXT/MD/GOOGLE DOCS/PDF; with cleaning) ======
GOOGLE_DOC = "application/vnd.google-apps.document"
TEXT_LIKE = {"text/plain", "text/markdown", "application/json"}
PDF_MIME  = "application/pdf"

def _clean_text_common(s: str) -> str:
    """문단/줄바꿈/공백 정리: 하이픈 줄바꿈, 중복 공백, 빈 줄 제거."""
    import re
    if not s:
        return ""
    # 1) 줄말 하이픈 제거: "exam-\nple" → "example"
    s = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", s)
    # 2) 단어 중간 불필요 개행 제거: "ab\ncd" → "ab cd"
    s = re.sub(r"(?<=\S)\n(?=\S)", " ", s)
    # 3) 여러 연속 공백/탭 축소
    s = re.sub(r"[ \t]+", " ", s)
    # 4) 페이지 단위 빈 줄 정리
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _extract_text(service, file: Dict[str, Any], stats: Dict[str, int]) -> Optional[str]:
    """
    파일을 텍스트로 추출하고 클린업.
    반환: 정제된 텍스트(str) 또는 None(미지원/실패)
    """
    mime = file.get("mimeType")
    fid  = file["id"]

    # Google Docs → export(text/plain)
    if mime == GOOGLE_DOC:
        try:
            data = service.files().export(fileId=fid, mimeType="text/plain").execute()
            stats["gdocs"] = stats.get("gdocs", 0) + 1
            return _clean_text_common(data.decode("utf-8", errors="ignore"))
        except Exception:
            stats["gdocs"] = stats.get("gdocs", 0) + 1
            return None

    # 텍스트 계열 → 바이너리 다운로드 후 decode
    if mime in TEXT_LIKE:
        b = _download_file_bytes(service, fid)
        stats["text_like"] = stats.get("text_like", 0) + 1
        return _clean_text_common(b.decode("utf-8", errors="ignore"))

    # PDF → PyPDF 사용(없으면 스킵)
    if mime == PDF_MIME:
        try:
            import pypdf  # 설치 필요: pyproject.toml에 pypdf 추가됨
            data = _download_file_bytes(service, fid)
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages = []
            for p in reader.pages:
                try:
                    pages.append(p.extract_text() or "")
                except Exception:
                    pages.append("")
            txt = "\n\n".join(pages)
            stats["pdf_parsed"] = stats.get("pdf_parsed", 0) + 1
            return _clean_text_common(txt)
        except Exception:
            stats["pdf_skipped"] = stats.get("pdf_skipped", 0) + 1
            return None

    # 그 외는 스킵 (docx 등은 다음 단계에서 확장)
    stats["others_skipped"] = stats.get("others_skipped", 0) + 1
    return None



# ===== [05] CHUNKING (paragraph-first, supports both overlap modes) ==========
from typing import Optional, List

def _norm_ws(s: str) -> str:
    return " ".join(s.split())

def _split_paragraphs(text: str) -> List[str]:
    """빈 줄/개행 기반 문단 분할(지나친 쪼개짐 방지)."""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    return paras

def _chunk_text(
    text: str,
    target_chars: int = 1000,        # 권장 800~1200
    *,                                 # 아래 인자는 키워드 전용(호환성 보장)
    overlap: Optional[int] = None,     # 글자 수 기준 오버랩(예: 120). 기존 코드 호환용.
    overlap_ratio: float = 0.12,       # 비율 기준 오버랩(예: 0.12 = 12%)
) -> List[str]:
    """
    문단 우선 청크 분할.
    - overlap 이 주어지면 '글자 수'로 적용 (기존 호출과 호환: overlap=120)
    - overlap 이 None이면 overlap_ratio(비율)로 적용
    """
    if not text.strip():
        return []

    paras = _split_paragraphs(text)
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    max_chars = max(400, int(target_chars))  # 최소 하한선

    for p in paras:
        seg = p
        # 현재 청크에 더 붙이면 타겟 길이를 초과하는 경우 잘라서 내보냄
        if cur and cur_len + len(seg) + 1 > max_chars:
            joined = _norm_ws("\n".join(cur))
            chunks.append(joined)

            # --- 소프트 오버랩 계산 -----------------------------------------
            if overlap is not None:
                keep = int(max(0, min(overlap, len(joined))))
            else:
                keep = int(max(0, min(int(len(joined) * overlap_ratio), len(joined))))
            tail = joined[-keep:] if keep > 0 else ""
            # 다음 청크 시작 버퍼
            cur, cur_len = ([tail] if tail else []), len(tail)
            # ----------------------------------------------------------------

        cur.append(seg)
        cur_len += len(seg) + 1

    if cur:
        chunks.append(_norm_ws("\n".join(cur)))
    return chunks


# ===== [06] MANIFEST & DELTA =================================================
def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _load_manifest(path: Path) -> Dict[str, Dict[str, Any]]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_manifest(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _need_update(prev: Dict[str, Any], now_meta: Dict[str, Any]) -> bool:
    if not prev:
        return True
    if prev.get("modifiedTime") != now_meta.get("modifiedTime"):
        return True
    if prev.get("md5Checksum") and now_meta.get("md5Checksum"):
        return prev["md5Checksum"] != now_meta["md5Checksum"]
    if prev.get("content_sha1") and now_meta.get("content_sha1"):
        return prev["content_sha1"] != now_meta["content_sha1"]
    return True


# ===== [07] BUILD FROM PREPARED =============================================
def _build_from_prepared(service, prepared_id: str) -> Tuple[int, int, Dict[str, Any], Dict[str, int]]:
    """
    prepared 폴더의 파일들을 읽어 chunks.jsonl/manifest.json을 갱신한다.
    반환: (processed_files, generated_chunks, manifest, stats)
    """
    files = _list_files(service, prepared_id)
    manifest = _load_manifest(MANIFEST_PATH)
    out_path = PERSIST_DIR / "chunks.jsonl"

    stats = {"gdocs": 0, "text_like": 0, "pdf_parsed": 0, "pdf_skipped": 0, "others_skipped": 0}
    new_lines: List[str] = []
    processed, total_chunks = 0, 0
    changed_ids: set[str] = set()

    for f in files:
        meta_base = {
            "id": f["id"],
            "name": f.get("name"),
            "mimeType": f.get("mimeType"),
            "modifiedTime": f.get("modifiedTime"),
            "md5Checksum": f.get("md5Checksum"),
            "size": f.get("size"),
        }
        text = _extract_text(service, f, stats)
        if text is None or not text.strip():
            continue

        now_meta = {**meta_base, "content_sha1": _sha1(text)}
        prev_meta = manifest.get(f["id"], {})

        if not _need_update(prev_meta, now_meta):
            continue

        chunks = _chunk_text(text, target_chars=1200, overlap=120)
        for i, ch in enumerate(chunks):
            rec = {
                "doc_id": f["id"],
                "doc_name": f.get("name"),
                "chunk_index": i,
                "text": ch,
                "meta": {"mime": f.get("mimeType"), "modified": f.get("modifiedTime")},
            }
            new_lines.append(json.dumps(rec, ensure_ascii=False))
        now_meta["chunk_count"] = len(chunks)
        manifest[f["id"]] = now_meta

        processed += 1
        total_chunks += len(chunks)
        changed_ids.add(f["id"])

    # 기존 라인 보존 + 변경된 doc_id의 라인은 제거
    existing: List[str] = []
    if out_path.exists():
        existing = [ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    filtered_existing = []
    for ln in existing:
        try:
            obj = json.loads(ln)
            if obj.get("doc_id") in changed_ids:
                continue
        except Exception:
            pass
        filtered_existing.append(ln)

    merged = filtered_existing + new_lines
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
    _save_manifest(MANIFEST_PATH, manifest)

    return processed, total_chunks, manifest, stats


# ===== [08] QUALITY REPORT & BACKUP ZIP =====================================
def _percentiles(values: List[int], ps: List[float]) -> Dict[str, Optional[int]]:
    if not values:
        return {f"p{int(p*100)}": None for p in ps}
    vals = sorted(values)
    out: Dict[str, Optional[int]] = {}
    for p in ps:
        k = int(round((len(vals) - 1) * p))
        out[f"p{int(p*100)}"] = vals[k]
    return out

def _quality_report(manifest: Dict[str, Any]) -> Dict[str, Any]:
    chunks_path = PERSIST_DIR / "chunks.jsonl"
    lengths: List[int] = []
    if chunks_path.exists():
        for ln in chunks_path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                obj = json.loads(ln)
                lengths.append(len(obj.get("text", "")))
            except Exception:
                pass

    avg = round(sum(lengths) / len(lengths), 1) if lengths else None
    pct = _percentiles(lengths, [0.5, 0.9, 0.99])

    # MIME 분포
    mime_dist: Dict[str, int] = {}
    for m in manifest.values():
        mime = m.get("mimeType", "unknown")
        mime_dist[mime] = mime_dist.get(mime, 0) + 1

    report = {
        "docs_total": len(manifest),
        "chunks_total": sum(m.get("chunk_count", 0) for m in manifest.values()),
        "avg_chunk_length_chars": avg,
        **pct,
        "mime_distribution": mime_dist,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report



# ===== [09] PUBLIC ENTRY (APP에서 호출) ======================================
def build_index_with_checkpoint(
    update_pct: Callable[[int, str | None], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,                 # (호환 위해 유지: prepared ID로 사용 가능)
    gcp_creds: Mapping[str, object],
    persist_dir: str,                      # (호환, 현재 내부 PERSIST_DIR 사용)
    remote_manifest: Dict[str, Dict[str, object]],
    should_stop: Callable[[], bool] | None = None,
) -> Dict[str, Any]:
    """
    목표:
      - 앱 첫 실행 시: prepared 폴더 내용을 최적화하여 로컬 인덱스 생성
      - 이후 prepared에 새 파일이 추가되면: 델타만 누적 반영
      - 항상 완료 후 backup_zip 폴더에 zip 업로드(있으면)
    반환: 처리 요약(dict)
    """
    # 안전 콜백
    def _pct(v: int, msg: str | None = None):
        try:
            update_pct(int(v), msg)
        except Exception:
            pass
    def _msg(s: str):
        try:
            update_msg(str(s))
        except Exception:
            pass

    _msg("🔐 Preparing Google Drive client (OAuth first)…")
    svc = _drive_client()
    _pct(5, "drive-ready")

    # 폴더 ID 결정
    prepared_id = _find_folder_id("PREPARED", fallback=gdrive_folder_id)
    backup_id   = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT")
    if not prepared_id:
        raise KeyError("prepared 폴더 ID를 찾지 못했습니다. (GDRIVE_PREPARED_FOLDER_ID / PREPARED_FOLDER_ID / gdrive_folder_id 인자)")

    # 요구사항: 백업 ZIP이 있어도 항상 prepared 기준 델타 빌드로 누적 반영
    _msg("📦 Scanning prepared folder and building delta…")
    processed, chunks, manifest, stats = _build_from_prepared(svc, prepared_id)
    _pct(70, f"processed={processed}, chunks={chunks}")

    if should_stop and should_stop():
        return {"ok": False, "stopped": True}

    _msg("🧮 Writing quality report…")
    report = _quality_report(manifest)
    _pct(85, "report-ready")

    _msg("⬆️ Uploading backup zip…")
    uploaded_id = _make_and_upload_backup_zip(svc, backup_id)
    _pct(100, "done")

    return {
        "ok": True,
        "processed_files": processed,
        "generated_chunks": chunks,
        "stats": stats,
        "report": report,
        "backup_zip_id": uploaded_id,
        "prepared_folder_id": prepared_id,
        "backup_folder_id": backup_id,
        "auth_mode": "oauth-first"  # 디버그용
    }


# ===== [10] (선택) CLI 테스트용 엔트리 =======================================
if __name__ == "__main__":
    def _noop_pct(v: int, msg: str | None = None): ...
    def _noop_msg(s: str): ...
    res = build_index_with_checkpoint(_noop_pct, _noop_msg, gdrive_folder_id="", gcp_creds={}, persist_dir="", remote_manifest={})
    print(json.dumps(res, ensure_ascii=False, indent=2))
# =============================================================================
