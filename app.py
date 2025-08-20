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
# ===== [02] RAG: Restore / Make Backup (zip → loose → prepared → manual) =====
# 목적:
# 1) BACKUP 폴더에 ZIP이 있으면: 내려받아 APP_DATA_DIR에 풀고 인덱스 로드
# 2) ZIP이 없으면: BACKUP 폴더 안의 느슨한 파일(chunks.jsonl, manifest.json, quality_report.json) 내려받아 복구
# 3) 그래도 없으면: PREPARED 폴더에서 위 3개를 찾아 내려받고 → ZIP으로 묶어 BACKUP 폴더에 업로드(백업 자동생성)
# 4) 전부 없으면: 관리자가 파일 업로드 → ZIP으로 묶어 BACKUP에 올린 뒤 복구

import json, io, os, zipfile
from pathlib import Path
from typing import Any, Mapping, Iterator, Tuple, List, Optional

import streamlit as st

# --- 공통 상수 ----------------------------------------------------------------
REQ_FILES = ["chunks.jsonl", "manifest.json", "quality_report.json"]

# --- (A) 시크릿 전수조사 -----------------------------------------------------
def _iter_secrets(obj: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    try:
        from collections.abc import Mapping as _Mapping
        if isinstance(obj, _Mapping):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                yield from _iter_secrets(v, path)
        else:
            yield (prefix, obj)
    except Exception:
        yield (prefix, obj)

def _flatten_secrets() -> list[Tuple[str, Any]]:
    return list(_iter_secrets(st.secrets))

# --- (B) 서비스계정 JSON 자동 탐색 -------------------------------------------
def _find_service_account_in_secrets() -> dict:
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

    candidates: list[tuple[str, dict]] = []
    for path, val in _flatten_secrets():
        try:
            from collections.abc import Mapping as _Mapping
            if isinstance(val, _Mapping):
                if val.get("type") == "service_account" and "client_email" in val and "private_key" in val:
                    candidates.append((path, dict(val)))
            elif isinstance(val, str):
                if '"type": "service_account"' in val and '"client_email"' in val and '"private_key"' in val:
                    candidates.append((path, json.loads(val)))
        except Exception:
            continue
    if candidates:
        candidates.sort(key=lambda kv: (
            0 if any(tok in kv[0].upper() for tok in ("RAG", "GDRIVE", "SERVICE")) else 1,
            len(kv[0]),
        ))
        return candidates[0][1]
    raise KeyError("서비스계정 JSON을 시크릿에서 찾지 못했습니다.")

# --- (C) 폴더 ID 자동 탐색 ---------------------------------------------------
def _find_folder_id(kind: str) -> Optional[str]:
    """
    kind: 'BACKUP' | 'PREPARED' | 'DEFAULT'
    시크릿에서 대응 키를 찾는다. (중첩 포함)
    """
    key_sets = {
        "BACKUP": ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID"),
        "PREPARED": ("GDRIVE_PREPARED_FOLDER_ID", "PREPARED_FOLDER_ID"),
        "DEFAULT": ("GDRIVE_FOLDER_ID",),
    }
    for key in key_sets.get(kind, ()):
        if key in st.secrets and str(st.secrets[key]).strip():
            return str(st.secrets[key]).strip()
    for path, val in _flatten_secrets():
        try:
            if isinstance(val, (str, int)) and "FOLDER_ID" in path.upper() and str(val).strip():
                up = path.upper()
                if kind == "BACKUP" and "BACKUP" in up:
                    return str(val).strip()
                if kind == "PREPARED" and "PREPARED" in up:
                    return str(val).strip()
                if kind == "DEFAULT" and "GDRIVE_FOLDER_ID" in up:
                    return str(val).strip()
        except Exception:
            continue
    return None

# --- (D) Drive 유틸 ----------------------------------------------------------
def _drive_client():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except Exception as e:
        raise RuntimeError("google-api-python-client / google-auth 패키지가 필요합니다.") from e
    sa_info = _find_service_account_in_secrets()
    creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _download_file_to(service, file_id: str, out_path: Path) -> None:
    from googleapiclient.http import MediaIoBaseDownload
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    out_path.write_bytes(buf.read())

def _find_latest_zip(service, folder_id: str):
    q = f"'{folder_id}' in parents and trashed=false and mimeType='application/zip'"
    resp = service.files().list(q=q, orderBy="modifiedTime desc",
                                fields="files(id,name,modifiedTime,size)", pageSize=1).execute()
    files = resp.get("files", [])
    return files[0] if files else None

def _find_named_files(service, folder_id: str, names: List[str]) -> dict:
    found = {}
    for nm in names:
        q = f"'{folder_id}' in parents and trashed=false and name='{nm}'"
        resp = service.files().list(q=q, fields="files(id,name,size,modifiedTime)", pageSize=1).execute()
        files = resp.get("files", [])
        if files:
            found[nm] = files[0]
    return found

def _upload_zip(service, folder_id: str, path: Path, name: str) -> str:
    media = None
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(path), mimetype="application/zip", resumable=False)
    file_metadata = {"name": name, "parents": [folder_id], "mimeType": "application/zip"}
    created = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created.get("id")

# --- (E) 로컬 경로 -----------------------------------------------------------
def _app_data_dir() -> Path:
    try:
        from src.config import APP_DATA_DIR
        return Path(APP_DATA_DIR)
    except Exception:
        return Path(os.getenv("APP_DATA_DIR") or (Path.home() / ".maic"))

def _ensure_local_index_dir() -> Path:
    p = _app_data_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _zip_local_index(zip_path: Path) -> None:
    base = _ensure_local_index_dir()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fn in REQ_FILES:
            fp = base / fn
            if fp.exists():
                zf.write(fp, arcname=fn)

# --- (F) 핵심: 복구/생성 파이프라인 -----------------------------------------
def _restore_or_make_backup():
    svc = _drive_client()
    # 폴더 탐색 우선순위
    backup_folder = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT")
    prepared_folder = _find_folder_id("PREPARED")

    if not backup_folder:
        raise KeyError("백업 폴더 ID를 찾지 못했습니다. (GDRIVE_BACKUP_FOLDER_ID 또는 GDRIVE_FOLDER_ID)")

    local_dir = _ensure_local_index_dir()

    # 1) ZIP 우선 복구
    z = _find_latest_zip(svc, backup_folder)
    if z:
        buf_zip = local_dir / "_restore.zip"
        _download_file_to(svc, z["id"], buf_zip)
        with zipfile.ZipFile(buf_zip) as zf:
            zf.extractall(local_dir)
        buf_zip.unlink(missing_ok=True)
        return {"mode": "zip_restore", "from": "BACKUP", "name": z.get("name")}

    # 2) BACKUP 폴더의 느슨한 파일 복구
    loose = _find_named_files(svc, backup_folder, REQ_FILES)
    if len(loose) >= 2:  # 최소 2개 이상이면 복구 시도
        for nm, meta in loose.items():
            _download_file_to(svc, meta["id"], local_dir / nm)
        # 보너스: 미래 사용을 위해 ZIP 생성 & 업로드
        tmp_zip = local_dir / "_made_from_loose.zip"
        _zip_local_index(tmp_zip)
        _upload_zip(svc, backup_folder, tmp_zip, "index_backup.zip")
        tmp_zip.unlink(missing_ok=True)
        return {"mode": "loose_restore", "from": "BACKUP", "files": list(loose.keys())}

    # 3) PREPARED 폴더에서 준비물 가져와 ZIP 만들어 BACKUP에 저장 후 복구
    if prepared_folder:
        prep = _find_named_files(svc, prepared_folder, REQ_FILES)
        if len(prep) >= 2:
            for nm, meta in prep.items():
                _download_file_to(svc, meta["id"], local_dir / nm)
            tmp_zip = local_dir / "_made_from_prepared.zip"
            _zip_local_index(tmp_zip)
            _upload_zip(svc, backup_folder, tmp_zip, "index_backup.zip")
            tmp_zip.unlink(missing_ok=True)
            return {"mode": "made_from_prepared", "from": "PREPARED", "files": list(prep.keys())}

    # 4) 전부 없으면: 수동 업로드 UI로 처리하도록 신호
    return {"mode": "need_manual_upload"}

# --- (G) UI ------------------------------------------------------------------
st.subheader("RAG: Restore / Make Backup")
col1, col2 = st.columns(2)
with col1:
    _b = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT") or ""
    st.text_input("Backup folder ID", value=_b, disabled=True)
with col2:
    _p = _find_folder_id("PREPARED") or ""
    st.text_input("Prepared folder ID (optional)", value=_p, disabled=True)

if st.button("🔁 Restore (zip → loose → prepared) / Make backup"):
    with st.spinner("Running restore/make pipeline…"):
        try:
            res = _restore_or_make_backup()
            mode = res.get("mode")
            if mode == "need_manual_upload":
                st.warning("백업 ZIP/느슨한 파일/준비물 모두 없음 → 아래 수동 업로드로 처리하세요.")
            else:
                st.success(f"Done via: {mode} from {res.get('from')}")
                st.caption(str({k: v for k, v in res.items() if k not in ('mode',)}))
                # 복구 직후 인덱스 재시도
                try:
                    idx = get_or_build_index() if get_or_build_index else None
                    if idx is not None:
                        st.session_state["rag_index"] = idx
                        st.success("Index loaded.")
                except Exception as e:
                    st.warning(f"Index reload skipped: {type(e).__name__}: {e}")
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")

# --- (H) 수동 업로드(최후의 보루) --------------------------------------------
st.markdown("**Manual upload (최후의 보루)** — 아래 3개 중 보유한 파일만 올려도 됩니다.")
u_cols = st.columns(3)
up = {
    "chunks.jsonl": u_cols[0].file_uploader("chunks.jsonl", type=["jsonl"]),
    "manifest.json": u_cols[1].file_uploader("manifest.json", type=["json"]),
    "quality_report.json": u_cols[2].file_uploader("quality_report.json", type=["json"]),
}
if st.button("⬆️ Save locally & make BACKUP zip"):
    try:
        base = _ensure_local_index_dir()
        saved = []
        for nm, fl in up.items():
            if fl is not None:
                p = base / nm
                p.write_bytes(fl.read())
                saved.append(nm)
        if not saved:
            st.warning("업로드된 파일이 없습니다.")
        else:
            tmp_zip = base / "_uploaded_make.zip"
            _zip_local_index(tmp_zip)
            # 업로드 대상 폴더
            bfolder = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT")
            if not bfolder:
                raise KeyError("백업 폴더 ID가 없습니다.")
            svc = _drive_client()
            _upload_zip(svc, bfolder, tmp_zip, "index_backup.zip")
            tmp_zip.unlink(missing_ok=True)
            st.success(f"Saved locally: {saved} → backup zip uploaded.")
            # 복구 직후 인덱스 재시도
            try:
                idx = get_or_build_index() if get_or_build_index else None
                if idx is not None:
                    st.session_state["rag_index"] = idx
                    st.success("Index loaded from uploaded files.")
            except Exception as e:
                st.warning(f"Index reload skipped: {type(e).__name__}: {e}")
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")

# ===== [03] END ==============================================================

# ===== [03] END ==============================================================
