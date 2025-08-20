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
# 바로 인덱스를 재로딩합니다. (실패해도 앱은 죽지 않음)
import json, io, os, zipfile
from pathlib import Path

def _restore_from_drive_backup():
    # 1) 서비스계정 로드 (secrets의 원문 JSON을 그대로 읽음)
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except Exception as e:
        raise RuntimeError("google-api-python-client / google-auth 패키지가 필요합니다.") from e

    raw = None
    for k in ("GDRIVE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_JSON", "SERVICE_ACCOUNT_JSON"):
        if k in st.secrets and str(st.secrets[k]).strip():
            raw = st.secrets[k]; break
    if raw is None:
        raise KeyError("st.secrets['GDRIVE_SERVICE_ACCOUNT_JSON']가 없습니다.")
    info = json.loads(raw) if isinstance(raw, str) else dict(raw)
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])

    # 2) 백업 폴더 ID (우선순위: GDRIVE_BACKUP_FOLDER_ID > BACKUP_FOLDER_ID > GDRIVE_FOLDER_ID)
    folder_id = None
    for k in ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID", "GDRIVE_FOLDER_ID"):
        if k in st.secrets and str(st.secrets[k]).strip():
            folder_id = str(st.secrets[k]).strip(); break
    if not folder_id:
        raise KeyError("백업 폴더 ID가 없습니다. GDRIVE_BACKUP_FOLDER_ID(권장) 또는 GDRIVE_FOLDER_ID를 설정하세요.")

    # 3) 최신 ZIP 1개 찾기 → 다운로드
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = f"'{folder_id}' in parents and trashed=false and mimeType='application/zip'"
    resp = svc.files().list(q=q, orderBy="modifiedTime desc",
                            fields="files(id,name,modifiedTime,size),nextPageToken", pageSize=1).execute()
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

    # 4) 압축 해제 대상 경로(APP_DATA_DIR)
    try:
        from src.config import APP_DATA_DIR
    except Exception:
        APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR") or (Path.home() / ".maic"))
    target = APP_DATA_DIR
    target.mkdir(parents=True, exist_ok=True)

    # 5) ZIP 풀기 (루트 그대로 투하)
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(target)

    # 6) 추출 파일 수 집계
    count = sum(1 for p in target.rglob("*") if p.is_file())
    return {"ok": True, "backup_name": f.get("name"), "modifiedTime": f.get("modifiedTime"),
            "target": str(target), "files": count}

st.subheader("RAG: Restore from Drive BACKUP_ZIP")
if st.button("⬇️ Restore backup zip from Drive"):
    with st.spinner("Restoring from Drive backup…"):
        try:
            res = _restore_from_drive_backup()
            st.success(f"Restored '{res['backup_name']}' → {res['target']}")
            st.caption(f"Modified: {res['modifiedTime']} | Total local files: {res['files']}")

            # 복구 직후 인덱스 재시도(있으면 세션에 저장)
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
