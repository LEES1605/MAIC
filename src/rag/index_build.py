# [01] 기본 설정 & 상수  # [01] START
from __future__ import annotations

import os
import io
import json
import time
import hashlib
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple, Iterable, Optional

# ── 로컬 퍼시스트 경로(인덱스/매니페스트 저장소)
PERSIST_DIR = Path.home() / ".maic" / "persist"
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# ── 인덱싱 대상 확장자(감지/인덱싱 모두 동일 규칙 사용)
ALLOWED_EXTS = (".md", ".txt", ".pdf", ".csv", ".zip")

# ── manifest 파일 경로
MANIFEST_PATH = PERSIST_DIR / "manifest.json"

# ── 준비 폴더(Drive) 이름 기본값 또는 환경변수로 ID 직접 지정
PREPARED_FOLDER_NAME = os.getenv("MAIC_PREPARED_FOLDER_NAME", "prepared")
PREPARED_FOLDER_ID   = os.getenv("MAIC_PREPARED_FOLDER_ID")  # 있으면 이 ID를 직접 사용

# ── Google API: SERVICE ACCOUNT JSON 경로 (환경변수 우선)
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# ── 최대 파일 크기 제한(안전)
MAX_BYTES = 64 * 1024 * 1024  # 64MB
# [01] END


# [02] 로깅 유틸  # [02] START
def _log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[index_build][{ts}] {msg}", flush=True)
# [02] END


# [03] Google Drive 클라이언트 & 헬퍼  # [03] START
def _drive_client():
    """
    Google Drive API v3 클라이언트 생성.
    - 서비스 계정(JSON) 또는 ADC(Application Default Credentials) 사용.
    """
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]

    if GOOGLE_APPLICATION_CREDENTIALS and Path(GOOGLE_APPLICATION_CREDENTIALS).exists():
        creds = Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS, scopes=scopes)
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # ADC 시도(Cloud Run/GCE 등)
    try:
        import google.auth
        creds, _ = google.auth.default(scopes=scopes)
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        raise RuntimeError(f"Drive 인증 실패: {e}")


def _find_folder_id(svc, prefer_id: Optional[str] = None, name: Optional[str] = None) -> Optional[str]:
    """폴더 ID를 환경변수 또는 이름으로 탐색."""
    if prefer_id:
        return prefer_id
    if not name:
        name = PREPARED_FOLDER_NAME

    q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = svc.files().list(q=q, fields="files(id, name)", pageSize=50).execute()
    files = res.get("files", [])
    if not files:
        # 이름 대소문자 변형으로 재시도
        q2 = f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res2 = svc.files().list(q=q2, fields="files(id, name)", pageSize=1000).execute()
        for f in res2.get("files", []):
            if f.get("name", "").lower() == name.lower():
                return f.get("id")
        return None
    return files[0].get("id")


def _list_files_in_folder(svc, folder_id: str) -> List[Dict[str, Any]]:
    """
    prepared 폴더의 '직속 파일'을 모두 반환(페이지네이션 지원).
    하위 폴더 재귀는 이 함수에서 하지 않는다(요구 시 확장).
    """
    q = f"'{folder_id}' in parents and trashed=false and mimeType != 'application/vnd.google-apps.folder'"
    fields = "nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum)"
    out, token = [], None
    while True:
        res = svc.files().list(
            q=q, fields=fields, orderBy="modifiedTime desc", pageSize=1000, pageToken=token
        ).execute()
        out.extend(res.get("files", []))
        token = res.get("nextPageToken")
        if not token:
            break
    return out


def _download_file_bytes(svc, file_id: str, mime_type: Optional[str] = None) -> bytes:
    """
    Drive 파일 바이트 다운로드.
    - 일반 파일: files().get_media()
    - Google Docs류: files().export_media() (텍스트/PDF 등으로)
    """
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError

    # 파일 메타 조회
    meta = svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    m = meta.get("mimeType", "")
    is_gdoc = m.startswith("application/vnd.google-apps")

    try:
        if not is_gdoc:
            request = svc.files().get_media(fileId=file_id)
        else:
            # Google Docs/Sheets/Slides → 텍스트 우선, 안되면 PDF
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
            status, done = downloader.next_chunk()
        return fh.getvalue()
    except HttpError:
        return b""
# [03] END


# [04] 텍스트 추출기  # [04] START
def _extract_text_from_bytes(name: str, data: bytes) -> str:
    """텍스트/마크다운/CSV는 UTF-8로, PDF는 PyPDF2로 추출."""
    if not data:
        return ""
    if len(data) > MAX_BYTES:
        data = data[:MAX_BYTES]

    lower = (name or "").lower()
    if lower.endswith(".pdf"):
        # PDF → PyPDF2
        try:
            from PyPDF2 import PdfReader  # type: ignore
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for p in reader.pages:
                try:
                    pages.append(p.extract_text() or "")
                except Exception:
                    pages.append("")
            return "\n".join(pages).strip()
        except Exception:
            return ""  # 추출 실패는 공백으로

    # 텍스트/마크다운/CSV 등
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_texts_from_zip(data: bytes, zip_name: str) -> List[Dict[str, str]]:
    """
    ZIP 내부의 파일 중 ALLOWED_EXTS(단, .zip 제외)만 펼쳐서 텍스트 추출.
    """
    out: List[Dict[str, str]] = []
    if not data:
        return out
    if len(data) > MAX_BYTES:
        data = data[:MAX_BYTES]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                inner_name = info.filename
                if not any(inner_name.lower().endswith(ext) for ext in ALLOWED_EXTS if ext != ".zip"):
                    continue
                try:
                    b = zf.read(info)
                except Exception:
                    continue
                text = _extract_text_from_bytes(inner_name, b)
                if text.strip():
                    out.append({"name": inner_name, "text": text})
    except Exception:
        pass
    return out
# [04] END


# [05] 청크 분할  # [05] START
def _to_chunks(name: str, text: str, meta: Dict[str, Any],
               chunk_size: int = 900, chunk_overlap: int = 120) -> List[Dict[str, Any]]:
    """
    간단한 토큰 유사 길이 청크(문자 기준). 모델/임베딩 전처리용.
    """
    chunks: List[Dict[str, Any]] = []
    t = text.strip()
    if not t:
        return chunks
    start = 0
    n = len(t)
    while start < n:
        end = min(n, start + chunk_size)
        chunk_text = t[start:end]
        chunks.append({
            "file_name": name,
            "text": chunk_text,
            "meta": meta,
            "offset": start,
            "length": len(chunk_text),
        })
        if end >= n:
            break
        start = end - chunk_overlap
        if start < 0:
            start = 0
    return chunks
# [05] END


# [06] 인덱스 빌드(Drive prepared 폴더)  # [06] START
def _build_from_prepared(svc, prepared_folder_id: str) -> Tuple[int, int, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """
    prepared 폴더의 '직속 파일'을 인덱싱해 청크와 매니페스트 요약을 생성.
    - ZIP: 내부 텍스트류만 펼쳐서 처리
    - PDF: PyPDF2로 텍스트 추출
    - .md/.txt/.csv: UTF-8 decode
    """
    files = _list_files_in_folder(svc, prepared_folder_id)
    docs_summary: List[Dict[str, Any]] = []
    chunk_rows: List[Dict[str, Any]] = []

    for f in files:
        fid = f["id"]
        name = f.get("name", fid)
        mime = f.get("mimeType", "")
        lower = name.lower()

        # 인덱싱 대상 필터
        if not any(lower.endswith(ext) for ext in ALLOWED_EXTS):
            continue

        data = _download_file_bytes(svc, fid)

        # ZIP → 내부 텍스트만
        if lower.endswith(".zip") or mime == "application/zip":
            extracted = _extract_texts_from_zip(data, name)
            for item in extracted:
                meta = {
                    "file_id": f"{fid}:{item['name']}",
                    "file_name": item["name"],
                    "mimeType": "text/plain",
                    "page_approx": None,
                }
                chunk_rows.extend(_to_chunks(item["name"], item["text"], meta))
            docs_summary.append({
                "id": fid,
                "name": name,
                "mimeType": mime,
                "size": f.get("size"),
                "md5": f.get("md5Checksum"),
                "expanded_from_zip": len(extracted),
            })
            continue

        # 단일 파일 텍스트 추출
        text = _extract_text_from_bytes(name, data)
        if text.strip():
            meta = {
                "file_id": fid,
                "file_name": name,
                "mimeType": mime,
                "page_approx": None,
            }
            chunk_rows.extend(_to_chunks(name, text, meta))

        # 매니페스트 요약(텍스트가 비어도 기록)
        docs_summary.append({
            "id": fid,
            "name": name,
            "mimeType": mime,
            "size": f.get("size"),
            "md5": f.get("md5Checksum"),
        })

    manifest = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "docs": docs_summary,
    }
    extra = {
        "processed_files": len(docs_summary),
        "generated_chunks": len(chunk_rows),
    }
    return len(docs_summary), len(chunk_rows), manifest, extra, chunk_rows
# [06] END


# [07] 디스크 저장  # [07] START
def _write_manifest(manifest: Dict[str, Any]):
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"manifest 저장: {MANIFEST_PATH}")

def _write_chunks_jsonl(chunks: List[Dict[str, Any]]):
    out_path = PERSIST_DIR / "chunks.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in chunks:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    _log(f"chunks 저장: {out_path} (rows={len(chunks)})")
# [07] END


# [08] 변경 감지(diff) — 인덱싱 대상만 비교, 최초 실행은 '전부 추가'  # [08] START
def _ingestible(name: str) -> bool:
    n = (name or "").lower()
    return any(n.endswith(ext) for ext in ALLOWED_EXTS)

def diff_with_manifest(folder_id: str | None = None, limit: int = 5000) -> dict:
    """
    prepared 폴더 목록과 로컬 manifest.json을 비교하여
    added/changed/removed 통계를 반환한다.
    - 인덱싱 대상 확장자만 비교(.md/.txt/.pdf/.csv/.zip)
    - 최초 실행(no_manifest) 시 현재 대상 파일을 모두 'added'로 간주
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

        # 현재 목록(인덱싱 대상만)
        cur_all = _list_files_in_folder(svc, fid)
        cur = [f for f in cur_all if _ingestible(f.get("name", ""))][:limit]
        cdocs = {f.get("id"): f for f in cur if f.get("id")}

        # manifest가 없으면: 현재 대상 파일을 전부 added로 보고 종료
        if not MANIFEST_PATH.exists():
            out["ok"] = True
            out["reason"] = "no_manifest"
            out["added"] = [f.get("name") for f in cur]
            out["stats"] = {"added": len(out["added"]), "changed": 0, "removed": 0}
            return out

        man = json.loads(MANIFEST_PATH.read_text(encoding="utf-8") or "{}")
        mdocs_src = {d.get("id"): d for d in (man.get("docs") or []) if d.get("id")}
        # manifest 쪽도 인덱싱 대상만 비교
        mdocs = {i: d for i, d in mdocs_src.items() if _ingestible(d.get("name", ""))}

        ids_m = set(mdocs.keys())
        ids_c = set(cdocs.keys())
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
        out["added"] = _names(added_ids)
        out["changed"] = _names(changed_ids)
        out["removed"] = _names(removed_ids)
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


# [09] 전체 파이프라인 실행(빌드)  # [09] START
def run_index_pipeline(folder_id: str | None = None) -> Dict[str, Any]:
    """
    prepared 폴더에서 문서를 인덱싱해 manifest/chunks를 저장.
    반환: {"files": n_files, "chunks": n_chunks, "manifest_path": ..., "chunks_path": ...}
    """
    svc = _drive_client()
    fid = folder_id or _find_folder_id(svc, prefer_id=PREPARED_FOLDER_ID, name=PREPARED_FOLDER_NAME)
    if not fid:
        raise RuntimeError("prepared 폴더 ID를 찾을 수 없습니다.")

    n_files, n_chunks, manifest, extra, chunks = _build_from_prepared(svc, fid)

    _write_manifest(manifest)
    _write_chunks_jsonl(chunks)

    result = {
        "files": n_files,
        "chunks": n_chunks,
        "manifest_path": str(MANIFEST_PATH),
        "chunks_path": str(PERSIST_DIR / "chunks.jsonl"),
        "extra": extra,
    }
    _log(f"인덱싱 완료: files={n_files}, chunks={n_chunks}")
    return result
# [09] END


# [10] CLI 진입점  # [10] START
def main():
    import argparse
    p = argparse.ArgumentParser(description="MAIC Index Builder (Drive prepared 폴더)")
    p.add_argument("--build", action="store_true", help="변경 여부와 무관하게 인덱싱 수행")
    p.add_argument("--diff", action="store_true", help="변경 감지만 수행(added/changed/removed 출력)")
    p.add_argument("--folder-id", type=str, default=None, help="prepared 폴더 ID를 직접 지정")
    args = p.parse_args()

    if args.diff and not args.build:
        d = diff_with_manifest(folder_id=args.folder_id)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    if args.build:
        res = run_index_pipeline(folder_id=args.folder_id)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    # 기본 동작: diff 후, 변경 있으면 build / 없으면 종료
    d = diff_with_manifest(folder_id=args.folder_id)
    if not d.get("ok"):
        _log(f"변경 감지 실패: {d.get('reason')}")
        return

    st = d.get("stats", {})
    if st.get("added", 0) or st.get("changed", 0):
        _log(f"변경 감지됨: added={st.get('added')} changed={st.get('changed')} → 인덱싱 수행")
        run_index_pipeline(folder_id=args.folder_id)
    else:
        _log("변경 없음: 인덱싱 생략")


if __name__ == "__main__":
    main()
# [10] END
