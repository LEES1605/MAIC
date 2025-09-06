# ============================ [01] GOOGLE DRIVE PREPARED — START ============================
"""
Google Drive 'prepared' 폴더 파일 목록 드라이버 (동적 임포트로 정적 검사 에러 제거)

공개 함수:
    list_prepared_files() -> list[dict]
        예: [{"id": "...", "name": "doc.pdf", "modified_ts": 1725000000, "size": 12345}, ...]

설정(환경변수/Secrets):
    - GDRIVE_PREPARED_FOLDER_ID   (필수) : 대상 폴더 ID
    - GDRIVE_SA_JSON              (선택) : 서비스계정 JSON 문자열 또는 파일 경로
    - (대안 secrets) st.secrets["gcp_service_account"] / ["GOOGLE_SERVICE_ACCOUNT_JSON"]

권한: scope = https://www.googleapis.com/auth/drive.readonly
메모: google-* 모듈은 모두 importlib 로 동적 로딩하여 정적 검사 에러를 방지.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import importlib
import os
import json
import time


def _get_folder_id() -> str:
    fid = os.getenv("GDRIVE_PREPARED_FOLDER_ID", "").strip()
    if fid:
        return fid

    # streamlit secrets 사용 가능 시 대체
    try:
        st = importlib.import_module("streamlit")
        secrets_obj = getattr(st, "secrets", {})
        fid = (secrets_obj.get("GDRIVE_PREPARED_FOLDER_ID") or "").strip()
        if fid:
            return fid
    except Exception:
        pass

    raise RuntimeError("GDRIVE_PREPARED_FOLDER_ID not found")


def _load_service_account_json() -> Dict[str, Any] | None:
    """
    우선순위:
      1) 환경변수 GDRIVE_SA_JSON (JSON 문자열 또는 파일 경로)
      2) st.secrets["gcp_service_account"] 또는 ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    """
    # 1) 환경변수
    sa = (os.getenv("GDRIVE_SA_JSON") or "").strip()
    if sa:
        # 파일 경로일 수 있음
        p = Path(sa)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        # 아니면 JSON 문자열
        try:
            return json.loads(sa)
        except Exception:
            pass

    # 2) streamlit secrets
    try:
        st = importlib.import_module("streamlit")
        secrets_obj = getattr(st, "secrets", {})
        sa_obj = (
            secrets_obj.get("gcp_service_account")
            or secrets_obj.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        )
        if isinstance(sa_obj, dict):
            return dict(sa_obj)
        if isinstance(sa_obj, str):
            return json.loads(sa_obj)
    except Exception:
        pass

    return None


def _build_credentials():
    """
    서비스 계정 JSON이 있으면 해당 계정으로, 없으면 ADC(앱 기본 자격증명)로 시도.
    """
    scope = ["https://www.googleapis.com/auth/drive.readonly"]

    # google.oauth2.service_account
    try:
        svc_mod = importlib.import_module("google.oauth2.service_account")
        sa_json = _load_service_account_json()
        if sa_json:
            creds = getattr(svc_mod, "Credentials").from_service_account_info(
                sa_json,
                scopes=scope,
            )
            return creds
    except Exception:
        pass

    # ADC
    try:
        auth = importlib.import_module("google.auth")
        default_fn = getattr(auth, "default")
        creds, _ = default_fn(scopes=scope)
        return creds
    except Exception:
        pass

    raise RuntimeError("No credentials found (service account or ADC)")


def _list_via_google_api(creds, folder_id: str) -> List[Dict[str, Any]]:
    """
    googleapiclient.discovery 사용
    """
    try:
        disc = importlib.import_module("googleapiclient.discovery")
    except Exception as e:
        raise RuntimeError(
            f"googleapiclient.discovery import failed: {e}"
        ) from None

    service = disc.build(
        "drive",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )

    q = (
        f"'{folder_id}' in parents and "
        "mimeType != 'application/vnd.google-apps.folder' and "
        "trashed = false"
    )
    res = service.files().list(
        q=q,
        fields="files(id,name,modifiedTime,size,mimeType),nextPageToken",
        spaces="drive",
        pageSize=1000,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        corpora="allDrives",
    ).execute()

    files = []
    for f in res.get("files", []):
        modified_ts = _parse_modified_time(f.get("modifiedTime"))
        size = int(f.get("size") or 0)
        files.append(
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "modified_ts": modified_ts,
                "size": size,
                "mime": f.get("mimeType"),
            }
        )
    return files


def _parse_modified_time(s: str | None) -> int:
    """
    RFC3339 문자열에서 epoch 초로 변환
    """
    if not s:
        return 0
    try:
        # "2024-08-31T10:22:33.000Z" 형태
        # 표준 라이브러리로 단순 파싱 (정밀도는 초 단위)
        from datetime import datetime, timezone

        # 끝이 'Z'인 UTC
        if s.endswith("Z"):
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        # 실패 시 대략 현재 시각 반환(정렬 목적)
        return int(time.time())


def _list_via_rest(creds, folder_id: str) -> List[Dict[str, Any]]:
    """
    googleapiclient 가 불가할 때 requests + google.auth.transport.requests 로 대체
    """
    try:
        req_mod = importlib.import_module("google.auth.transport.requests")
        session_cls = getattr(req_mod, "AuthorizedSession", None)
        if session_cls is None:
            raise RuntimeError("AuthorizedSession not found")
        sess = session_cls(creds)
    except Exception:
        # AuthorizedSession 이 없거나 실패 시, 토큰을 직접 주입하는 간이 대체
        import requests

        # creds.refresh(Request()) 으로 토큰 취득을 시도
        try:
            req_mod2 = importlib.import_module("google.auth.transport.requests")
            Request = getattr(req_mod2, "Request")
            creds.refresh(Request())
        except Exception:
            pass

        token = getattr(creds, "token", None)
        if not token:
            raise RuntimeError("No OAuth token available") from None

        sess = requests.Session()
        sess.headers.update({"Authorization": f"Bearer {token}"})

    url = "https://www.googleapis.com/drive/v3/files"
    q = (
        f"'{folder_id}' in parents and "
        "mimeType != 'application/vnd.google-apps.folder' and "
        "trashed = false"
    )
    params = {
        "q": q,
        "fields": "files(id,name,modifiedTime,size,mimeType),nextPageToken",
        "spaces": "drive",
        "pageSize": "1000",
        "includeItemsFromAllDrives": "true",
        "supportsAllDrives": "true",
        "corpora": "allDrives",
    }

    r = sess.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    files = []
    for f in data.get("files", []):
        modified_ts = _parse_modified_time(f.get("modifiedTime"))
        size = int(f.get("size") or 0)
        files.append(
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "modified_ts": modified_ts,
                "size": size,
                "mime": f.get("mimeType"),
            }
        )
    return files


def list_prepared_files() -> List[Dict[str, Any]]:
    """
    prepared 폴더의 (폴더 제외) 파일 목록을 반환
    - googleapiclient가 있으면 우선 사용
    - 없으면 REST 대체 경로
    """
    folder_id = _get_folder_id()
    if not folder_id:
        raise RuntimeError("GDRIVE_PREPARED_FOLDER_ID missing")

    creds = _build_credentials()

    try:
        return _list_via_google_api(creds, folder_id)
    except Exception:
        return _list_via_rest(creds, folder_id)
# ============================= [01] GOOGLE DRIVE PREPARED — END =============================

# ============================ [02] DOWNLOAD API — START ============================
def _drive_service():
    """googleapiclient discovery client 생성"""
    creds = _build_credentials()
    disc = importlib.import_module("googleapiclient.discovery")
    return disc.build("drive", "v3", credentials=creds, cache_discovery=False)

def _export_mime(mime: str) -> Optional[str]:
    """Google Docs류는 export로 평문을 받는다."""
    maps = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }
    for k, v in maps.items():
        if mime.startswith(k):
            return v
    return None

def download_bytes(file_id: str, *, mime_hint: Optional[str] = None) -> Tuple[bytes, str]:
    """
    파일 바이트와 최종 MIME을 반환.
    - Google Docs류는 export로 평문/CSV
    - 일반 파일은 media download
    """
    svc = _drive_service()
    files = svc.files()
    meta = files.get(fileId=file_id, fields="id,name,mimeType").execute()
    mime = (meta.get("mimeType") or "").strip()
    exp = _export_mime(mime)
    if exp:
        req = files.export_media(fileId=file_id, mimeType=exp)
        data = req.execute()
        return data or b"", exp

    # 일반 바이너리 다운로드
    req = files.get_media(fileId=file_id)
    # MediaIoBaseDownload 동적 import (정적 검사 무시)
    io_mod = importlib.import_module("io")
    buf = io_mod.BytesIO()
    http = importlib.import_module("googleapiclient.http")
    downloader = http.MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue(), (mime or (mime_hint or "application/octet-stream"))
# ============================= [02] DOWNLOAD API — END =============================
# ======================= [03] PREPARED API ADAPTER — START ========================
"""
준수 인터페이스:
- check_prepared_updates(persist_dir) -> dict
- mark_prepared_consumed(persist_dir, files: list[dict] | list[str]) -> None

설명:
- Google Drive의 prepared 폴더를 단일 소스로 가정.
- '신규 파일 감지'는 persist_dir 아래의 prepared.seen.json 에 저장/조회.
- gdrive 통합의 list_prepared_files()가 존재하면 이용하고, 없으면 안전 폴백(빈 목록).
"""

from __future__ import annotations


def _seen_store_path(persist_dir) -> "Path":
    from pathlib import Path

    return Path(persist_dir).expanduser() / "prepared.seen.json"


def _load_seen(persist_dir) -> "set[str]":
    import json
    from pathlib import Path

    p = _seen_store_path(persist_dir)
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
    except Exception:
        pass
    return set()


def _save_seen(persist_dir, seen: "set[str]") -> None:
    import json

    p = _seen_store_path(persist_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # 저장 실패는 기능 치명상이 아님(다음 번에 다시 감지될 뿐)
        pass


def _extract_id(rec) -> str:
    """
    files 항목에서 식별자 우선순위:
    - id → fileId → name → path → ''(미상)
    dict/str 혼용 입력을 모두 수용.
    """
    if isinstance(rec, str):
        return rec.strip()
    if isinstance(rec, dict):
        for k in ("id", "fileId", "name", "path"):
            v = rec.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _list_prepared_files_safe() -> "list[dict]":
    """
    src.integrations.gdrive.list_prepared_files() 가 있으면 호출,
    없으면 빈 목록 반환(폴백).
    """
    try:
        import importlib

        mod = importlib.import_module("src.integrations.gdrive")
        lf = getattr(mod, "list_prepared_files", None)
        if callable(lf):
            out = lf() or []
            return out if isinstance(out, list) else []
    except Exception:
        pass
    return []


def check_prepared_updates(persist_dir) -> "dict[str, object]":
    """
    반환 스키마(최소):
    {
      "driver": "drive",
      "total": <전체 파일 수>,
      "new":   <신규 파일 수>,
      "files": [<신규 식별자(str)>...]
    }
    """
    files: list[dict] = _list_prepared_files_safe()
    seen: set[str] = _load_seen(persist_dir)

    new_ids: list[str] = []
    for rec in files:
        fid = _extract_id(rec)
        if fid and fid not in seen:
            new_ids.append(fid)

    return {
        "driver": "drive",
        "total": len(files),
        "new": len(new_ids),
        "files": new_ids,
    }


def mark_prepared_consumed(persist_dir, files) -> None:
    """
    files: list[dict] | list[str]
    - dict/str 혼용을 모두 허용하며, _extract_id()로 식별자를 추출하여 seen에 추가
    """
    seen: set[str] = _load_seen(persist_dir)

    # list[str] / list[dict] 모두 수용
    if isinstance(files, list):
        for rec in files:
            fid = _extract_id(rec)
            if fid:
                seen.add(fid)

    _save_seen(persist_dir, seen)
# ======================== [03] PREPARED API ADAPTER — END =========================

