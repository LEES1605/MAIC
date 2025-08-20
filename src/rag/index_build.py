# ===== [01] IMPORTS & HELPERS ===============================================
from __future__ import annotations

from typing import Callable, Dict, Mapping, Any, List, Optional
import json
import streamlit as st


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        # 진행률/메시지 콜백이 없는 경우를 대비한 안전 가드
        return None


# ===== [02] DRIVE CREDS / SERVICE / LIST ====================================
def _coerce_credentials(gcp_creds: Mapping[str, object] | None):
    """
    우선순위:
      1) 인자 gcp_creds (Mapping 또는 JSON 문자열)
      2) st.secrets['GDRIVE_SERVICE_ACCOUNT_JSON' | 'GOOGLE_SERVICE_ACCOUNT_JSON' | 'SERVICE_ACCOUNT_JSON']
    """
    try:
        from google.oauth2.service_account import Credentials  # lazy import
    except Exception as e:
        raise RuntimeError("google-auth 패키지가 필요합니다.") from e

    info: Optional[dict] = None
    if gcp_creds:
        info = dict(gcp_creds) if isinstance(gcp_creds, Mapping) else None
        if info is None and isinstance(gcp_creds, str):
            info = json.loads(gcp_creds)

    if info is None:
        raw = None
        for key in ("GDRIVE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_JSON", "SERVICE_ACCOUNT_JSON"):
            if key in st.secrets and str(st.secrets[key]).strip():
                raw = st.secrets[key]
                break
        if raw is None:
            raise KeyError("서비스계정 JSON이 없습니다. st.secrets['GDRIVE_SERVICE_ACCOUNT_JSON']를 확인하세요.")
        info = json.loads(raw) if isinstance(raw, str) else dict(raw)

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    return Credentials.from_service_account_info(info, scopes=scopes)


def _resolve_folder_id(gdrive_folder_id: str | None) -> str:
    if gdrive_folder_id and str(gdrive_folder_id).strip():
        return str(gdrive_folder_id).strip()
    for key in ("GDRIVE_FOLDER_ID", "DRIVE_FOLDER_ID"):
        if key in st.secrets and str(st.secrets[key]).strip():
            return str(st.secrets[key]).strip()
    raise KeyError("대상 폴더 ID가 없습니다. st.secrets['GDRIVE_FOLDER_ID']를 확인하세요.")


def _drive_service(creds):
    try:
        from googleapiclient.discovery import build  # lazy import
    except Exception as e:
        raise RuntimeError("google-api-python-client 패키지가 필요합니다.") from e
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list_files(service, folder_id: str) -> List[Dict[str, Any]]:
    """폴더 내 파일 목록(필수 메타만)"""
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id,name,mimeType,modifiedTime), nextPageToken"
    files, token = [], None
    while True:
        resp = service.files().list(q=q, fields=fields, pageToken=token, pageSize=1000).execute()
        files.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    files.sort(key=lambda x: x.get("name", ""))
    return files


# ===== [03] PUBLIC ENTRY =====================================================
def build_index_with_checkpoint(
    update_pct: Callable[[int, str | None], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,
    gcp_creds: Mapping[str, object],
    persist_dir: str,
    remote_manifest: Dict[str, Dict[str, object]],
    should_stop: Callable[[], bool] | None = None,
) -> Dict[str, Any]:
    """
    B-프로브 단계: 실제 인덱스/파일 저장은 아직 하지 않음.
    - Drive 연결 → 폴더 파일 "목록"만 가져와서 샘플 10개 반환
    - 호출측 UI는 진행률/상태만 표시
    """
    _safe_call(update_msg, "🔌 Connecting to Google Drive…")
    creds = _coerce_credentials(gcp_creds)
    folder_id = _resolve_folder_id(gdrive_folder_id)
    service = _drive_service(creds)
    _safe_call(update_pct, 10, "connected")

    if should_stop and should_stop():
        return {"ok": False, "stopped": True, "note": "stopped before listing"}

    _safe_call(update_msg, "📄 Listing files in the folder…")
    files = _list_files(service, folder_id)
    sample = [{k: f.get(k) for k in ("id", "name", "mimeType", "modifiedTime")} for f in files[:10]]
    _safe_call(update_pct, 100, f"found {len(files)} files")

    return {
        "ok": True,
        "files_total": len(files),
        "sample": sample,
        "note": "Probe-only. No index writes yet.",
    }

# ===== [04] END ==============================================================
