# ============================ [01] GOOGLE DRIVE PREPARED — START ============================
"""
Google Drive 'prepared' 폴더 파일 목록 드라이버 (동적 임포트로 정적 검사 에러 제거)

공개 함수:
    list_prepared_files() -> list[dict]
        반환 예: [{"id": "...", "name": "doc.pdf", "modified_ts": 1725000000, "size": 12345}, ...]

설정(환경변수/Secrets):
    - GDRIVE_PREPARED_FOLDER_ID   (필수) : 대상 폴더 ID
    - GDRIVE_SA_JSON              (선택) : 서비스계정 JSON 문자열 또는 파일 경로
    - (대안 secrets) st.secrets["gcp_service_account"] / ["GOOGLE_SERVICE_ACCOUNT_JSON"]

권한:
    - scope: https://www.googleapis.com/auth/drive.readonly

메모:
    - google-* 라이브러리가 설치되지 않은 환경에서도 정적 검사(mypy/ruff)가 깨지지 않도록
      모든 외부 모듈은 importlib.import_module 로 '런타임에만' 로드합니다.
"""

from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path
import importlib
import os
import json
import time


def _get_folder_id() -> str:
    """환경변수/Secrets에서 prepared 폴더 ID를 찾는다."""
    fid = os.getenv("GDRIVE_PREPARED_FOLDER_ID", "").strip()
    if fid:
        return fid
    try:
        st = importlib.import_module("streamlit")  # type: ignore[import-not-found]
        for k in ("GDRIVE_PREPARED_FOLDER_ID", "PREPARED_FOLDER_ID"):
            if getattr(st, "secrets", None) and k in st.secrets:
                v = str(st.secrets[k]).strip()
                if v:
                    return v
    except Exception:
        pass
    return ""


def _get_service_account_json() -> Dict[str, Any] | None:
    """서비스 계정 JSON 반환 (문자열/파일경로/secrets 모두 지원)."""
    v = os.getenv("GDRIVE_SA_JSON", "").strip()
    if v:
        try:
            if v.lstrip().startswith("{"):
                return json.loads(v)
            p = Path(v).expanduser()
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        st = importlib.import_module("streamlit")  # type: ignore[import-not-found]
        for k in ("gcp_service_account", "GOOGLE_SERVICE_ACCOUNT_JSON", "GDRIVE_SA_JSON"):
            if getattr(st, "secrets", None) and k in st.secrets:
                obj = st.secrets[k]
                if isinstance(obj, dict):
                    return dict(obj)
                try:
                    return json.loads(str(obj))
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _build_credentials():
    """google-auth 서비스계정 Credentials 객체 생성(동적 임포트)."""
    try:
        svc_mod = importlib.import_module("google.oauth2.service_account")  # type: ignore[import-not-found]
    except Exception as e:
        raise RuntimeError("google-auth not available") from e

    sa = _get_service_account_json()
    if not sa:
        raise RuntimeError("service account json missing")

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    Credentials = getattr(svc_mod, "Credentials", None)
    if Credentials is None:
        raise RuntimeError("Credentials class not found in google.oauth2.service_account")
    return Credentials.from_service_account_info(sa, scopes=scopes)


def _rfc3339_to_epoch(s: str) -> int:
    """RFC3339(Drive modifiedTime) → epoch seconds."""
    try:
        from datetime import datetime
        ss = s.replace("Z", "+00:00")
        return int(datetime.fromisoformat(ss).timestamp())
    except Exception:
        try:
            import datetime as dt
            return int(time.mktime(dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").timetuple()))
        except Exception:
            return 0


def _list_via_google_api(creds, folder_id: str) -> List[Dict[str, Any]]:
    """google-api-python-client 경로 (존재 시 우선 사용)."""
    try:
        disc = importlib.import_module("googleapiclient.discovery")  # type: ignore[import-not-found]
    except Exception as e:
        raise RuntimeError("google-api-python-client not available") from e

    build = getattr(disc, "build")
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id,name,modifiedTime,size,mimeType),nextPageToken"
    page_token = None
    out: List[Dict[str, Any]] = []
    while True:
        resp = (
            service.files()
            .list(q=q, fields=fields, pageSize=1000, pageToken=page_token)
            .execute()
        )
        for f in resp.get("files", []):
            out.append(
                {
                    "id": f.get("id") or "",
                    "name": f.get("name") or "",
                    "modified_ts": _rfc3339_to_epoch(str(f.get("modifiedTime") or "")),
                    "size": int(f.get("size") or 0),
                    "mime": f.get("mimeType") or "",
                }
            )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _list_via_rest(creds, folder_id: str) -> List[Dict[str, Any]]:
    """google-auth + REST(AuthorizedSession) 경로 — 의존성 최소."""
    try:
        req_mod = importlib.import_module("google.auth.transport.requests")  # type: ignore[import-not-found]
    except Exception as e:
        raise RuntimeError("google-auth transport not available") from e

    AuthorizedSession = getattr(req_mod, "AuthorizedSession", None)
    if AuthorizedSession is None:
        raise RuntimeError("AuthorizedSession not found")

    sess = AuthorizedSession(creds)
    base = "https://www.googleapis.com/drive/v3/files"
    q = f"'{folder_id}' in parents and trashed=false"
    params = {
        "q": q,
        "fields": "files(id,name,modifiedTime,size,mimeType),nextPageToken",
        "pageSize": "1000",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    out: List[Dict[str, Any]] = []
    page_token = None
    while True:
        if page_token:
            params["pageToken"] = page_token
        r = sess.get(base, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        for f in data.get("files", []):
            out.append(
                {
                    "id": f.get("id") or "",
                    "name": f.get("name") or "",
                    "modified_ts": _rfc3339_to_epoch(str(f.get("modifiedTime") or "")),
                    "size": int(f.get("size") or 0),
                    "mime": f.get("mimeType") or "",
                }
            )
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return out


def list_prepared_files() -> List[Dict[str, Any]]:
    """
    준비(prepared) 폴더의 파일 목록을 반환.
    - google-api-python-client가 있으면 우선 사용
    - 없으면 google-auth의 AuthorizedSession으로 REST 호출
    - 설정/의존성 부족 시 RuntimeError를 던져 상위(로컬 폴백 등)에서 처리
    """
    folder_id = _get_folder_id()
    if not folder_id:
        raise RuntimeError("GDRIVE_PREPARED_FOLDER_ID missing")

    creds = _build_credentials()

    # 1) google-api-python-client가 있으면 우선 사용
    try:
        return _list_via_google_api(creds, folder_id)
    except Exception:
        # 2) 없으면 REST 경로로 시도
        return _list_via_rest(creds, folder_id)
# ============================= [01] GOOGLE DRIVE PREPARED — END =============================
