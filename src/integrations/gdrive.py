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

from typing import Any, Dict, List
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
