# ========================== prompting/drive_source.py — START ====================
from __future__ import annotations

import io
import json
from typing import Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def _drive_client(creds_json: Optional[str] = None):
    """
    서비스 계정 JSON 문자열 또는 ADC로 Drive v3 클라이언트 생성.
    """
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    if creds_json:
        from google.oauth2.service_account import Credentials

        info = json.loads(creds_json)
        cred = Credentials.from_service_account_info(info, scopes=scopes)
    else:
        import google.auth

        cred, _ = google.auth.default(scopes=scopes)
    return build("drive", "v3", credentials=cred, cache_discovery=False)


def _find_file_id(svc, folder_id: str, file_name: str) -> Optional[str]:
    q = (
        f"'{folder_id}' in parents and trashed=false and name='{file_name}' and "
        "mimeType!='application/vnd.google-apps.folder'"
    )
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=10).execute()
    arr = res.get("files", [])
    return arr[0]["id"] if arr else None


def _download_bytes(svc, file_id: str) -> bytes:
    req = svc.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = dl.next_chunk()
    buf.seek(0)
    return buf.read()


def fetch_prompts_from_drive(
    *,
    folder_id: Optional[str],
    file_name: str = "prompts.yaml",
    creds_json: Optional[str] = None,
) -> Optional[Dict]:
    """
    Drive 폴더에서 prompts.yaml 다운로드하여 dict로 반환. 실패 시 None.
    """
    if not folder_id:
        return None
    try:
        svc = _drive_client(creds_json)
        fid = _find_file_id(svc, folder_id, file_name)
        if not fid:
            return None
        blob = _download_bytes(svc, fid)
        try:
            import yaml  # lazy

            return yaml.safe_load(blob) or {}
        except Exception:
            return json.loads(blob.decode("utf-8"))
    except Exception:
        return None
# =========================== prompting/drive_source.py — END =====================
