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
# 바로 인덱스를 재로딩합니다. (시크릿이 섹션/중첩 안에 있어도 자동 탐색)

import json, io, os, zipfile
from pathlib import Path
from typing import Any, Mapping, Iterator, Tuple

# --- (A) 시크릿 전수조사 도우미 ---------------------------------------------
def _iter_secrets(obj: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """
    st.secrets 전체를 재귀적으로 훑어서 (경로키, 값) 튜플을 뽑습니다.
    경로키 예: 'RAG.GDRIVE_FOLDER_ID'
    """
    try:
        # Mapping(dict 유사)이면 항목 순회
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                yield from _iter_secrets(v, path)
        else:
            # 말단 값
            yield (prefix, obj)
    except Exception:
        # st.secrets 내부 타입 차이 대비
        yield (prefix, obj)

def _flatten_secrets() -> list[Tuple[str, Any]]:
    return list(_iter_secrets(st.secrets))

# --- (B) 서비스계정 JSON 자동 탐색 -------------------------------------------
def _find_service_account_in_secrets() -> dict:
    # 1) 흔한 키 우선
    preferred = (
        "GDRIVE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "SERVICE_ACCOUNT_JSON",
        "gdrive_service_account_json",
        "service_account_json",
        "GCP_SERVICE_ACCOUNT",
        "gcp_service_account",
    )
    for key in preferred:
        if key in st.secrets and str(st.secrets[key]).strip():
            raw = st.secrets[key]
            return json.loads(raw) if isinstance(raw, str) else dict(raw)

    # 2) 전수조사(중첩 포함)
    candidates: list[tuple[str, dict]] = []
    for path, val in _flatten_secrets():
        try:
            if isinstance(val, Mapping):
                if val.get("type") == "service_account" and "client_email" in val and "private_key" in val:
                    candidates.append((path, dict(val)))
            elif isinstance(val, str):
                if '"type": "service_account"' in val and '"client_email"' in val and '"private_key"' in val:
                    candidates.append((path, json.loads(val)))
        except Exception:
            continue
    if candidates:
        # 경로에 'RAG' / 'GDRIVE' / 'SERVICE' 같은 힌트가 있으면 우선
        candidates.sort(key=lambda kv: (
            0 if any(tok in kv[0].upper() for tok in ("RAG", "GDRIVE", "SERVICE")) else 1,
            len(kv[0]),
        ))
        return candidates[0][1]

    raise KeyError(
        "서비스계정 JSON을 시크릿에서 찾지 못했습니다. "
        "예: 최상위에 GDRIVE_SERVICE_ACCOUNT_JSON = '''{...}'''"
    )

# --- (C) 백업 폴더 ID 자동 탐색 ----------------------------------------------
def _find_backup_folder_id() -> str:
    # 1) 흔한 키 우선
    for key in ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID", "GDRIVE_FOLDER_ID"):
        if key in st.secrets and str(st.secrets[key]).strip():
            return str(st.secrets[key]).strip()

    # 2) 전수조사(중첩 포함) — FOLDER_ID를 품은 키 수집
    found: list[Tuple[str, str]] = []
    for path, val in _flatten_secrets():
        try:
            if isinstance(val, (str, int)) and "FOLDER_ID" in path.upper() and str(val).strip():
                found.append((path, str(val).strip()))
        except Exception:
            continue
    if not found:
        raise KeyError(
            "백업 폴더 ID를 찾지 못했습니다. "
            "권장: GDRIVE_BACKUP_FOLDER_ID = '폴더_ID' (또는 GDRIVE_FOLDER_ID) 를 시크릿에 추가"
        )
    # 'BACKUP'을 포함한 경로 우선, 그 다음 경로 길이 짧은 것
    found.sort(key=lambda kv: (0 if "BACKUP" in kv[0].upper() else 1, len(kv[0])))
    return found[0][1]

# --- (D) 복구 로직 -----------------------------------------------------------
def _restore_from_drive_backup(folder_id: str):
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except Exception as e:
        raise RuntimeError("google-api-python-client / google-auth 패키지가 필요합니다.") from e

    sa_info = _find_service_account_in_secrets()
    creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/drive.readonly"])

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

# --- (E) UI: 폴더 ID 자동제안 + 복구 버튼 -----------------------------------
_suggest = _find_backup_folder_id if True else lambda: None  # 명시적 호출
try:
    _default_folder = _suggest()
except Exception:
    _default_folder = ""

st.subheader("RAG: Restore from Drive BACKUP_ZIP")
folder_input = st.text_input("Backup folder ID (자동 감지값이 있으면 미리 채워집니다)", value=_default_folder, help="예: 1AbCdeFg... (Drive 폴더 ID)")

if st.button("⬇️ Restore backup zip from Drive"):
    with st.spinner("Restoring from Drive backup…"):
        try:
            fid = folder_input.strip() or _find_backup_folder_id()
            res = _restore_from_drive_backup(fid)
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
