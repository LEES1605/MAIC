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
# ===== [02] RAG: Build from PREPARED + Restore/Make Backup ===================
# 목적:
# (A) PREPARED 폴더 ID를 자동 탐지/입력받아 → 최적화(인덱스) 빌드 → 백업 ZIP 업로드
# (B) 기존 Restore/Make Backup 파이프라인 유지(Zip → Loose → Prepared → Manual)

import json, io, os, zipfile
from pathlib import Path
from typing import Any, Mapping, Iterator, Tuple, List, Optional

import streamlit as st

# --- 공통 상수 ----------------------------------------------------------------
REQ_FILES = ["chunks.jsonl", "manifest.json", "quality_report.json"]

# --- (A0) 시크릿 전수조사 ----------------------------------------------------
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

# --- (A1) 서비스계정 JSON 자동 탐색 -------------------------------------------
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

# --- (A2) 폴더 ID 자동 탐색 (APP_* 별칭 지원, URL도 허용) ----------------------
def _find_folder_id(kind: str) -> Optional[str]:
    """
    kind: 'BACKUP' | 'PREPARED' | 'DEFAULT'
    우선순위:
      1) 표준 키 + APP_* 별칭 키
      2) URL 키(값이 URL이면 ID 추출)
      3) 중첩 시크릿 전수조사
      4) 환경변수
    """
    import re, os

    def _parse(v: str) -> Optional[str]:
        v = (v or "").strip()
        for patt in (r"/folders/([A-Za-z0-9_-]{20,})",
                     r"/file/d/([A-Za-z0-9_-]{20,})",
                     r"^([A-Za-z0-9_-]{20,})$"):
            m = re.search(patt, v)
            if m:
                return m.group(1)
        return None

    KEY_PREFS = {
        # PREPARED: 표준 + 기존 프로젝트의 APP_* 키까지 인식
        "PREPARED": (
            "GDRIVE_PREPARED_FOLDER_ID",
            "PREPARED_FOLDER_ID",
            "GDRIVE_PREPARED_FOLDER_URL",
            "PREPARED_FOLDER_URL",
            # 별칭(현재 시크릿과 호환)
            "APP_GDRIVE_FOLDER_ID",
            "APP_PREPARED_FOLDER_ID",
            "APP_GDRIVE_FOLDER_URL",
        ),
        "BACKUP": (
            "GDRIVE_BACKUP_FOLDER_ID",
            "BACKUP_FOLDER_ID",
            "BACKUP_FOLDER_URL",
            # 별칭(현재 시크릿과 호환)
            "APP_BACKUP_FOLDER_ID",
            "APP_BACKUP_FOLDER_URL",
        ),
        "DEFAULT": (
            "GDRIVE_FOLDER_ID",
            "GDRIVE_FOLDER_URL",
        ),
    }

    # 1) 우선 키 직접 조회 (URL이면 ID 추출)
    for k in KEY_PREFS.get(kind, ()):
        if k in st.secrets and str(st.secrets[k]).strip():
            v = str(st.secrets[k]).strip()
            return _parse(v) or v

    # 2) 중첩 시크릿 전수조사 (오타 허용 없음: PREPARED / BACKUP 만)
    TOK = {"PREPARED": ("PREPARED",), "BACKUP": ("BACKUP",), "DEFAULT": ("GDRIVE_FOLDER_ID",)}[kind]
    for path, val in _flatten_secrets():
        try:
            if isinstance(val, (str, int)) and str(val).strip():
                up = path.upper()
                # 키 경로에 목적 토큰 + (FOLDER_ID 또는 URL) 포함 시 후보로 인정
                if any(t in up for t in TOK) and ("FOLDER_ID" in up or "URL" in up or up.endswith(".ID") or up.endswith("_ID")):
                    v = str(val).strip()
                    return _parse(v) or v
        except Exception:
            continue

    # 3) 환경변수도 최후에 확인
    ENV_MAP = {
        "PREPARED": ("GDRIVE_PREPARED_FOLDER_ID", "PREPARED_FOLDER_ID", "APP_GDRIVE_FOLDER_ID", "PREPARED_FOLDER_URL"),
        "BACKUP": ("GDRIVE_BACKUP_FOLDER_ID", "BACKUP_FOLDER_ID", "APP_BACKUP_FOLDER_ID", "BACKUP_FOLDER_URL"),
        "DEFAULT": ("GDRIVE_FOLDER_ID", "GDRIVE_FOLDER_URL"),
    }[kind]
    for e in ENV_MAP:
        v = os.getenv(e)
        if v:
            return _parse(v) or v

    return None


# --- (A3) Drive 유틸 ----------------------------------------------------------
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
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(path), mimetype="application/zip", resumable=False)
    file_metadata = {"name": name, "parents": [folder_id], "mimeType": "application/zip"}
    created = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return created.get("id")

# --- (A4) 로컬 경로 -----------------------------------------------------------
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

# ================= (A) Build from PREPARED 패널 ===============================
st.subheader("RAG: Build from PREPARED (최적화 → 백업 업로드)")
try:
    _prepared_default = _find_folder_id("PREPARED") or ""
except Exception:
    _prepared_default = ""
try:
    _backup_default = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT") or ""
except Exception:
    _backup_default = ""

cols0 = st.columns(2)
with cols0[0]:
    _prepared_input = st.text_input(
        "Prepared folder ID (필수)",
        value=_prepared_default,
        placeholder="예: 1AbCdeFg... (my-ai-teacher-data/prepared)",
        help="시크릿에서 자동 감지된 값이 있으면 채워집니다. 필요하면 직접 입력하세요."
    )
with cols0[1]:
    _backup_disp = st.text_input(
        "Backup folder ID (참고용)",
        value=_backup_default,
        disabled=True,
        help="인덱스 빌더가 완료 후 ZIP을 업로드할 대상(있으면)입니다."
    )

# 인덱스 빌더 호출
try:
    from src.rag.index_build import build_index_with_checkpoint
except Exception:
    build_index_with_checkpoint = None

if st.button("🛠 Build index from PREPARED now"):
    if not _prepared_input.strip():
        st.error("Prepared folder ID가 비었습니다.")
    elif build_index_with_checkpoint is None:
        st.error("인덱스 빌더 모듈을 찾지 못했습니다. (src.rag.index_build)")
    else:
        prog = st.progress(0)
        status = st.empty()
        def _pct(v: int, msg: str | None = None):
            prog.progress(max(0, min(int(v), 100)))
            if msg:
                status.info(str(msg))
        def _msg(s: str):
            status.write(f"• {s}")

        with st.spinner("Building index from PREPARED…"):
            try:
                res = build_index_with_checkpoint(
                    update_pct=_pct,
                    update_msg=_msg,
                    gdrive_folder_id=_prepared_input.strip(),   # PREPARED ID 전달
                    gcp_creds={},                              # 시크릿에서 자동 사용
                    persist_dir="",                            # 내부 기본 사용
                    remote_manifest={},                        # 원격 미사용
                )
                prog.progress(100)
                st.success("Build complete.")
                st.json(res)

                # 빌드 성공 후 인덱스 재로드 시도
                try:
                    from src.rag_engine import get_or_build_index as _gobi
                except Exception:
                    _gobi = None
                if _gobi:
                    try:
                        idx = _gobi()
                        st.session_state["rag_index"] = idx
                        st.success("Index loaded.")
                    except Exception as e:
                        st.warning(f"Index reload skipped: {type(e).__name__}: {e}")
            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")

# ================= (B) Restore / Make Backup 패널 (기존 기능 유지) ============
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
                    from src.rag_engine import get_or_build_index as _gobi2
                except Exception:
                    _gobi2 = None
                if _gobi2:
                    try:
                        idx = _gobi2()
                        st.session_state["rag_index"] = idx
                        st.success("Index loaded.")
                    except Exception as e:
                        st.warning(f"Index reload skipped: {type(e).__name__}: {e}")
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")

# --- (B-끝) 수동 업로드(최후의 보루) -----------------------------------------
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
            bfolder = _find_folder_id("BACKUP") or _find_folder_id("DEFAULT")
            if not bfolder:
                raise KeyError("백업 폴더 ID가 없습니다.")
            svc = _drive_client()
            _upload_zip(svc, bfolder, tmp_zip, "index_backup.zip")
            tmp_zip.unlink(missing_ok=True)
            st.success(f"Saved locally: {saved} → backup zip uploaded.")
            try:
                from src.rag_engine import get_or_build_index as _gobi3
            except Exception:
                _gobi3 = None
            if _gobi3:
                try:
                    idx = _gobi3()
                    st.session_state["rag_index"] = idx
                    st.success("Index loaded from uploaded files.")
                except Exception as e:
                    st.warning(f"Index reload skipped: {type(e).__name__}: {e}")
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")

# ===== [02A] OAUTH: Refresh Token Helper (auto-detect & no re-prompt) =======
import urllib.parse
import streamlit as st

st.subheader("🔑 OAuth Refresh Token Helper (for Google Drive)")

SCOPE = "https://www.googleapis.com/auth/drive"
token_uri = st.secrets.get("GDRIVE_OAUTH_TOKEN_URI", "https://oauth2.googleapis.com/token")
cid  = st.secrets.get("GDRIVE_OAUTH_CLIENT_ID")
csec = st.secrets.get("GDRIVE_OAUTH_CLIENT_SECRET")
rt_secret = st.secrets.get("GDRIVE_OAUTH_REFRESH_TOKEN") or st.secrets.get("GOOGLE_OAUTH_REFRESH_TOKEN")

def _mask(s: str) -> str:
    try:
        return f"{s[:6]}…{s[-6:]}" if s and len(s) > 14 else "********"
    except Exception:
        return "********"

# 0) 클라이언트 감지
if not (cid and csec):
    st.error("먼저 secrets에 GDRIVE_OAUTH_CLIENT_ID / GDRIVE_OAUTH_CLIENT_SECRET 를 넣어주세요.")
    st.stop()

# A) 이미 토큰이 있으면 입력 UI 숨기고 감지만 표시
if rt_secret:
    st.success("✅ Refresh token(시크릿 저장)을 감지했습니다. 재입력 필요 없습니다.")
    with st.expander("세부 정보 / 빠른 점검", expanded=False):
        st.write(f"• Client ID: `{cid}`")
        st.write(f"• Refresh token: `{_mask(rt_secret)}`")
        if st.button("🔎 Quick check (실제 갱신 시도)"):
            try:
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request
                creds = Credentials(
                    None,
                    refresh_token=str(rt_secret),
                    client_id=str(cid),
                    client_secret=str(csec),
                    token_uri=str(token_uri),
                    scopes=[SCOPE],
                )
                creds.refresh(Request())  # 실패 시 예외
                st.success("OK! 토큰 유효합니다. 업로드는 OAuth 모드로 동작합니다.")
            except Exception as e:
                st.error(f"검증 실패: {type(e).__name__}: {e}")
                st.info("• Client Secret을 바꿨다면 새 토큰이 필요합니다.\n"
                        "• 계정의 앱 권한을 제거했다면 다시 발급하세요.")
else:
    # B) 토큰이 없을 때만 발급 안내 + 입력/검증 UI 노출
    st.info("GCP OAuth 클라이언트가 감지되었습니다. 아래 1~3단계로 Refresh Token을 발급하세요.")

    playground_base = "https://developers.google.com/oauthplayground"
    pre_filled = f"{playground_base}/?scope={urllib.parse.quote(SCOPE)}#step1"
    st.markdown(f"**1) OAuth Playground 열기** → [Open OAuth Playground (pre-filled scope)]({pre_filled})")
    st.caption(
        "Playground 좌측 하단 ⚙️에서 **Use your own OAuth credentials**를 켜고\n"
        "Client ID/Secret에 지금 secrets의 값을 입력 → Access type=Offline / Force prompt=Yes → "
        "Step 1 'Authorize APIs' → Step 2 'Exchange…' 후 refresh_token 복사."
    )

    rt_input = st.text_input("2) Refresh token 붙여넣기", value="", type="password")
    col1, col2 = st.columns([1,1])
    with col1:
        validate = st.button("✅ Validate & show secrets line")
    with col2:
        clear = st.button("🧹 Clear")

    if clear:
        st.experimental_rerun()

    if validate:
        if not rt_input.strip():
            st.error("Refresh token이 비었습니다.")
        else:
            try:
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request
                creds = Credentials(
                    None,
                    refresh_token=rt_input.strip(),
                    client_id=str(cid),
                    client_secret=str(csec),
                    token_uri=str(token_uri),
                    scopes=[SCOPE],
                )
                creds.refresh(Request())  # 유효성 검증
                st.success("유효한 Refresh token 입니다. 아래 한 줄을 secrets에 추가하세요.")
                st.code(f'GDRIVE_OAUTH_REFRESH_TOKEN = "{rt_input.strip()}"', language="toml")
                st.caption("Streamlit Cloud: Settings → Secrets에 붙여넣고 Save\n"
                           "로컬: .streamlit/secrets.toml 파일에 추가 후 재실행")
            except Exception as e:
                st.error(f"검증 실패: {type(e).__name__}: {e}")
                st.info("• Playground 설정(Use your own creds/Offline/Force prompt)을 다시 확인하세요.\n"
                        "• OAuth 클라이언트의 Redirect URI 목록에 "
                        "`https://developers.google.com/oauthplayground` 가 있어야 합니다.")
# ============================================================================ 



# ===== [03] END ==============================================================
