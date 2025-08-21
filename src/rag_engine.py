# ===== [01] IMPORTS ==========================================================
from __future__ import annotations

import io
import json
import os
import zipfile
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st
from src.compat.config_bridge import PERSIST_DIR  # 호환용(로컬 인덱스가 있을 때만 사용)


# ===== [02] ERRORS ===========================================================
class RAGEngineError(Exception):
    ...


class QueryEngineNotReady(RAGEngineError):
    ...


class LocalIndexMissing(RAGEngineError):
    ...


# ===== [03] LOCAL PATH HELPERS (fallback 전용) ===============================
def _as_path(p: str | PathLike[str]) -> Path:
    return Path(p)


def _index_exists(persist_dir: str | PathLike[str]) -> bool:
    """로컬 폴더에 무언가가 있으면 True (완전 remote-only라면 False 여야 함)."""
    p = _as_path(persist_dir)
    try:
        return p.exists() and any(p.iterdir())
    except Exception:
        return False


# ===== [04] SECRETS/ID HELPERS ==============================================
def _flatten_secrets(obj: Any = None, prefix: str = "") -> List[Tuple[str, Any]]:
    from collections.abc import Mapping as _Map
    if obj is None:
        obj = st.secrets
    out: List[Tuple[str, Any]] = []
    try:
        if isinstance(obj, _Map):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                out.extend(_flatten_secrets(v, path))
        else:
            out.append((prefix, obj))
    except Exception:
        out.append((prefix, obj))
    return out


def _parse_drive_id(s: str) -> Optional[str]:
    """URL/ID 혼합 입력에서 폴더/파일 ID만 추출."""
    s = (s or "").strip()
    import re
    for patt in (
        r"/folders/([A-Za-z0-9_-]{20,})",
        r"/file/d/([A-Za-z0-9_-]{20,})",
        r"^([A-Za-z0-9_-]{20,})$",
    ):
        m = re.search(patt, s)
        if m:
            return m.group(1)
    return None


def _find_folder_id(kind: str) -> Optional[str]:
    """
    kind: 'BACKUP' | 'PREPARED' | 'DEFAULT'
    표준 키 + 프로젝트 별칭(APP_*)까지 폭넓게 인식.
    """
    KEY_PREFS = {
        "BACKUP": (
            "GDRIVE_BACKUP_FOLDER_ID",
            "BACKUP_FOLDER_ID",
            "BACKUP_FOLDER_URL",
            "APP_BACKUP_FOLDER_ID",  # 별칭 호환
        ),
        "PREPARED": (
            "GDRIVE_PREPARED_FOLDER_ID",
            "PREPARED_FOLDER_ID",
            "PREPARED_FOLDER_URL",
            "APP_GDRIVE_FOLDER_ID",  # 별칭 호환(프로젝트에선 prepared로 사용)
        ),
        "DEFAULT": ("GDRIVE_FOLDER_ID", "GDRIVE_FOLDER_URL"),
    }
    for k in KEY_PREFS.get(kind, ()):
        if k in st.secrets and str(st.secrets[k]).strip():
            v = str(st.secrets[k]).strip()
            return _parse_drive_id(v) or v

    # 중첩 탐색 (키 경로에 토큰이 포함되면 후보로 인정)
    TOK = {
        "BACKUP": ("BACKUP",),
        "PREPARED": ("PREPARED", "APP_GDRIVE_FOLDER_ID", "SOURCE", "DATA"),
        "DEFAULT": ("GDRIVE_FOLDER_ID",),
    }[kind]
    for path, val in _flatten_secrets():
        try:
            if isinstance(val, (str, int)) and str(val).strip():
                up = path.upper()
                if any(t in up for t in TOK) and (
                    "FOLDER_ID" in up or "URL" in up or up.endswith(".ID") or up.endswith("_ID")
                ):
                    v = str(val).strip()
                    return _parse_drive_id(v) or v
        except Exception:
            continue

    # 환경변수도 확인
    ENV = {
        "BACKUP": ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID", "BACKUP_FOLDER_URL"),
        "PREPARED": ("GDRIVE_PREPARED_FOLDER_ID", "PREPARED_FOLDER_ID", "PREPARED_FOLDER_URL", "APP_GDRIVE_FOLDER_ID"),
        "DEFAULT": ("GDRIVE_FOLDER_ID", "GDRIVE_FOLDER_URL"),
    }[kind]
    for e in ENV:
        v = os.getenv(e)
        if v:
            return _parse_drive_id(v) or v
    return None


# ===== [05] GOOGLE DRIVE AUTH (OAuth 우선, SA 폴백) ==========================
def _get_drive_credentials():
    # 1) 사용자 OAuth (My Drive에 '생성/업로드' 가능)
    cid = st.secrets.get("GDRIVE_OAUTH_CLIENT_ID") or st.secrets.get("GOOGLE_OAUTH_CLIENT_ID")
    csec = st.secrets.get("GDRIVE_OAUTH_CLIENT_SECRET") or st.secrets.get("GOOGLE_OAUTH_CLIENT_SECRET")
    rtok = st.secrets.get("GDRIVE_OAUTH_REFRESH_TOKEN") or st.secrets.get("GOOGLE_OAUTH_REFRESH_TOKEN")
    t_uri = st.secrets.get("GDRIVE_OAUTH_TOKEN_URI") or "https://oauth2.googleapis.com/token"
    if cid and csec and rtok:
        from google.oauth2.credentials import Credentials as UserCreds

        return (
            UserCreds(
                None,
                refresh_token=str(rtok),
                client_id=str(cid),
                client_secret=str(csec),
                token_uri=str(t_uri),
                scopes=["https://www.googleapis.com/auth/drive"],
            ),
            "oauth",
        )

    # 2) 서비스계정(SA) — 개인 드라이브에서 '새로 업로드'는 불가(공유드라이브/이미 존재 파일 갱신/읽기 위주)
    sa_raw = None
    for k in (
        "GDRIVE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "SERVICE_ACCOUNT_JSON",
        "APP_GDRIVE_SERVICE_ACCOUNT_JSON",
    ):
        if k in st.secrets and str(st.secrets[k]).strip():
            sa_raw = st.secrets[k]
            break
    if sa_raw is None:
        for _, v in _flatten_secrets():
            try:
                from collections.abc import Mapping as _Map
                if isinstance(v, _Map) and v.get("type") == "service_account" and "private_key" in v:
                    sa_raw = v
                    break
                if isinstance(v, str) and '"type": "service_account"' in v:
                    sa_raw = v
                    break
            except Exception:
                pass
    if sa_raw is None:
        raise RuntimeError("Drive 자격정보가 없습니다 (OAuth 또는 Service Account).")

    info = json.loads(sa_raw) if isinstance(sa_raw, str) else dict(sa_raw)
    from google.oauth2.service_account import Credentials as SACreds

    return SACreds.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"]), "sa"


def _drive_client():
    from googleapiclient.discovery import build

    creds, mode = _get_drive_credentials()
    st.session_state["gdrive_auth_mode"] = mode  # 디버그 표시에 사용
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ===== [06] REMOTE-ONLY LOAD =================================================
def _download_latest_backup_zip_bytes() -> Tuple[bytes, Dict[str, Any]]:
    """백업 폴더에서 최신 ZIP을 찾아서 '메모리로' 다운로드."""
    backup_folder = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT")
    if not backup_folder:
        raise LocalIndexMissing("백업 폴더 ID(GDRIVE_BACKUP_FOLDER_ID/GDRIVE_FOLDER_ID)가 없습니다.")

    svc = _drive_client()
    q = f"'{backup_folder}' in parents and trashed=false and mimeType='application/zip'"
    resp = svc.files().list(
        q=q,
        orderBy="modifiedTime desc",
        fields="files(id,name,modifiedTime,size)",
        pageSize=1,
        supportsAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    if not files:
        raise LocalIndexMissing("드라이브 백업 ZIP이 없습니다.")

    meta = files[0]
    req = svc.files().get_media(fileId=meta["id"])
    from googleapiclient.http import MediaIoBaseDownload

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf.read(), meta


def _load_index_in_memory_from_drive() -> Dict[str, Any]:
    """백업 ZIP을 메모리에서 바로 파싱하여 인덱스(dict)를 반환(디스크 저장 X)."""
    blob, meta = _download_latest_backup_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = set(zf.namelist())

        def _read_json(name: str, default: Any) -> Any:
            try:
                with zf.open(name, "r") as f:
                    return json.loads(f.read().decode("utf-8"))
            except Exception:
                return default

        data: Dict[str, Any] = {
            "_origin": {"drive_file": meta},
            "manifest": _read_json("manifest.json", {}),
            "quality_report": _read_json("quality_report.json", {}),
            "chunks": [],
        }
        if "chunks.jsonl" in names:
            with zf.open("chunks.jsonl", "r") as f:
                for raw in f:
                    line = raw.decode("utf-8").strip()
                    if line:
                        try:
                            data["chunks"].append(json.loads(line))
                        except Exception:
                            pass
        return data


# ===== [07] LOCAL LOAD (fallback; 선택) ======================================
def _load_index_from_disk(persist_dir: str | PathLike[str]) -> Dict[str, Any]:
    """로컬 폴더에 인덱스가 있는 경우만 사용."""
    p = _as_path(persist_dir)
    reqs = ["chunks.jsonl", "manifest.json", "quality_report.json"]
    if not (p.exists() and all((p / f).exists() for f in reqs)):
        raise LocalIndexMissing("No local index")

    data: Dict[str, Any] = {"manifest": {}, "quality_report": {}, "chunks": []}
    data["manifest"] = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
    try:
        data["quality_report"] = json.loads((p / "quality_report.json").read_text(encoding="utf-8"))
    except Exception:
        data["quality_report"] = {}
    with (p / "chunks.jsonl").open("r", encoding="utf-8") as f:
        data["chunks"] = [json.loads(line) for line in f if line.strip()]
    return data


# ===== [08] SIMPLE QUERY ENGINE WRAPPER ======================================
class _SimpleQE:
    """아주 단순한 쿼리엔진(데모/디버그용)."""

    def __init__(self, idx: Dict[str, Any]) -> None:
        self.idx = idx

    def query(self, q: str) -> Any:
        # 최소 동작: 질문을 에코하고, 청크 수 통계만 보여줌
        total = len(self.idx.get("chunks", []))
        return type("R", (), {"response": f"[RAG stub] chunks={total}, q={q}"})


class _Index:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data

    def as_query_engine(self, **kw: Any) -> _SimpleQE:
        return _SimpleQE(self.data)


# ===== [09] PUBLIC API =======================================================
def get_or_build_index(
    update_pct: Optional[Callable[[int], None]] = None,
    update_msg: Optional[Callable[[str], None]] = None,
    gdrive_folder_id: Optional[str] = None,
    raw_sa: Optional[str] = None,
    persist_dir: str | PathLike[str] = str(PERSIST_DIR),
    manifest_path: Optional[str] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Any:
    """
    1) 로컬에 인덱스가 있으면 그대로 사용
    2) 없으면 Google Drive의 최신 백업 ZIP을 '메모리로' 읽어 로드(로컬 저장 X)
    """
    # 1) 로컬 우선
    try:
        if _index_exists(persist_dir):
            return _Index(_load_index_from_disk(persist_dir))
    except Exception:
        # 로컬이 망가져도 원격 시도
        pass

    # 2) 원격(in-memory)
    data = _load_index_in_memory_from_drive()
    return _Index(data)


# ===== [10] END ==============================================================
