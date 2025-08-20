# ===== [01] APP BOOT =========================================================
from __future__ import annotations

import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태를 세션에 보관 (없으면 None)
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None

def _index_status_badge() -> None:
    """창고 상태 표시: 준비/없음."""
    if st.session_state["rag_index"] is None:
        st.caption("Index status: ❌ missing (빌드 또는 복구 필요)")
    else:
        st.caption("Index status: ✅ ready")

st.title("🧑‍🏫 AI Teacher — Clean Scaffold")
_index_status_badge()

# 버튼을 눌렀을 때만 로드/빌드 시도 (없으면 크래시 대신 안내)
if st.button("Build/Load Index"):
    with st.spinner("Loading / building local index…"):
        if get_or_build_index is None:
            st.warning("RAG 엔진이 아직 준비되지 않았어요.")
        else:
            try:
                idx = get_or_build_index()              # ← 여기서 없으면 예외 발생
                st.session_state["rag_index"] = idx     # 준비 완료 상태로 저장
                st.success("Index ready.")
            except LocalIndexMissing:
                # 창고가 비어 있으면 여기로 떨어짐 — 크래시 대신 안내만.
                st.info("아직 로컬 인덱스가 없습니다. 백업 복구 또는 인덱스 빌드를 먼저 실행해 주세요.")
            except Exception as e:
                st.error(f"Index load/build failed: {type(e).__name__}: {e}")
# ===== [02] RAG: Restore from Drive BACKUP_ZIP ===============================
# 백업 ZIP을 구글드라이브에서 내려받아 로컬(APP_DATA_DIR)에 풀고,
# 바로 인덱스를 재로딩합니다. (키 이름이 달라도 시크릿에서 자동 탐색)

import json, io, os, zipfile
from pathlib import Path

# --- (A) 시크릿에서 "서비스계정 JSON" 자동 탐색 -----------------------------
def _find_service_account_in_secrets() -> dict:
    """
    1) 흔한 키 후보들을 우선 확인
    2) 그래도 없으면 st.secrets 전체를 훑어서 service_account 형태를 자동 탐색
    """
    candidates = (
        "GDRIVE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "SERVICE_ACCOUNT_JSON",
        # 소문자/다른 팀이 쓰던 별칭도 지원
        "gdrive_service_account_json",
        "service_account_json",
        "GCP_SERVICE_ACCOUNT",
        "gcp_service_account",
    )
    # 1) 후보 키 직행
    for k in candidates:
        if k in st.secrets and str(st.secrets[k]).strip():
            raw = st.secrets[k]
            return json.loads(raw) if isinstance(raw, str) else dict(raw)

    # 2) 최상위 모든 키를 스캔 (중첩 테이블/문자열 모두 탐색)
    for k, v in st.secrets.items():
        try:
            if isinstance(v, (dict,)):
                if v.get("type") == "service_account" and "client_email" in v and "private_key" in v:
                    return dict(v)
            elif isinstance(v, str):
                if '"type": "service_account"' in v and '"client_email"' in v and '"private_key"' in v:
                    return json.loads(v)
        except Exception:
            pass

    raise KeyError(
        "서비스계정 JSON을 시크릿에서 찾지 못했습니다. "
        "권장: 최상위에 GDRIVE_SERVICE_ACCOUNT_JSON = '''{...}''' 로 추가하세요."
    )

# --- (B) 시크릿에서 "백업 폴더 ID" 자동 탐색 --------------------------------
def _find_backup_folder_id() -> str:
    candidates = (
        "GDRIVE_BACKUP_FOLDER_ID",
        "BACKUP_FOLDER_ID",
        "GDRIVE_FOLDER_ID",   # 일반 폴더 키도 허용
    )
    for k in candidates:
        if k in st.secrets and str(st.secrets[k]).strip():
            return str(st.secrets[k]).strip()

    # 혹시 섹션/중첩 안쪽에 들어 있다면 전체 스캔
    for _, v in st.secrets.items():
        try:
            if isinstance(v, (dict,)):
                for kk, vv in v.items():
                    if "FOLDER_ID" in str(kk).upper() and str(vv).strip():
                        return str(vv).strip()
        except Exception:
            pass

    raise KeyError(
        "백업 폴더 ID를 찾지 못했습니다. "
        "권장: GDRIVE_BACKUP_FOLDER_ID = '폴더_ID' (또는 GDRIVE_FOLDER_ID) 를 최상위에 추가하세요."
    )

# --- (C) 복구 로직 -----------------------------------------------------------
def _restore_from_drive_backup():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except Exception as e:
        raise RuntimeError("google-api-python-client / google-auth 패키지가 필요합니다.") from e

    sa_info = _find_service_account_in_secrets()
    creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/drive.readonly"])

    folder_id = _find_backup_folder_id()

    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = f"'{folder_id}' in parents and trashed=false and mimeType='application/zip'"
    resp = svc.files().list(
        q=q, orderBy="modifiedTime desc",
        fields="files(id,name,modifiedTime,size),nextPageToken", pageSize=1
    ).execute()
    files = resp.get("files", [])
    if not files:
        raise FileNotFoundError("백업 폴더에 .zip 파일이 없습니다.")
    f = files[0]

    req = svc.files().get_media(fileId=f["id"])
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)

    # APP_DATA_DIR 결정
    try:
        from src.config import APP_DATA_DIR
    except Exception:
        APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR") or (Path.home() / ".maic"))
    target = APP_DATA_DIR
    target.mkdir(parents=True, exist_ok=True)

    # ZIP 풀기
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(target)

    count = sum(1 for p in target.rglob("*") if p.is_file())
    return {
        "ok": True,
        "backup_name": f.get("name"),
        "modifiedTime": f.get("modifiedTime"),
        "target": str(target),
        "files": count,
    }

st.subheader("RAG: Restore from Drive BACKUP_ZIP")
if st.button("⬇️ Restore backup zip from Drive"):
    with st.spinner("Restoring from Drive backup…"):
        try:
            res = _restore_from_drive_backup()
            st.success(f"Restored '{res['backup_name']}' → {res['target']}")
            st.caption(f"Modified: {res['modifiedTime']} | Total local files: {res['files']}")
            # 복구 직후 인덱스 재시도
            try:
                idx = get_or_build_index() if get_or_build_index else None
                if idx is not None:
                    st.session_state["rag_index"] = idx
                    st.success("Index loaded from restored backup.")
            except Exception as e:
                st.warning(f"Index reload skipped: {type(e).__name__}: {e}")
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")

# ===== [03] END ==============================================================
