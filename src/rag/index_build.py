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
    cid   = st.secrets.get("GDRIVE_OAUTH_CLIENT_ID") or st.secrets.get("GOOGLE_OAUTH_CLIENT_ID")
    csec  = st.secrets.get("GDRIVE_OAUTH_CLIENT_SECRET") or st.secrets.get("GOOGLE_OAUTH_CLIENT_SECRET")
    r_tok = st.secrets.get("GDRIVE_OAUTH_REFRESH_TOKEN") or st.secrets.get("GOOGLE_OAUTH_REFRESH_TOKEN")
    t_uri = st.secrets.get("GDRIVE_OAUTH_TOKEN_URI") or "https://oauth2.googleapis.com/token"
    if cid and csec and r_tok:
        from google.oauth2.credentials import Credentials as UserCredentials
        return UserCredentials(
            None,
            refresh_token=str(r_tok),
            client_id=str(cid),
            client_secret=str(csec),
            token_uri=str(t_uri),
            scopes=["https://www.googleapis.com/auth/drive"],
        )

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
    """kind: 'PREPARED' | 'BACKUP' | 'DEFAULT'"""
    key_sets = {
        "PREPARED": ("GDRIVE_PREPARED_FOLDER_ID", "PREPARED_FOLDER_ID", "APP_GDRIVE_FOLDER_ID"),
        "BACKUP":   ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID", "APP_BACKUP_FOLDER_ID"),
        "DEFAULT":  ("GDRIVE_FOLDER_ID",),
    }
    for key in key_sets.get(kind, ()):
        if key in st.secrets and str(st.secrets[key]).strip():
            return str(st.secrets[key]).strip()
    for path, val in _flatten_secrets(st.secrets):
        if isinstance(val, (str, int)) and str(val).strip():
            up = path.upper()
            if kind == "PREPARED" and "PREPARED" in up and "FOLDER_ID" in up:
                return str(val).strip()
            if kind == "BACKUP" and "BACKUP" in up and "FOLDER_ID" in up:
                return str(val).strip()
            if kind == "DEFAULT" and "GDRIVE_FOLDER_ID" in up:
                return str(val).strip()
    return fallback


# ===== [03] DRIVE CLIENT & FILE LIST ========================================
def _drive_client():
    from googleapiclient.discovery import build
    creds = _get_drive_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _list_files(service, folder_id: str) -> List[Dict[str, Any]]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id,name,mimeType,modifiedTime,md5Checksum,size),nextPageToken"
    files, token = [], None
    while True:
        resp = service.files().list(
            q=q, fields=fields, pageToken=token, pageSize=1000,
            includeItemsFromAllDrives=True, supportsAllDrives=True
        ).execute()
        files.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    files.sort(key=lambda x: x.get("name", ""))
    return files

def _find_latest_zip(service, folder_id: str):
    resp = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false and mimeType='application/zip'",
        orderBy="modifiedTime desc",
        fields="files(id,name,modifiedTime,size)", pageSize=1,
        includeItemsFromAllDrives=True, supportsAllDrives=True
    ).execute()
    f = resp.get("files", [])
    return f[0] if f else None

def _download_file_bytes(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    req = service.files().get_media(fileId=file_id, supportsAllDrives=True)
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
    created = service.files().create(
        body=meta, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return created.get("id")


# ===== [04] CONTENT EXTRACTORS (TXT/MD/GOOGLE DOCS/PDF; with cleaning) ======
GOOGLE_DOC = "application/vnd.google-apps.document"
TEXT_LIKE = {"text/plain", "text/markdown", "application/json"}
PDF_MIME  = "application/pdf"

def _clean_text_common(s: str) -> str:
    import re
    if not s:
        return ""
    s = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", s)         # exam-\nple → example
    s = re.sub(r"(?<=\S)\n(?=\S)", " ", s)               # ab\ncd → ab cd
    s = re.sub(r"[ \t]+", " ", s)                        # 다중 공백 축소
    s = re.sub(r"\n{3,}", "\n\n", s)                     # 빈 줄 정리
    return s.strip()

def _extract_text(service, file: Dict[str, Any], stats: Dict[str, int]) -> Optional[str]:
    mime = file.get("mimeType"); fid  = file["id"]

    if mime == GOOGLE_DOC:
        try:
            data = service.files().export(
                fileId=fid, mimeType="text/plain", supportsAllDrives=True
            ).execute()
            stats["gdocs"] = stats.get("gdocs", 0) + 1
            return _clean_text_common(data.decode("utf-8", errors="ignore"))
        except Exception:
            stats["gdocs"] = stats.get("gdocs", 0) + 1
            return None

    if mime in TEXT_LIKE:
        b = _download_file_bytes(service, fid)
        stats["text_like"] = stats.get("text_like", 0) + 1
        return _clean_text_common(b.decode("utf-8", errors="ignore"))

    if mime == PDF_MIME:
        try:
            import pypdf
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

    stats["others_skipped"] = stats.get("others_skipped", 0) + 1
    return None


# ===== [05] CHUNKING (paragraph-first) ======================================
def _norm_ws(s: str) -> str: return " ".join(s.split())

def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]

def _chunk_text(
    text: str,
    target_chars: int = 1000,
    *, overlap: Optional[int] = None, overlap_ratio: float = 0.12,
) -> List[str]:
    if not text.strip():
        return []

    paras = _split_paragraphs(text)
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    max_chars = max(400, int(target_chars))

    for p in paras:
        if cur and cur_len + len(p) + 1 > max_chars:
            joined = _norm_ws("\n".join(cur))
            chunks.append(joined)
            keep = int(max(0, min(overlap if overlap is not None else int(len(joined)*overlap_ratio), len(joined))))
            tail = joined[-keep:] if keep > 0 else ""
            cur, cur_len = ([tail] if tail else []), len(tail)
        cur.append(p)
        cur_len += len(p) + 1

    if cur:
        chunks.append(_norm_ws("\n".join(cur)))
    return chunks

# ===== [05A] GRAMMAR TAGGING (NEW) ==========================================
# 목적: 청크 텍스트에서 문법 키워드를 감지하여 grammar_tags: [...]를 생성합니다.
# 외부 YAML(선택)을 못 찾으면 내장 미니 사전을 사용합니다.

try:
    import yaml  # 선택 의존성: 없으면 자동 폴백
except Exception:
    yaml = None  # type: ignore

from pathlib import Path as _Path
import re as _re

# 우선순위: 홈 데이터 디렉토리 → 소스 폴더
_HOME_DATA_DIR = _Path.home() / ".maic"
_GRAMMAR_TAXONOMY_PATHS = [
    _HOME_DATA_DIR / "grammar_taxonomy.yaml",
    _Path(__file__).resolve().parent / "grammar_taxonomy.yaml",
]

_DEFAULT_GRAMMAR_TAXONOMY = {
    "관계대명사": ["which", "that", "relative pronoun"],
    "시제(과거)": ["did", "was", "were"],
    "가정법": ["if I were", "would have", "had + p.p."],
    "to부정사": ["to + V", "to + "],
    "동명사": [" V-ing ", "-ing"],
    "조동사": ["can", "could", "should", "must", "may", "might", "will", "would"],
}

def _load_grammar_taxonomy() -> dict:
    # YAML 혹은 JSON 딕셔너리 포맷 지원
    import json as _json
    for p in _GRAMMAR_TAXONOMY_PATHS:
        try:
            if p.exists() and p.is_file():
                raw = p.read_text(encoding="utf-8", errors="ignore")
                if yaml is not None:
                    y = yaml.safe_load(raw) or {}
                    if isinstance(y, dict):
                        return y
                # JSON 폴백
                try:
                    y = _json.loads(raw)
                    if isinstance(y, dict):
                        return y
                except Exception:
                    pass
        except Exception:
            pass
    return _DEFAULT_GRAMMAR_TAXONOMY

def _compile_taxonomy(tax: dict):
    rules = []
    for cat, kws in (tax or {}).items():
        if not isinstance(kws, (list, tuple)):
            continue
        pats = []
        for kw in kws:
            if not isinstance(kw, str) or not kw.strip():
                continue
            s = kw.strip()
            # 느슨한 패턴들
            if s.lower() in {"to + v", "to +", "to + v."}:
                pats.append(r"\bto\s+\w+")
                continue
            esc = _re.escape(s)
            pats.append(esc)
        if pats:
            rx = _re.compile("|".join(pats), _re.IGNORECASE)
            rules.append((str(cat), rx))
    return rules

_GRAMMAR_RULES = _compile_taxonomy(_load_grammar_taxonomy())

def _extract_grammar_tags(text: str):
    """텍스트에서 카테고리 매칭하여 태그 리스트 반환(중복 제거, 순서 보존)."""
    if not text or not _GRAMMAR_RULES:
        return []
    tags, seen, out = [], set(), []
    for cat, rx in _GRAMMAR_RULES:
        try:
            if rx.search(text):
                tags.append(cat)
        except Exception:
            continue
    for t in tags:
        if t not in seen:
            out.append(t); seen.add(t)
    return out


# ===== [06] MANIFEST & DELTA =================================================
def _sha1(s: str) -> str: return hashlib.sha1(s.encode("utf-8")).hexdigest()

def _load_manifest(path: Path) -> Dict[str, Dict[str, Any]]:
    if path.exists():
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}

def _save_manifest(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _need_update(prev: Dict[str, Any], now_meta: Dict[str, Any]) -> bool:
    if not prev: return True
    if prev.get("modifiedTime") != now_meta.get("modifiedTime"): return True
    if prev.get("md5Checksum") and now_meta.get("md5Checksum"):
        return prev["md5Checksum"] != now_meta["md5Checksum"]
    if prev.get("content_sha1") and now_meta.get("content_sha1"):
        return prev["content_sha1"] != now_meta["content_sha1"]
    return True


# ===== [07] BUILD FROM PREPARED =============================================
def _guess_section_hint(text: str) -> Optional[str]:
    import re
    if not text: return None
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    for ln in lines[:5]:
        if 8 <= len(ln) <= 120:
            if re.search(r"^(Chapter|Unit|Lesson|Section|Part)\s+[0-9IVX]+[:\-\.\s]", ln, re.I): return ln
            if re.fullmatch(r"[A-Za-z0-9\s\-\(\)\.\,']{8,120}", ln) and sum(c.isalpha() for c in ln) > len(ln)*0.5:
                return ln
    head = text.strip().split("\n", 1)[0]
    return (head[:80] + "…") if len(head) > 80 else (head or None)

def _pdf_page_count_quick(service, file_id: str) -> Optional[int]:
    try:
        import pypdf
        data = _download_file_bytes(service, file_id)
        return len(pypdf.PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return None

def _build_from_prepared(service, prepared_id: str) -> Tuple[int, int, Dict[str, Any], Dict[str, int]]:
    files = _list_files(service, prepared_id)
    manifest = _load_manifest(MANIFEST_PATH)
    prev_ids = set(manifest.keys())
    out_path = PERSIST_DIR / "chunks.jsonl"

    stats: Dict[str, int] = {
        "gdocs": 0, "text_like": 0, "pdf_parsed": 0, "pdf_skipped": 0, "others_skipped": 0,
        "new_docs": 0, "updated_docs": 0, "unchanged_docs": 0
    }
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
        if not text or not text.strip():
            continue

        now_meta = {**meta_base, "content_sha1": _sha1(text)}
        prev_meta = manifest.get(f["id"], {})

        need = _need_update(prev_meta, now_meta)
        if not need:
            stats["unchanged_docs"] += 1
            continue
        if f["id"] not in prev_ids:
            stats["new_docs"] += 1
        else:
            stats["updated_docs"] += 1

        chunks = _chunk_text(text, target_chars=1200, overlap=120)

        pages = _pdf_page_count_quick(service, f["id"]) if (f.get("mimeType") == "application/pdf") else None
        total_len = len(text)
        running_start = 0

        for i, ch in enumerate(chunks):
            start = running_start
            end = start + len(ch)
            keep = min(120, len(ch))
            running_start = end - keep

            rec = {
                "doc_id": f["id"],
                "doc_name": f.get("name"),
                "chunk_index": i,
                "text": ch,
                "grammar_tags": _extract_grammar_tags(ch),  # ← 태그 저장 (중요)
                "meta": {
                    "file_id": f["id"],
                    "file_name": f.get("name"),
                    "source_drive_url": f"https://drive.google.com/file/d/{f['id']}/view",
                    "mime": f.get("mimeType"),
                    "modified": f.get("modifiedTime"),
                    "page_approx": _page_range_linear(total_len, pages, start, end),
                    "section_hint": _guess_section_hint(ch),
                },
            }
            new_lines.append(json.dumps(rec, ensure_ascii=False))

        now_meta["chunk_count"] = len(chunks)
        manifest[f["id"]] = now_meta

        processed += 1
        total_chunks += len(chunks)
        changed_ids.add(f["id"])

    existing: List[str] = []
    if out_path.exists():
        existing = [ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    # ✅ BUGFIX: append를 for 루프 ‘안쪽’에서 수행 (빈 리스트여도 안전)
    filtered_existing: List[str] = []
    for ln in existing:
        try:
            obj = json.loads(ln)
            if obj.get("doc_id") in changed_ids:
                continue
        except Exception:
            pass
        filtered_existing.append(ln)  # ← 루프 내부

    merged = filtered_existing + new_lines
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
    _save_manifest(MANIFEST_PATH, manifest)

    return processed, total_chunks, manifest, stats

def _page_range_linear(total_len: int, pages: Optional[int], start: int, end: int) -> Optional[str]:
    if not pages or total_len <= 0:
        return None
    def pos2pg(pos: int) -> int:
        p = int((max(0, min(pos, total_len-1)) / max(1, total_len-1)) * (pages - 1)) + 1
        return max(1, min(p, pages))
    sp, ep = pos2pg(start), pos2pg(max(start, end-1))
    return f"{sp}" if sp == ep else f"{sp}–{ep}"

# ===== [08] BACKUP/RESTORE (Drive 최신 ZIP 복구 + 업로드, 폴더 ID 통일) ==========
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple
import io, os, json, zipfile, shutil, datetime as dt

try:
    PERSIST_DIR = PERSIST_DIR  # type: ignore[name-defined]
except Exception:
    PERSIST_DIR = Path.home() / ".maic" / "persist"

try:
    BACKUP_DIR = BACKUP_DIR  # type: ignore[name-defined]
except Exception:
    BACKUP_DIR = Path.home() / ".maic" / "backup"

# ──────────────────────────────────────────────────────────────────────────────
# 공통: Drive 서비스/폴더 ID 해석
def _drive_service():
    """Drive v3 read/write 서비스 생성 (OAuth 우선, SA 폴백). 실패 시 None."""
    try:
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.oauth2.service_account import Credentials as SACreds  # type: ignore
        import streamlit as st  # type: ignore

        cid  = st.secrets.get("GDRIVE_OAUTH_CLIENT_ID")
        csec = st.secrets.get("GDRIVE_OAUTH_CLIENT_SECRET")
        rft  = st.secrets.get("GDRIVE_OAUTH_REFRESH_TOKEN")
        if cid and csec and rft:
            token_uri = st.secrets.get("GDRIVE_TOKEN_URI", "https://oauth2.googleapis.com/token")
            data = {"client_id":cid, "client_secret":csec, "refresh_token":rft, "token_uri":token_uri}
            scopes = ["https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_authorized_user_info(data, scopes=scopes)
        else:
            raw = st.secrets.get("GDRIVE_SERVICE_ACCOUNT_JSON")
            if not raw:
                return None
            info = json.loads(raw) if isinstance(raw, str) else dict(raw)
            scopes = ["https://www.googleapis.com/auth/drive"]
            creds = SACreds.from_service_account_info(info, scopes=scopes)
        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        return svc
    except Exception:
        return None

def _pick_backup_folder_id(svc) -> Optional[str]:
    """시크릿에서 백업 폴더 ID를 찾고, 없으면 루트 아래의 'backup_zip' 폴더를 탐색."""
    try:
        import streamlit as st  # type: ignore
        # 1) 직접 지정 키
        for k in ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID", "gdrive_backup_folder_id"):
            v = st.secrets.get(k)
            if v:
                return str(v)
        # 2) 루트 ID가 있으면 그 아래에서 backup_zip 탐색
        root_id = None
        for k in ("GDRIVE_DATA_ROOT_FOLDER_ID", "DATA_ROOT_FOLDER_ID", "gdrive_data_root_folder_id"):
            v = st.secrets.get(k)
            if v:
                root_id = str(v); break
        if not (svc and root_id):
            return None
        q = f"'{root_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='backup_zip'"
        resp = svc.files().list(q=q, fields="files(id,name)", includeItemsFromAllDrives=True,
                                supportsAllDrives=True, corpora="allDrives", pageSize=10).execute()
        files = resp.get("files", [])
        if files:
            return files[0]["id"]
    except Exception:
        pass
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 복구(Drive 최신 ZIP 우선)
def _latest_drive_backup_zip(svc, backup_fid: str) -> Optional[Dict[str, Any]]:
    """backup_zip 폴더의 최신 ZIP 파일 메타를 반환."""
    resp = svc.files().list(
        q=f"'{backup_fid}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
        fields="files(id,name,modifiedTime,createdTime,size,mimeType)",
        includeItemsFromAllDrives=True, supportsAllDrives=True, corpora="allDrives", pageSize=1000
    ).execute()
    zips = [f for f in resp.get("files", []) if (f.get("name","").lower().endswith(".zip"))]
    if not zips:
        return None
    zips.sort(key=lambda x: x.get("modifiedTime") or x.get("createdTime") or "", reverse=True)
    return zips[0]

def _safe_clear_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for p in d.iterdir():
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except Exception:
            pass

def restore_latest_backup_to_local() -> Dict[str, Any]:
    """
    Drive backup_zip의 최신 ZIP을 로컬 PERSIST_DIR로 복구.
    실패 시, 로컬 BACKUP_DIR의 최근 ZIP으로 폴백.
    반환 예:
      {"ok": True, "source": "drive|local", "zip_name": "...", "persist_dir": "..."}
      {"ok": False, "error": "no_remote_backup|download_failed|extract_failed|no_local_backup"}
    """
    svc = _drive_service()
    backup_fid = _pick_backup_folder_id(svc)
    chosen = None
    source = None

    # 0) Drive에서 최신 ZIP 선택
    if svc and backup_fid:
        try:
            chosen = _latest_drive_backup_zip(svc, backup_fid)
            if chosen:
                source = "drive"
        except Exception:
            chosen = None

    # 1) Drive 실패 시: 로컬 BACKUP_DIR의 최신 ZIP 선택
    local_zip_path: Optional[Path] = None
    if chosen is None:
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            zips = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if zips:
                local_zip_path = zips[0]
                source = "local"
        except Exception:
            pass

    if chosen is None and local_zip_path is None:
        return {"ok": False, "error": "no_remote_backup"}

    # 2) ZIP 데이터 가져오기
    zip_bytes = None
    zip_name = ""
    if source == "drive" and chosen:
        try:
            from googleapiclient.http import MediaIoBaseDownload  # type: ignore
            req = svc.files().get_media(fileId=chosen["id"])
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(fd=buf, request=req)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            zip_bytes = buf.getvalue()
            zip_name = chosen.get("name", "backup.zip")
        except Exception:
            # Drive 다운로드 실패 → 로컬 폴백 시도
            zip_bytes = None
            chosen = None
    if zip_bytes is None and local_zip_path:
        try:
            zip_bytes = local_zip_path.read_bytes()
            zip_name = local_zip_path.name
            source = "local"
        except Exception:
            return {"ok": False, "error": "no_local_backup"}

    # 3) PERSIST_DIR 정리 후 압축 해제 + .ready 생성
    try:
        _safe_clear_dir(Path(PERSIST_DIR))
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            zf.extractall(str(PERSIST_DIR))
        # .ready 마커 생성(시간 포함)
        (Path(PERSIST_DIR) / ".ready").write_text(
            dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
        )
    except Exception as e:
        return {"ok": False, "error": f"extract_failed:{type(e).__name__}"}

    # 4) 복구에 사용한 ZIP을 로컬에도 캐시 저장(드라이브 소스인 경우)
    try:
        if source == "drive":
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            (BACKUP_DIR / f"restored_{ts}.zip").write_bytes(zip_bytes or b"")
    except Exception:
        pass

    return {"ok": True, "source": source, "zip_name": zip_name, "persist_dir": str(PERSIST_DIR)}

# ──────────────────────────────────────────────────────────────────────────────
# 백업 ZIP 업로드(동일 폴더 ID 사용)
def _make_and_upload_backup_zip(_: Any = None, __: Any = None) -> Dict[str, Any]:
    """
    PERSIST_DIR 내용을 ZIP으로 만들어 Drive backup_zip 폴더에 업로드.
    업로드/복구가 동일 폴더 ID를 사용하도록 _pick_backup_folder_id를 공유.
    """
    svc = _drive_service()
    backup_fid = _pick_backup_folder_id(svc)
    if not (svc and backup_fid):
        return {"ok": False, "error": "no_backup_folder_id"}

    # ZIP 만들기 (메모리)
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            base = Path(PERSIST_DIR)
            if not base.exists():
                return {"ok": False, "error": "persist_dir_missing"}
            for p in base.rglob("*"):
                if p.is_dir():
                    continue
                arc = str(p.relative_to(base))
                zf.write(str(p), arcname=arc)
        buf.seek(0)
    except Exception as e:
        return {"ok": False, "error": f"zip_create_failed:{type(e).__name__}"}

    # Drive 업로드
    try:
        from googleapiclient.http import MediaIoBaseUpload  # type: ignore
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"backup_{ts}.zip"
        media = MediaIoBaseUpload(buf, mimetype="application/zip", resumable=True)
        meta = {"name": filename, "parents": [backup_fid]}
        file = svc.files().create(body=meta, media_body=media, fields="id,name").execute()
        # 로컬 캐시도 남김
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (BACKUP_DIR / filename).write_bytes(buf.getvalue())
        return {"ok": True, "file_id": file.get("id"), "name": file.get("name")}
    except Exception as e:
        return {"ok": False, "error": f"upload_failed:{type(e).__name__}"}
# ===== [08] END ===============================================================



# ===== [09] QUICK PRECHECK (내용 중심, 변경 여부만 빠르게) ======================
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import io, json, zipfile

try:
    # 모듈 상단에서 이미 정의되어 있으면 그대로 사용
    PERSIST_DIR = PERSIST_DIR  # type: ignore[name-defined]
except Exception:
    PERSIST_DIR = Path.home() / ".maic" / "persist"

try:
    BACKUP_DIR = BACKUP_DIR  # type: ignore[name-defined]
except Exception:
    BACKUP_DIR = Path.home() / ".maic" / "backup"

# ── 비교에서 제외할 항목 규칙 ────────────────────────────────────────────────────
_EXCLUDED_GOOGLE_APPS = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
    "application/vnd.google-apps.script",
}
_EXCLUDED_NAME_SUFFIX = {".zip", ".ZIP"}
_EXCLUDED_NAME_MATCH = {"backup", "backup_zip", "~", ".tmp", ".temp", ".bak"}

def _is_excluded_item(name: str, mime: str) -> bool:
    if mime in _EXCLUDED_GOOGLE_APPS:
        return True
    low = (name or "").lower()
    if any(low.endswith(sfx.lower()) for sfx in _EXCLUDED_NAME_SUFFIX):
        return True
    if any(tok in low for tok in _EXCLUDED_NAME_MATCH):
        return True
    return False

# ── Drive 목록 → "내용 중심" 지문 만들기 ───────────────────────────────────────────
def _fingerprint_for_drive_item(item: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (kind, fp)
      - Google 네이티브: ('gdoc', id)  ← 제목/위치/modifiedTime 무시(오탐 방지)
      - 바이너리:       ('bin', md5 | size | id)
    """
    mime = item.get("mimeType", "") or ""
    fid  = item.get("id", "") or ""
    if mime.startswith("application/vnd.google-apps"):
        return ("gdoc", fid)
    # 업로드/바이너리
    md5  = (item.get("md5Checksum") or "").strip()
    size = str(item.get("size") or "").strip()
    if md5:
        return ("bin", md5)
    if size:
        return ("bin", f"size:{size}")
    return ("bin", f"id:{fid}")

def _list_prepared_from_drive(folder_id: Optional[str]) -> List[Dict[str, Any]]:
    """
    Drive에서 prepared 폴더의 파일 메타데이터 수집.
    """
    try:
        from googleapiclient.discovery import build  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.oauth2.service_account import Credentials as SACreds  # type: ignore
        import streamlit as st  # type: ignore

        # 자격증명 로딩 (OAuth 우선, SA 폴백)
        candidates = [
            ("oauth", "GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET", "GDRIVE_OAUTH_REFRESH_TOKEN"),
            ("sa",    "GDRIVE_SERVICE_ACCOUNT_JSON"),
        ]
        creds = None
        for kind, *keys in candidates:
            if kind == "oauth":
                cid, csec, rft = (st.secrets.get(keys[0]), st.secrets.get(keys[1]), st.secrets.get(keys[2]))
                if cid and csec and rft:
                    token_uri = st.secrets.get("GDRIVE_TOKEN_URI", "https://oauth2.googleapis.com/token")
                    data = {"client_id":cid, "client_secret":csec, "refresh_token":rft, "token_uri":token_uri}
                    creds = Credentials.from_authorized_user_info(data, scopes=["https://www.googleapis.com/auth/drive.readonly"])
                    break
            else:
                raw = st.secrets.get(keys[0])
                if raw:
                    info = json.loads(raw) if isinstance(raw, str) else dict(raw)
                    creds = SACreds.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
                    break
        if creds is None or not folder_id:
            return []

        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        q = f"'{folder_id}' in parents and trashed=false"
        fields = "files(id,name,mimeType,md5Checksum,size,modifiedTime)"
        items: List[Dict[str, Any]] = []
        page_token = None
        while True:
            resp = svc.files().list(
                q=q,
                fields="nextPageToken," + fields,
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                corpora="allDrives",
                pageSize=1000,
                spaces="drive",
            ).execute()
            for it in resp.get("files", []):
                if _is_excluded_item(it.get("name",""), it.get("mimeType","")):
                    continue
                items.append(it)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items
    except Exception:
        # Drive 접근 실패 시 빈 목록(오탐 방지)
        return []

def _fingerprint_set_for_prepared(folder_id: Optional[str]) -> Tuple[set, List[Tuple[str,str]]]:
    items = _list_prepared_from_drive(folder_id)
    fps: List[Tuple[str,str]] = []
    for it in items:
        kind, fp = _fingerprint_for_drive_item(it)
        fps.append((kind, fp))
    return set(fps), fps

# ── manifest 로딩(로컬 우선, 없으면 최신 ZIP에서 manifest.json 추출) ───────────────
def _load_manifest_dict() -> Optional[Dict[str, Any]]:
    # 1) 로컬
    mf = Path(PERSIST_DIR) / "manifest.json"
    if mf.exists():
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 2) 백업 ZIP(최신)
    bdir = Path(BACKUP_DIR)
    if bdir.exists():
        zips = sorted(bdir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        for z in zips:
            try:
                with zipfile.ZipFile(z, "r") as zf:
                    with zf.open("manifest.json") as fh:
                        data = fh.read()
                        return json.loads(data.decode("utf-8"))
            except Exception:
                continue
    return None

def _fingerprint_set_for_manifest(manifest: Dict[str, Any]) -> Tuple[set, List[Tuple[str,str]]]:
    """
    manifest 구조에 의존하지 않도록 보수적으로 해석:
      - google-apps.* → ('gdoc', id)
      - 그 외 → ('bin', md5 | size | id | content_sha1)
    """
    entries = manifest.get("files") or manifest.get("docs") or manifest.get("entries") or []
    fps: List[Tuple[str,str]] = []
    for e in entries:
        name = (e.get("name") or e.get("filename") or "")
        mime = (e.get("mimeType") or e.get("mime") or "")
        if _is_excluded_item(name, mime):
            continue
        fid  = (e.get("id") or e.get("file_id") or "")
        if mime.startswith("application/vnd.google-apps"):
            fps.append(("gdoc", fid))
            continue
        md5  = (e.get("md5") or e.get("md5Checksum") or "").strip()
        size = str(e.get("size") or e.get("bytes") or "").strip()
        csha = (e.get("content_sha1") or "").strip()
        if md5:
            fps.append(("bin", md5))
        elif size:
            fps.append(("bin", f"size:{size}"))
        elif csha:
            fps.append(("bin", f"sha1:{csha}"))
        else:
            fps.append(("bin", f"id:{fid}"))
    return set(fps), fps

# ── 공개 API: 빠른 사전점검 ───────────────────────────────────────────────────────
def quick_precheck(gdrive_folder_id: Optional[str] = None) -> Dict[str, Any]:
    """
    prepared 폴더의 '내용 중심' fingerprint 집합을
    마지막 인덱싱 manifest의 fingerprint 집합과 비교한다.
    """
    # prepared fingerprints
    try:
        prepared_set, _prepared_list = _fingerprint_set_for_prepared(gdrive_folder_id)
    except Exception as e:
        return {
            "changed": False,
            "reasons": [f"prepared_list_failed:{type(e).__name__}"],
            "prepared_count": 0,
            "manifest_count": 0,
            "samples": {"only_in_prepared": [], "only_in_manifest": []},
        }

    # manifest fingerprints
    manifest = _load_manifest_dict()
    if manifest is None:
        # manifest가 없으면 최초 빌드 필요로 간주(관리자 모드에서는 질문 유도)
        return {
            "changed": True,
            "reasons": ["no_local_manifest"],
            "prepared_count": len(prepared_set),
            "manifest_count": 0,
            "samples": {"only_in_prepared": list(map(str, list(prepared_set)[:5])), "only_in_manifest": []},
        }

    manifest_set, _manifest_list = _fingerprint_set_for_manifest(manifest)

    # 집합 비교(내용 중심)
    only_prepared = prepared_set - manifest_set
    only_manifest = manifest_set - prepared_set

    if not only_prepared and not only_manifest:
        return {
            "changed": False,
            "reasons": [],
            "prepared_count": len(prepared_set),
            "manifest_count": len(manifest_set),
            "samples": {"only_in_prepared": [], "only_in_manifest": []},
        }

    # 이름/위치 요인 제거 뒤 남는 차이는 실제 추가/삭제/콘텐츠 변경으로 간주
    return {
        "changed": True,
        "reasons": ["content_diff"],
        "prepared_count": len(prepared_set),
        "manifest_count": len(manifest_set),
        "samples": {
            "only_in_prepared": list(map(str, list(only_prepared)[:5])),
            "only_in_manifest": list(map(str, list(only_manifest)[:5])),
        },
    }
# ===== [09] END ===============================================================




# ===== [10] PUBLIC ENTRY (빌드 실행) =========================================
def build_index_with_checkpoint(
    update_pct: Callable[[int, str | None], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,
    gcp_creds: Mapping[str, object],
    persist_dir: str,
    remote_manifest: Dict[str, Dict[str, object]],
    should_stop: Callable[[], bool] | None = None,
) -> Dict[str, Any]:
    def _pct(v: int, msg: str | None = None):
        try: update_pct(int(v), msg)
        except Exception: pass
    def _msg(s: str):
        try: update_msg(str(s))
        except Exception: pass

    _msg("🔐 Preparing Google Drive client (OAuth first)…")
    svc = _drive_client()
    _pct(5, "drive-ready")

    prepared_id = _find_folder_id("PREPARED", fallback=gdrive_folder_id)
    backup_id   = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT")
    if not prepared_id:
        raise KeyError("prepared 폴더 ID를 찾지 못했습니다.")

    _msg("📦 Scanning prepared folder and building delta…")
    processed, chunks, manifest, stats = _build_from_prepared(svc, prepared_id)
    _pct(70, f"processed={processed}, chunks={chunks}")

    if should_stop and should_stop():
        return {"ok": False, "stopped": True}

    _msg("🧮 Writing quality report…")
    report = _quality_report(manifest, extra_counts=stats)
    _pct(85, "report-ready")

    _msg("⬆️ Uploading backup zip…")
    uploaded_id = _make_and_upload_backup_zip(svc, backup_id)
    _pct(92, "backup-zip-uploaded")

    # === NEW: GitHub Releases 업로드(최신 2개만 보존) ==========================
    try:
        from pathlib import Path as _P
        manifest_path = _P(PERSIST_DIR) / "manifest.json"
        chunks_path   = _P(PERSIST_DIR) / "chunks.jsonl"
        if manifest_path.exists() and chunks_path.exists():
            from src.backup.github_release import upload_index_release, GitHubReleaseError
            _msg("🚀 Publishing index to GitHub Releases…")
            res = upload_index_release(
                manifest_path=manifest_path,
                chunks_jsonl_path=chunks_path,
                include_zip=False,   # 필요 시 True로 변경 가능
                keep=2,
                build_meta={
                    "processed_files": processed,
                    "generated_chunks": chunks,
                    "prepared_folder_id": prepared_id,
                },
            )
            _msg(f"✅ GitHub Releases 완료: {res.get('tag')} / {res.get('assets')}")
        else:
            _msg("⚠️ manifest/chunks 누락으로 GitHub 업로드 생략")
    except ModuleNotFoundError as e:
        _msg(f"⚠️ 업로더 모듈 누락: {e}")
    except Exception as e:
        # 정책: 업로드 실패해도 인덱싱은 성공 처리 (다음 단계에서 UI 배너/재시도 연결)
        try:
            from src.backup.github_release import GitHubReleaseError  # noqa
            _msg(f"⚠️ GitHub 업로드 실패: {type(e).__name__}")
        except Exception:
            _msg(f"⚠️ GitHub 업로드 예외: {type(e).__name__}")

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
        "auth_mode": "oauth-first"
    }
# ===== [10] END ==============================================================


# ===== [10A] QUALITY REPORTER (품질 리포트 생성/저장/업로드) =====================
from pathlib import Path as _QPath
from typing import Any as _Any, Dict as _Dict, List as _List, Optional as _Opt
import json as _json, datetime as _dt
from collections import Counter as _Counter

# 상위에서 이미 정의되어 있으면 그대로 사용
try:
    PERSIST_DIR = PERSIST_DIR  # type: ignore[name-defined]
except Exception:
    PERSIST_DIR = _QPath.home() / ".maic" / "persist"

try:
    BACKUP_DIR = BACKUP_DIR  # type: ignore[name-defined]
except Exception:
    BACKUP_DIR = _QPath.home() / ".maic" / "backup"

try:
    QUALITY_REPORT_PATH = QUALITY_REPORT_PATH  # type: ignore[name-defined]
except Exception:
    QUALITY_REPORT_PATH = _QPath.home() / ".maic" / "quality_report.json"

def _now_iso_z() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _p95(_vals: _List[int]) -> int:
    if not _vals: return 0
    s = sorted(_vals); k = int(0.95 * (len(s) - 1))
    return s[k]

def _scan_chunks_for_quality(_chunks_path: _QPath, top_n: int = 20) -> _Dict[str, _Any]:
    total = with_tags = without_tags = 0
    char_total = word_total = 0
    char_lens: _List[int] = []; word_lens: _List[int] = []
    invalid_empty = invalid_non_str = dup_in_chunk = 0
    tag_freq: _Counter[str] = _Counter()
    missing_doc_id = missing_source = missing_page = 0
    invalid_samples: _List[_Dict[str, _Any]] = []
    missing_samples: _List[_Dict[str, _Any]] = []
    parse_errors: _List[str] = []

    def _push_invalid(s): 
        if len(invalid_samples) < 10: invalid_samples.append(s)
    def _push_missing(s): 
        if len(missing_samples) < 10: missing_samples.append(s)

    with _chunks_path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            ln = line.strip()
            if not ln: continue
            try:
                obj = _json.loads(ln)
            except Exception:
                if len(parse_errors) < 10: parse_errors.append(f"line {i}")
                continue

            text = obj.get("text") or obj.get("content") or ""
            if not isinstance(text, str): text = str(text or "")
            tlen = len(text); wlen = len(text.split())
            char_total += tlen; word_total += wlen
            char_lens.append(tlen); word_lens.append(wlen)
            total += 1

            tags = obj.get("grammar_tags") or []
            if not isinstance(tags, list):
                invalid_non_str += 1; _push_invalid({"line": i, "reason": "tags_not_list"}); tags = []
            if tags: with_tags += 1
            else:    without_tags += 1

            seen = set()
            for t in tags:
                if not isinstance(t, str):
                    invalid_non_str += 1; _push_invalid({"line": i, "tag": t, "reason": "non_string"}); continue
                t2 = t.strip()
                if not t2:
                    invalid_empty += 1; _push_invalid({"line": i, "tag": t, "reason": "empty"}); continue
                if t2 in seen:
                    dup_in_chunk += 1; _push_invalid({"line": i, "tag": t2, "reason": "dup_in_chunk"})
                seen.add(t2); tag_freq[t2] += 1

            if not obj.get("doc_id"):
                missing_doc_id += 1; _push_missing({"line": i, "field": "doc_id"})
            if not obj.get("source"):
                missing_source += 1; _push_missing({"line": i, "field": "source"})
            if obj.get("page") in (None, "", -1):
                missing_page += 1; _push_missing({"line": i, "field": "page"})

    return {
        "generated_at": _now_iso_z(),
        "summary": {
            "chunks": total,
            "with_tags": with_tags,
            "without_tags": without_tags,
            "with_tags_ratio": round(with_tags / total, 4) if total else 0.0,
        },
        "length": {
            "chars_avg": round(char_total / total, 2) if total else 0.0,
            "words_avg": round(word_total / total, 2) if total else 0.0,
            "chars_p95": _p95(char_lens),
            "words_p95": _p95(word_lens),
        },
        "tags": {
            "freq_top": tag_freq.most_common(int(top_n or 20)),
            "unique_count": len(tag_freq),
            "invalid": {
                "empty": invalid_empty,
                "non_str": invalid_non_str,
                "dup_in_chunk": dup_in_chunk,
                "samples": invalid_samples,
            },
        },
        "missing_fields": {
            "doc_id": missing_doc_id,
            "source": missing_source,
            "page": missing_page,
            "samples": missing_samples,
        },
        "parse_errors": parse_errors,
    }

def _upload_quality_report_to_drive(_report_dict: _Dict[str, _Any]) -> _Dict[str, _Any]:
    # [08] 구획의 드라이브 헬퍼 재사용
    _svc_fn = globals().get("_drive_service")
    _pick_fn = globals().get("_pick_backup_folder_id")
    try:
        if callable(_svc_fn) and callable(_pick_fn):
            svc = _svc_fn(); fid = _pick_fn(svc)
            if svc and fid:
                from googleapiclient.http import MediaInMemoryUpload  # type: ignore
                data = _json.dumps(_report_dict, ensure_ascii=False).encode("utf-8")
                media = MediaInMemoryUpload(data, mimetype="application/json", resumable=False)
                name = f"quality_report_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.json"
                meta = {"name": name, "parents": [fid], "mimeType": "application/json"}
                out = svc.files().create(body=meta, media_body=media, fields="id,name").execute()
                return {"ok": True, "file_id": out.get("id"), "name": out.get("name")}
    except Exception as e:
        return {"ok": False, "error": f"upload_failed:{type(e).__name__}"}
    return {"ok": False, "error": "no_drive_or_folder"}

def _quality_report(manifest: _Dict[str, _Any] | None = None, *, extra_counts: _Dict[str,int] | None = None, top_n: int = 20) -> _Dict[str, _Any]:
    """
    [10] PUBLIC ENTRY와의 호환용 함수.
    - 현재 persist/chunks.jsonl을 스캔해 리포트를 만들고
      1) 로컬 QUALITY_REPORT_PATH
      2) 로컬 BACKUP_DIR/quality_report_YYYYMMDD_HHMM.json
      3) Drive backup_zip(가능하면) 에 업로드까지 수행.
    - manifest/extra_counts는 요약에 포함만 한다(호환 목적).
    """
    chunks = _QPath(PERSIST_DIR) / "chunks.jsonl"
    if not chunks.exists():
        return {"ok": False, "error": "chunks_missing", "path": str(chunks)}

    rep = _scan_chunks_for_quality(chunks, top_n=top_n)
    if manifest is not None:
        rep["manifest_brief"] = {"entries": len(manifest or {})}
    if extra_counts:
        rep["build_stats"] = dict(extra_counts)

    # 1) 로컬 저장
    QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT_PATH.write_text(_json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) 로컬 백업 디렉토리에도 타임스탬프 파일로 캐시
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M")
        (BACKUP_DIR / f"quality_report_{ts}.json").write_text(
            _json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass

    # 3) Drive 업로드
    uploaded = _upload_quality_report_to_drive(rep)

    return {"ok": True, "path": str(QUALITY_REPORT_PATH), "uploaded": uploaded, "summary": rep.get("summary")}

def autorun_quality_scan_if_stale(top_n: int = 20) -> _Dict[str, _Any]:
    """
    chunks.jsonl이 더 새로우면 자동으로 품질 리포트를 갱신.
    """
    cj = _QPath(PERSIST_DIR) / "chunks.jsonl"
    qr = _QPath(QUALITY_REPORT_PATH)
    if not cj.exists():
        return {"ok": False, "error": "chunks_missing"}
    try:
        cj_m = cj.stat().st_mtime
        qr_m = qr.stat().st_mtime if qr.exists() else 0
        if (not qr.exists()) or (qr_m + 1 < cj_m):
            return _quality_report(None, extra_counts=None, top_n=top_n)
        return {"ok": True, "skipped": True}
    except Exception as e:
        return {"ok": False, "error": f"autorun_failed:{type(e).__name__}"}
# ===== [10A] END =============================================================

# ===== [11] CLI (optional) ===================================================
if __name__ == "__main__":
    def _noop_pct(v: int, msg: str | None = None): ...
    def _noop_msg(s: str): ...
    res = build_index_with_checkpoint(_noop_pct, _noop_msg, gdrive_folder_id="", gcp_creds={}, persist_dir="", remote_manifest={})
    print(json.dumps(res, ensure_ascii=False, indent=2))
# =============================================================================
