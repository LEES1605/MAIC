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

            tags = _extract_grammar_tags(ch)  # ← [ADD-1] 청크에서 문법 태그 추출
            
            rec = {
                "doc_id": f["id"],
                "doc_name": f.get("name"),
                "chunk_index": i,
                "text": ch,
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

def _page_range_linear(total_len: int, pages: Optional[int], start: int, end: int) -> Optional[str]:
    if not pages or total_len <= 0:
        return None
    def pos2pg(pos: int) -> int:
        p = int((max(0, min(pos, total_len-1)) / max(1, total_len-1)) * (pages - 1)) + 1
        return max(1, min(p, pages))
    sp, ep = pos2pg(start), pos2pg(max(start, end-1))
    return f"{sp}" if sp == ep else f"{sp}–{ep}"


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

def _quality_report(manifest: Dict[str, Any], extra_counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    chunks_path = PERSIST_DIR / "chunks.jsonl"
    lengths: List[int] = []
    by_mime: Dict[str, List[int]] = {}

    if chunks_path.exists():
        for ln in chunks_path.read_text(encoding="utf-8").splitlines():
            if not ln.strip(): continue
            try:
                obj = json.loads(ln)
                txt = obj.get("text", "")
                lnth = len(txt)
                lengths.append(lnth)
                mime = (obj.get("meta", {}) or {}).get("mime", "unknown")
                by_mime.setdefault(mime, []).append(lnth)
            except Exception:
                pass

    avg = round(sum(lengths) / len(lengths), 1) if lengths else None
    pct = _percentiles(lengths, [0.5, 0.9, 0.99])
    longest = max(lengths) if lengths else None
    shortest = min(lengths) if lengths else None

    mime_distribution: Dict[str, Any] = {}
    for m, vs in by_mime.items():
        mime_distribution[m] = {
            "docs": sum(1 for _ in vs),
            "avg_chunk_len": round(sum(vs)/len(vs), 1) if vs else None,
        }

    report = {
        "docs_total": len(manifest),
        "chunks_total": sum(m.get("chunk_count", 0) for m in manifest.values()),
        "avg_chunk_length_chars": avg,
        **pct,
        "longest_chunk_chars": longest,
        "shortest_chunk_chars": shortest,
        "mime_distribution": mime_distribution,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if extra_counts:
        for k in ("new_docs", "updated_docs", "unchanged_docs"):
            if k in extra_counts:
                report[k] = int(extra_counts[k])

    QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def _make_and_upload_backup_zip(service, backup_id: Optional[str]) -> Optional[str]:
    if not backup_id:
        return None
    ts = time.strftime("%Y%m%d-%H%M%S")
    zip_path = APP_DATA_DIR / f"index_backup_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        cj = PERSIST_DIR / "chunks.jsonl"
        if cj.exists(): zf.write(cj, arcname="chunks.jsonl")
        if MANIFEST_PATH.exists(): zf.write(MANIFEST_PATH, arcname="manifest.json")
        if QUALITY_REPORT_PATH.exists(): zf.write(QUALITY_REPORT_PATH, arcname="quality_report.json")
    try:
        return _upload_zip(service, backup_id, zip_path, zip_path.name)
    finally:
        try: zip_path.unlink(missing_ok=True)
        except Exception: pass


# ===== [09] QUICK PRECHECK (변경 여부만 빠르게) ===============================
def quick_precheck(gdrive_folder_id: Optional[str] = None) -> Dict[str, Any]:
    """
    prepared 폴더와 현재 manifest를 '메타데이터 수준'으로 빠르게 비교.
    - 변경 없음이면 {"changed": False, ...}
    - 변경 있으면 {"changed": True, reasons: [...], ...}
    """
    svc = _drive_client()
    prepared_id = _find_folder_id("PREPARED", fallback=gdrive_folder_id)
    if not prepared_id:
        raise KeyError("prepared 폴더 ID를 찾지 못했습니다.")

    files = _list_files(svc, prepared_id)
    man = _load_manifest(MANIFEST_PATH)

    def digest_from_files(fs: List[Dict[str, Any]]) -> str:
        parts = []
        for f in fs:
            parts.append(f"{f.get('id')}|{f.get('modifiedTime')}|{f.get('md5Checksum') or f.get('size') or ''}")
        return _sha1("|".join(parts))

    def digest_from_manifest(m: Dict[str, Any]) -> str:
        parts = []
        for fid, v in sorted(m.items()):
            parts.append(f"{fid}|{v.get('modifiedTime')}|{v.get('md5Checksum') or v.get('size') or ''}|{v.get('content_sha1','')}")
        return _sha1("|".join(parts))

    prep_digest = digest_from_files(files)
    mani_digest = digest_from_manifest(man)

    reasons: List[str] = []
    if len(files) != len(man):
        reasons.append(f"file_count_diff: prepared={len(files)} manifest={len(man)}")
    if prep_digest[:12] != mani_digest[:12]:
        reasons.append("digest_mismatch")

    changed = bool(reasons)
    sample = [{"name": f.get("name"), "mt": f.get("modifiedTime")} for f in files[:5]]

    return {
        "changed": changed,
        "reasons": reasons,
        "prepared_count": len(files),
        "manifest_docs": len(man),
        "prepared_digest": prep_digest,
        "manifest_digest": mani_digest,
        "prepared_sample": sample,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


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


# ===== [11] CLI (optional) ===================================================
if __name__ == "__main__":
    def _noop_pct(v: int, msg: str | None = None): ...
    def _noop_msg(s: str): ...
    res = build_index_with_checkpoint(_noop_pct, _noop_msg, gdrive_folder_id="", gcp_creds={}, persist_dir="", remote_manifest={})
    print(json.dumps(res, ensure_ascii=False, indent=2))
# =============================================================================
