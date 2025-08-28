# ==== [HEAD] future import must be first =====================================
from __future__ import annotations  # 반드시 파일 첫 실행문

# ===== [00A-FIX] ENV BOOTSTRAP (secrets → os.environ) ========================
import os
try:
    import streamlit as st  # Streamlit Cloud에서만 존재할 수 있음
except Exception:
    st = None

def _val_from_secrets(name: str):
    """secrets에서 안전하게 값 꺼내기 (없으면 None)"""
    try:
        if st is None:
            return None
        if hasattr(st.secrets, "get"):
            v = st.secrets.get(name, None)
        else:
            v = st.secrets[name]  # 없으면 예외
        return str(v) if v is not None else None
    except Exception:
        return None

def _bootstrap_env_from_secrets() -> None:
    """필요한 키/모델/설정값을 환경변수로 승격"""
    if st is None:
        return
    keys = (
        # 드라이브/경로
        "MAIC_PROMPTS_DRIVE_FOLDER_ID",
        "MAIC_PROMPTS_PATH",
        # LLM 자격/모델
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    )
    for k in keys:
        v = _val_from_secrets(k)
        if v and not os.getenv(k):
            os.environ[k] = v

_bootstrap_env_from_secrets()
# ===== [00A-FIX] END =========================================================

# ===== [00B] ERROR LOG 헬퍼 — START ==========================================
def _errlog(msg: str, *, where: str = "", exc: Exception | None = None):
    """에러/경고를 세션 로그에 적재(관리자 패널에서 복사/다운로드 가능)."""
    import traceback, datetime, io
    ss = st.session_state
    ss.setdefault("_error_log", [])
    rec = {
        "ts": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "where": where,
        "msg": str(msg),
        "trace": traceback.format_exc() if exc else "",
    }
    ss["_error_log"].append(rec)

def _errlog_text() -> str:
    """세션 내 에러 로그를 텍스트로 직렬화."""
    ss = st.session_state
    buf = io.StringIO()
    for i, r in enumerate(ss.get("_error_log", []), 1):
        buf.write(f"[{i}] {r['ts']}  {r.get('where','')}\n{r['msg']}\n")
        if r.get("trace"): buf.write(r["trace"] + "\n")
        buf.write("-" * 60 + "\n")
    return buf.getvalue()
# ===== [00B] ERROR LOG 헬퍼 — END ============================================

# ===== [01] 앱 부트 & 환경 변수 세팅 ========================================
import os

# Streamlit 서버 관련 환경변수 (성능/안정화 목적)
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUN_ON_SAVE"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION"] = "false"

# ===== [01] END ===============================================================

# ===== [02] IMPORTS & RAG 바인딩(예외 내성) ================================
from pathlib import Path
import os, sys
from typing import List, Any

# 전역 바인딩 기본값(안전장치)
get_or_build_index = None
LocalIndexMissing = None

# 인덱스 빌드/프리체크 관련 함수들(전역으로 항상 존재하도록: 없으면 None)
precheck_build_needed = None
quick_precheck = None
build_index_with_checkpoint = None
restore_latest_backup_to_local = None
_make_and_upload_backup_zip = None

# 임포트 오류 모음(BOOT-WARN/진단에서 표시)
_import_errors: List[str] = []

def _try_bind_from(modname: str) -> bool:
    """modname에서 필요한 심볼들을 가능한 만큼 바인딩. 하나라도 성공하면 True."""
    global get_or_build_index, LocalIndexMissing
    global precheck_build_needed, quick_precheck, build_index_with_checkpoint
    global restore_latest_backup_to_local, _make_and_upload_backup_zip
    try:
        m = __import__(modname, fromlist=["*"])
    except Exception as e:
        _import_errors.append(f"{modname}: {type(e).__name__}: {e}")
        return False
    try:
        if getattr(m, "get_or_build_index", None):
            get_or_build_index = m.get_or_build_index
        if getattr(m, "LocalIndexMissing", None):
            LocalIndexMissing = m.LocalIndexMissing
        if getattr(m, "precheck_build_needed", None):
            precheck_build_needed = m.precheck_build_needed
        if getattr(m, "quick_precheck", None):
            quick_precheck = m.quick_precheck
        if getattr(m, "build_index_with_checkpoint", None):
            build_index_with_checkpoint = m.build_index_with_checkpoint
        if getattr(m, "restore_latest_backup_to_local", None):
            restore_latest_backup_to_local = m.restore_latest_backup_to_local
        if getattr(m, "_make_and_upload_backup_zip", None):
            _make_and_upload_backup_zip = m._make_and_upload_backup_zip
        return True
    except Exception as e:
        _import_errors.append(f"{modname} bind: {type(e).__name__}: {e}")
        return False

# 1) 우선 경로: src.rag.index_build → 실패 시 2) 대체 경로: rag.index_build
resolved = _try_bind_from("src.rag.index_build")
if not resolved:
    _try_bind_from("rag.index_build")

# 3) 최종 안전망: LocalIndexMissing이 없으면 대체 예외 정의
if LocalIndexMissing is None:
    class LocalIndexMissing(Exception):
        """로컬 인덱스가 없거나 읽을 수 없음을 나타내는 예외(대체 정의)."""
        ...

# 4) 최종 안전망: get_or_build_index 폴백 래퍼
#    - 실제 엔진이 없어도 세션 부착을 가능하게 하는 경량 객체를 반환
if get_or_build_index is None:
    def get_or_build_index() -> Any:  # type: ignore[override]
        base = Path.home() / ".maic" / "persist"
        chunks = base / "chunks.jsonl"
        ready  = base / ".ready"
        if chunks.exists() or ready.exists():
            class _LiteIndex:
                def __init__(self, persist_dir: Path):
                    self.persist_dir = str(persist_dir)
                def __repr__(self) -> str:
                    return f"<LiteRAGIndex persist_dir='{self.persist_dir}'>"
            return _LiteIndex(base)
        # 파일 신호도 없으면 진짜로 로컬 인덱스 없음
        raise LocalIndexMissing("No local index signals (.ready/chunks.jsonl)")

# 5) 디버그 힌트(관리자만 확인 가능)
os.environ.setdefault("MAIC_IMPORT_INDEX_BUILD_RESOLVE",
    "resolved" if resolved else "fallback_or_partial")
# ===== [02] END ===============================================================

# ===== [BOOT-WARN] set_page_config 이전 경고 누적 ============================
from typing import List

_BOOT_WARNINGS: List[str] = []

# precheck는 precheck_build_needed 또는 quick_precheck 둘 중 하나만 있어도 정상
_no_precheck = (precheck_build_needed is None and quick_precheck is None)
_no_builder  = (build_index_with_checkpoint is None)

if _no_precheck or _no_builder:
    msgs = []
    if _no_precheck:
        msgs.append("• 사전점검 함수(precheck_build_needed 또는 quick_precheck)를 찾지 못했습니다.")
    if _no_builder:
        msgs.append("• 빌더 함수(build_index_with_checkpoint)를 찾지 못했습니다.")
    import_errs = globals().get("_import_errors") or []
    if import_errs:
        msgs.append("\n[임포트 오류]\n" + "\n".join(f"  - {m}" for m in import_errs))
    guide = (
        "\n확인하세요:\n"
        "1) 파일 존재: src/rag/index_build.py\n"
        "2) 패키지 마커: src/__init__.py, src/rag/__init__.py\n"
        "3) 함수 이름: precheck_build_needed **또는** quick_precheck 중 하나 필요\n"
        "4) import 철자: index_build(언더스코어), index.build(점) 아님"
    )
    _BOOT_WARNINGS.append("사전점검/빌더 임포트에 실패했습니다.\n" + "\n".join(msgs) + guide)
# ===== [BOOT-WARN] END =======================================================

# ===== [03] SESSION & HELPERS ===============================================
st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태 키
st.session_state.setdefault("rag_index", None)
st.session_state.setdefault("mode", "Grammar")    # Grammar | Sentence | Passage
st.session_state.setdefault("qa_submitted", False)
st.session_state.setdefault("_attach_log", [])    # ✅ attach/restore 상세 로그 보관

def _log_attach(step: str, **fields):
    """
    자동/강제 attach 및 복구 과정의 상세 로그를 세션에 기록.
    - step: 단계 태그 (예: 'start', 'local_attach_ok', 'drive_restore_fail' 등)
    - fields: 부가 정보 (status, error, counts 등)
    """
    from datetime import datetime
    try:
        entry = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "step": step}
        if fields: entry.update(fields)
        logs = st.session_state.get("_attach_log") or []
        logs.append(entry)
        # 오래된 로그는 정리(최대 200개 유지)
        if len(logs) > 200:
            logs = logs[-200:]
        st.session_state["_attach_log"] = logs
    except Exception:
        pass

# >>>>> START [A01] _force_persist_dir (config 기준 강제 통일)
def _force_persist_dir() -> str:
    """
    내부 모듈들이 사용하는 PERSIST_DIR을 'config 기준'으로 강제 통일.
    - src.rag.index_build / rag.index_build 의 PERSIST_DIR 속성 주입
    - 환경변수 MAIC_PERSIST_DIR 세팅
    """
    import importlib, os
    from pathlib import Path
    from src.config import PERSIST_DIR as _PD

    target = Path(_PD).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    for modname in ("src.rag.index_build", "rag.index_build"):
        try:
            m = importlib.import_module(modname)
            try:
                setattr(m, "PERSIST_DIR", target)
            except Exception:
                pass
        except Exception:
            continue

    os.environ["MAIC_PERSIST_DIR"] = str(target)
    _log_attach("force_persist_dir", target=str(target))
    return str(target)
# <<<<< END [A01] _force_persist_dir


def _is_attached_session() -> bool:
    """세션에 실제로 두뇌가 붙었는지(여러 키 중 하나라도 있으면 True)."""
    ss = st.session_state
    return bool(
        ss.get("brain_attached") or
        ss.get("rag_index") or
        ss.get("retriever") or
        ss.get("vectorstore") or
        ss.get("rag")
    )

# >>>>> START [A02] _has_local_index_files (config 기준 검사)
def _has_local_index_files() -> bool:
    """config의 PERSIST_DIR 안에 .ready 또는 chunks.jsonl이 있는지 신호만 확인."""
    from pathlib import Path as _P
    try:
        from src.config import PERSIST_DIR as _PD
        _PERSIST_DIR = _P(_PD)
    except Exception:
        # 최후 폴백(정상 환경에서는 도달하지 않음)
        _PERSIST_DIR = _P.home() / ".maic" / "persist"

    chunks = _PERSIST_DIR / "chunks.jsonl"
    ready  = _PERSIST_DIR / ".ready"
    ch_ok = chunks.exists() and (chunks.stat().st_size > 0)
    return bool(ch_ok or ready.exists())
# <<<<< END [A02] _has_local_index_files


def get_index_status() -> str:
    """
    단일 기준의 인덱스 상태:
      - 'ready'   : 세션에 부착 완료
      - 'pending' : 세션 미부착, 로컬 파일 신호(.ready/chunks.jsonl)만 존재
      - 'missing' : 로컬 신호 없음
    """
    if _is_attached_session():
        return "ready"
    if _has_local_index_files():
        return "pending"
    return "missing"

def _attach_from_local() -> bool:
    """로컬 인덱스를 세션에 부착 시도."""
    _force_persist_dir()
    if get_or_build_index is None:
        _log_attach("local_attach_skip", reason="get_or_build_index_none")
        return False
    try:
        _log_attach("local_attach_try")
        idx = get_or_build_index()
        st.session_state["rag_index"] = idx
        # ✅ 성공 시 플래그 명확화
        st.session_state["brain_attached"] = True
        st.session_state["rag_index_attached"] = True
        _log_attach("local_attach_ok")
        return True
    except LocalIndexMissing:
        _log_attach("local_attach_fail", error="LocalIndexMissing")
        return False
    except Exception as e:
        _log_attach("local_attach_fail", error=f"{type(e).__name__}: {e}")
        return False

def _auto_attach_or_restore_silently() -> bool:
    """
    1) 로컬 부착 시도
    2) 실패 시: 드라이브 최신 백업 ZIP 복구 → 다시 부착
    3) 그래도 실패 시: 최소 옵션으로 인덱스 재빌드 → 다시 부착
    (모든 예외는 삼키고, 성공 시 True/실패 시 False 반환)
    """
    import importlib
    st.session_state["_auto_restore_last"] = {
        "step": "start",
        "local_attach": None,
        "drive_restore": None,
        "rebuild": None,
        "final_attach": None,
    }
    _log_attach("auto_attach_start")

    _force_persist_dir()

    # 1) 로컬 attach
    if _attach_from_local():
        st.session_state["_auto_restore_last"].update(step="attached_local", local_attach=True, final_attach=True)
        _log_attach("auto_attach_done", path="local")
        return True
    st.session_state["_auto_restore_last"]["local_attach"] = False
    _log_attach("local_attach_result", ok=False)

    # 2) 드라이브에서 복구 시도
    try:
        mod = importlib.import_module("src.rag.index_build")
        restore_fn = getattr(mod, "restore_latest_backup_to_local", None)
        ok_restore = bool(callable(restore_fn) and (restore_fn() or {}).get("ok"))
    except Exception as e:
        ok_restore = False
        _log_attach("drive_restore_exception", error=f"{type(e).__name__}: {e}")
    st.session_state["_auto_restore_last"]["drive_restore"] = ok_restore
    _log_attach("drive_restore_result", ok=bool(ok_restore))

    if ok_restore and _has_local_index_files() and _attach_from_local():
        st.session_state["_auto_restore_last"].update(step="restored_and_attached", final_attach=True)
        _log_attach("auto_attach_done", path="drive_restore")
        return True

    # 3) 마지막 안전망: 인덱스 재생성
    ok_rebuild = None
    try:
        mod = importlib.import_module("src.rag.index_build")
        build_fn = getattr(mod, "build_index_with_checkpoint", None)
        persist_dir = getattr(mod, "PERSIST_DIR", Path.home() / ".maic" / "persist")
        if callable(build_fn):
            try:
                _log_attach("rebuild_try", persist_dir=str(persist_dir))
                build_fn(
                    update_pct=lambda *_a, **_k: None,
                    update_msg=lambda *_a, **_k: None,
                    gdrive_folder_id="",
                    gcp_creds={},
                    persist_dir=str(persist_dir),
                    remote_manifest={},
                )
            except TypeError:
                build_fn()
            ok_rebuild = True
            _log_attach("rebuild_ok")
        else:
            ok_rebuild = False
            _log_attach("rebuild_skip", reason="build_fn_not_callable")
    except Exception as e:
        ok_rebuild = False
        _log_attach("rebuild_fail", error=f"{type(e).__name__}: {e}")
    st.session_state["_auto_restore_last"]["rebuild"] = ok_rebuild

    if _attach_from_local():
        st.session_state["_auto_restore_last"].update(step="rebuilt_and_attached", final_attach=True)
        _log_attach("auto_attach_done", path="rebuild")
        return True

    st.session_state["_auto_restore_last"]["final_attach"] = False
    _log_attach("auto_attach_fail")
    return False

def _get_enabled_modes_unified() -> Dict[str, bool]:
    """
    관리자 설정 상태를 단일 맵으로 반환.
    반환 예: {"Grammar": True, "Sentence": True, "Passage": False}
    """
    ss = st.session_state
    # 신형(체크박스) 우선
    g = ss.get("cfg_show_mode_grammar",   ss.get("show_mode_grammar",   True))
    s = ss.get("cfg_show_mode_structure", ss.get("show_mode_structure", True))
    p = ss.get("cfg_show_mode_passage",   ss.get("show_mode_passage",   True))
    # 리스트 기반 설정이 있으면 덮어쓰기
    lst = ss.get("qa_modes_enabled")
    if isinstance(lst, list):
        g = ("문법설명" in lst)
        s = ("문장구조분석" in lst)
        p = ("지문분석" in lst)
    return {"Grammar": bool(g), "Sentence": bool(s), "Passage": bool(p)}
# ===== [03] END ===============================================================

# ===== [04] HEADER (비워둠: 타이틀/배지는 [07]에서 렌더) =====================
def render_header():
    """중복 렌더 방지용(과거 호환)."""
    return
# ===== [04] END ===============================================================

# ===== [04A] ADMIN BUTTONS (외부 모듈 호출) ==================================
from src.ui_admin import (
    ensure_admin_session_keys,
    render_admin_controls,
    render_role_caption,
)

ensure_admin_session_keys()
render_admin_controls()
render_role_caption()
st.divider()
# ===== [04A] END ==============================================================

# ===== [04B] 관리자 전역 토글 바 =============================================
def render_admin_toolbar():
    """관리자용 글로벌 도구 막대: 모든 패널 일괄 펼치기/접기 토글 제공"""
    # 관리자 가드
    if not (
        st.session_state.get("is_admin")
        or st.session_state.get("admin_mode")
        or st.session_state.get("role") == "admin"
        or st.session_state.get("mode") == "admin"
    ):
        return

    # ✅ 위젯 키는 위젯이 관리하도록: 최초 1회만 초기값 세팅(직접 대입 최소화)
    if "_admin_expand_all" not in st.session_state:
        st.session_state["_admin_expand_all"] = True  # 기본: 펼침

    st.markdown("### 관리자 도구")
    # ✅ 반환값을 세션에 다시 대입하지 않음 / value 파라미터도 생략
    st.toggle(
        "📂 관리자 패널 모두 펼치기",
        key="_admin_expand_all",
        help="켜면 아래 관리자용 패널들이 모두 펼쳐져 보입니다. 끄면 모두 접힙니다."
    )

# 전역 토글 바 렌더(관리자에게만 보임)
render_admin_toolbar()
# ===== [04B] END ==============================================================

# ===== [04C] 프롬프트 소스/드라이브 진단 패널(간단, 서비스계정 전용) — START
import importlib
import json
import os
import textwrap
import streamlit as st

def _mask(s: str | None, head: int = 6, tail: int = 4) -> str:
    if not s:
        return "—"
    if len(s) <= head + tail:
        return s
    return f"{s[:head]}…{s[-tail:]}"

with st.expander("🔧 프롬프트/드라이브 진단(간단)", expanded=False):
    st.caption("서비스 계정 기반의 Drive 연결 및 prompts.yaml 동기화를 점검합니다.")

    # 1) 폴더/설정 정보 (ID는 합의된 키 사용)
    folder_id = (
        os.getenv("GDRIVE_PREPARED_FOLDER_ID", "").strip()
        or str(st.secrets.get("GDRIVE_PREPARED_FOLDER_ID", "")).strip()
        or "prepared"
    )
    sa_blob = st.secrets.get("gcp_service_account")
    sa_info = None
    if isinstance(sa_blob, str):
        try: sa_info = json.loads(sa_blob)
        except Exception: sa_info = None
    elif isinstance(sa_blob, dict):
        sa_info = dict(sa_blob)

    st.write("• Drive 폴더 ID:", _mask(folder_id))
    st.write("• 서비스 계정 설정:", "✅ 있음" if sa_info else "❌ 없음")
    st.write("• OAuth 토큰 설정:", "— (사용 안 함)")

    # 2) Drive 연결 및 서비스계정 메일 확인
    drive_ok, drive_email, drive_err = False, None, None
    if sa_info:
        try:
            from google.oauth2 import service_account as _sa
            from googleapiclient.discovery import build as _build
            scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.metadata.readonly"]
            creds = _sa.Credentials.from_service_account_info(sa_info, scopes=scopes)
            svc = _build("drive", "v3", credentials=creds)
            about = svc.about().get(fields="user").execute()
            drive_email = (about or {}).get("user", {}).get("emailAddress")
            drive_ok = True
        except Exception as e:
            drive_err = f"{type(e).__name__}: {e}"
    else:
        drive_err = "gcp_service_account 비어있음"

    st.write("• Drive 연결:", "✅ 연결됨" if drive_ok else "❌ 없음")
    if drive_email:
        st.write("• 연결 계정:", f"`{drive_email}`")
    if drive_err and not drive_ok:
        st.warning(f"Drive 연결 실패: {drive_err}")

    # 3) prompts.yaml 동기화
    colA, colB = st.columns(2)
    with colA:
        if st.button("prompts.yaml 동기화 재시도"):
            try:
                mod = importlib.import_module("src.prompts_loader")
                do_sync = getattr(mod, "sync_prompts_from_drive", None)
                if callable(do_sync):
                    ok, detail = do_sync(folder_id=str(folder_id))
                    st.success("동기화 완료" if ok else f"동기화 결과: {detail}")
                else:
                    st.warning("동기화 함수가 모듈에 없습니다: src.prompts_loader.sync_prompts_from_drive")
            except Exception as e:
                st.error(f"동기화 중 예외: {type(e).__name__}: {e}")
    with colB:
        if st.button("Drive 연결 재점검"):
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()
# ===== [04C] 프롬프트 소스/드라이브 진단 패널(간단) — END


# ===== [04D] 인덱스 스냅샷/전체 재빌드/롤백 — 유틸리티 (세션/ENV/멀티루트) == START
import os, io, json, time, shutil, hashlib, importlib
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Callable, Iterable, List

INDEX_ROOT = Path(os.environ.get("MAIC_INDEX_ROOT", "~/.maic/persist")).expanduser()
SNAP_ROOT  = INDEX_ROOT / "indexes"
CUR_LINK   = SNAP_ROOT / "current"
KEEP_N     = 5
REQ_FILES  = ["chunks.jsonl", "manifest.json"]

TEXT_EXTS = {".txt", ".md"}
PDF_EXTS  = {".pdf"}
DOCX_EXTS = {".docx", ".docs"}

def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def _ensure_dirs() -> None:
    SNAP_ROOT.mkdir(parents=True, exist_ok=True)

def _resolve_current_path() -> Optional[Path]:
    if CUR_LINK.exists() and CUR_LINK.is_symlink():
        return CUR_LINK.resolve()
    ptr = SNAP_ROOT / "current.path"
    if ptr.exists():
        p = Path(ptr.read_text(encoding="utf-8").strip())
        return p if p.exists() else None
    return None

def _atomic_point_to(new_dir: Path) -> None:
    _ensure_dirs()
    tmp = SNAP_ROOT / (".current_tmp_" + _now_ts())
    try:
        if tmp.exists():
            if tmp.is_symlink() or tmp.is_file(): tmp.unlink()
            elif tmp.is_dir(): shutil.rmtree(tmp)
        os.symlink(new_dir, tmp)
        if CUR_LINK.exists() or CUR_LINK.is_symlink():
            CUR_LINK.unlink()
        os.replace(tmp, CUR_LINK)
        (SNAP_ROOT / "current.path").write_text(str(new_dir), encoding="utf-8")
    except Exception:
        (SNAP_ROOT / "current.path").write_text(str(new_dir), encoding="utf-8")

def _list_snapshots() -> list[Path]:
    _ensure_dirs()
    items = [p for p in SNAP_ROOT.iterdir() if p.is_dir() and p.name.startswith("v_")]
    items.sort(reverse=True)
    return items

def _gc_old_snapshots(keep: int = KEEP_N) -> None:
    for p in _list_snapshots()[keep:]:
        try: shutil.rmtree(p)
        except Exception: pass

# ---------- 후보 루트: 세션 → ENV → 흔한 경로들 ----------
def _candidate_roots() -> List[Path]:
    roots: List[Path] = []

    # 1) Streamlit 세션 우선 (관리자 UI에서 설정)
    try:
        import streamlit as st  # 없으면 무시
        pd = st.session_state.get("prepared_dir")
        if pd:
            roots.append(Path(pd).expanduser())
    except Exception:
        pass

    # 2) 환경변수
    env_dir = os.environ.get("MAIC_PREPARED_DIR", "").strip()
    if env_dir:
        roots.append(Path(env_dir).expanduser())

    # 3) 흔한 후보 (프로젝트/컨테이너)
    roots += [
        Path("~/.maic/prepared").expanduser(),
        Path("./prepared").resolve(),
        Path("./knowledge").resolve(),
        Path("/mount/data/knowledge"),
        Path("/mount/data"),
        Path("/mnt/data/knowledge"),
        Path("/mnt/data"),
    ]

    # 존재하는 디렉토리만, 중복 제거
    seen = set()
    valid: List[Path] = []
    for p in roots:
        try:
            rp = p.resolve()
        except Exception:
            continue
        key = str(rp)
        if rp.exists() and rp.is_dir() and key not in seen:
            valid.append(rp)
            seen.add(key)
    return valid

def _healthcheck(stage_dir: Path, stats: Optional[dict]=None) -> Tuple[bool, str]:
    for name in REQ_FILES:
        f = stage_dir / name
        if not f.exists() or f.stat().st_size == 0:
            detail = ""
            if stats:
                detail = (
                    f" (roots={stats.get('roots', [])}, "
                    f"txt/md={stats.get('txt_md',0)}, pdf={stats.get('pdf',0)}, "
                    f"docx={stats.get('docx',0)}, extracted_chunks={stats.get('chunks',0)})"
                )
            return False, f"필수 산출물 누락/0바이트: {name}{detail}"
    try:
        with open(stage_dir / "chunks.jsonl", "r", encoding="utf-8") as fr:
            line = fr.readline()
            if not line.strip():
                return False, "chunks.jsonl 첫 레코드 없음"
            _ = json.loads(line)
    except Exception as e:
        return False, f"chunks.jsonl 파싱 실패: {e}"
    return True, "OK"

# ---------- 파일 스캐너/리더 ----------
def _iter_docs(roots: List[Path]) -> Iterable[Path]:
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file(): 
                continue
            ext = p.suffix.lower()
            if ext in (TEXT_EXTS | PDF_EXTS | DOCX_EXTS):
                yield p

def _read_text_file(p: Path, max_bytes: int = 4_000_000) -> str:
    try:
        with open(p, "rb") as fr:
            b = fr.read(max_bytes)
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def _read_pdf_file(p: Path, max_pages: int = 100) -> str:
    try:
        import PyPDF2
    except Exception:
        return ""
    try:
        parts = []
        with open(p, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            n = min(len(reader.pages), max_pages)
            for i in range(n):
                try:
                    parts.append(reader.pages[i].extract_text() or "")
                except Exception:
                    continue
        return "\n".join([t for t in parts if t]).strip()
    except Exception:
        return ""

def _read_docx_file(p: Path, max_paras: int = 500) -> str:
    try:
        import docx  # python-docx
    except Exception:
        return ""
    try:
        d = docx.Document(str(p))
        paras = []
        for i, para in enumerate(d.paragraphs):
            if i >= max_paras: break
            t = (para.text or "").strip()
            if t: paras.append(t)
        return "\n".join(paras).strip()
    except Exception:
        return ""

# ---------- 폴백 전체 빌더 ----------
def _fallback_build_full_index(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_path   = out_dir / "chunks.jsonl"
    manifest_path = out_dir / "manifest.json"

    roots = _candidate_roots()
    stats = {"roots":[str(r) for r in roots], "txt_md":0, "pdf":0, "docx":0, "chunks":0}
    items = []

    with open(chunks_path, "w", encoding="utf-8") as fw:
        idx = 0
        for p in _iter_docs(roots):
            ext = p.suffix.lower()
            text = ""
            if ext in TEXT_EXTS:
                text = _read_text_file(p)
                stats["txt_md"] += 1
            elif ext in PDF_EXTS:
                text = _read_pdf_file(p)
                stats["pdf"] += 1
            elif ext in DOCX_EXTS:
                text = _read_docx_file(p)
                stats["docx"] += 1

            if not (text and text.strip()):
                continue

            idx += 1
            rec = {
                "id": f"{p.stem}-{idx}",
                "source": str(p),
                "text": text,
                "meta": {
                    "mtime": int(p.stat().st_mtime),
                    "size": p.stat().st_size,
                    "ext": ext,
                }
            }
            fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
            items.append({"id": rec["id"], "source": rec["source"]})
            stats["chunks"] += 1

    # 결과 요약
    manifest = {
        "created_at": _now_ts(),
        "source_roots": stats["roots"],
        "count": len(items),
        "items": items[:2000],
        "generator": "fallback_builder_multi",
        "stats": stats,
    }
    with open(manifest_path, "w", encoding="utf-8") as fm:
        json.dump(manifest, fm, ensure_ascii=False, indent=2)

    return stats

# ---------- 외부 빌더 자동 탐색 ----------
def _try_import_full_builder() -> Tuple[Optional[Callable], str]:
    env_spec = os.environ.get("MAIC_INDEX_BUILDER", "").strip()
    if env_spec and ":" in env_spec:
        mod, fn = env_spec.split(":", 1)
        try:
            m = importlib.import_module(mod)
            f = getattr(m, fn, None)
            if callable(f):
                return f, f"[ENV] {mod}:{fn}"
        except Exception:
            pass

    candidates = [
        ("src.rag.index_build", "build_full_index"),
        ("src.rag.index_build", "build_index"),
        ("rag.index_build",     "build_full_index"),
        ("rag.index_build",     "build_index"),
        ("src.index_build",     "build_full_index"),
        ("src.index_build",     "build_index"),
        ("index_build",         "build_full_index"),
        ("index_build",         "build_index"),
        ("MAIC.index_build",    "build_full_index"),
        ("MAIC.index_build",    "build_index"),
    ]
    for mod, attr in candidates:
        try:
            m = importlib.import_module(mod)
            f = getattr(m, attr, None)
            if callable(f):
                return f, f"[AUTO] {mod}:{attr}"
        except Exception:
            continue

    return None, "fallback"

# ---------- 퍼블릭 API ----------
def full_rebuild_safe(progress=None, on_drive_upload=None) -> Tuple[bool, str, Optional[Path]]:
    _ensure_dirs()
    builder, where = _try_import_full_builder()

    ts = _now_ts()
    stage = SNAP_ROOT / f"v_{ts}"
    stage.mkdir(parents=True, exist_ok=False)

    if progress: progress(10, text=f"전체 인덱스 빌드 시작… ({'외부' if builder else '폴백'})")
    stats = None
    try:
        if builder:
            try:
                builder(out_dir=str(stage))
            except TypeError:
                builder()
        else:
            stats = _fallback_build_full_index(stage)
    except Exception as e:
        return False, f"빌드 함수 실행 실패: {e}", stage

    if progress: progress(65, text="헬스체크 수행…")
    ok, msg = _healthcheck(stage, stats=stats or {})
    if not ok:
        return False, msg, stage

    if progress: progress(80, text="원자적 커밋(스왑)…")
    _atomic_point_to(stage)
    _gc_old_snapshots(keep=KEEP_N)

    if on_drive_upload:
        if progress: progress(90, text="Drive 백업 업로드…")
        try:
            on_drive_upload(stage)
        except Exception as e:
            return True, f"커밋 성공 / Drive 업로드 실패: {e}", stage

    if progress: progress(100, text="완료")
    return True, "전체 인덱스 재빌드 커밋 완료", stage

def incremental_rebuild_minimal(progress=None) -> Tuple[bool, str]:
    try:
        from src.rag.index_build import rebuild_incremental_minimal
    except Exception as e:
        return False, f"증분 빌더(rebuild_incremental_minimal) 미탑재: {e}", 
    if progress: progress(20, text="신규 파일 감지…")
    n = rebuild_incremental_minimal()
    if progress: progress(100, text=f"증분 완료: {n}개 반영")
    return True, f"증분 반영: {n}개 파일", 

def rollback_to(snapshot_dir: Path) -> Tuple[bool, str]:
    if not snapshot_dir.exists():
        return False, "스냅샷 경로가 존재하지 않습니다"
    ok, msg = _healthcheck(snapshot_dir)
    if not ok:
        return False, f"스냅샷 헬스체크 실패: {msg}"
    _atomic_point_to(snapshot_dir)
    return True, f"롤백 완료: {snapshot_dir.name}"
# ===== [04D] 인덱스 스냅샷/전체 재빌드/롤백 — 유틸리티 (세션/ENV/멀티루트) === END

# ===== [04E] 부팅 훅: Drive → prepared 동기화 + 자동 전체 인덱스 ========= START
import time

def _get_drive_prepared_folder_id() -> str | None:
    """secrets 또는 환경변수에서 Drive prepared 폴더 ID를 얻는다."""
    fid = os.environ.get("GDRIVE_PREPARED_FOLDER_ID", "").strip()
    if fid:
        return fid
    try:
        import streamlit as st
        fid = str(st.secrets.get("GDRIVE_PREPARED_FOLDER_ID", "")).strip()
        if fid:
            return fid
    except Exception:
        pass
    # 프로젝트에서 지정하신 기본값(메모리에 기록해둔 ID)
    fallback = "1bltOvqYsifPtmcx-epwJTq-hYAklNp2j".strip()
    return fallback or None

def _drive_sync_to_local_prepared(dest_dir: str | Path, folder_id: str, logger=None) -> bool:
    """
    Drive의 prepared 폴더(ID) → 로컬 dest_dir 로 동기화.
    - src.drive_sync.download_folder_by_id(stage_dir, folder_id) 가 있으면 사용
    - 없으면 조용히 skip (False 반환)
    """
    dest = Path(dest_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        import importlib
        m = importlib.import_module("src.drive_sync")
        fn = getattr(m, "download_folder_by_id", None)
        if callable(fn):
            if logger: logger(f"Drive 동기화 시작: folder_id={folder_id} → {dest}")
            fn(folder_id=folder_id, local_dir=str(dest))
            if logger: logger("Drive 동기화 완료")
            return True
    except Exception as e:
        if logger: logger(f"Drive 동기화 모듈 사용 불가: {e}")
    return False

def _auto_bootstrap_prepared_and_index(max_retries: int = 3, sleep_sec: float = 2.0):
    """
    앱 시작 시 한 번만:
      1) Drive prepared 동기화(가능하면)
      2) prepared 후보 루트 재검출
      3) 전체 인덱스(안전 커밋) 자동 실행
    - 세션 플래그로 중복 실행 방지
    """
    # Streamlit 세션 유무에 상관 없이, 환경변수 플래그로 켜고 끌 수 있음(기본: on)
    auto_on = os.environ.get("MAIC_AUTO_INDEX_ON_START", "1").strip() not in ("0", "false", "False")
    if not auto_on:
        return

    # 세션 플래그: 한 세션에서 한 번만
    try:
        import streamlit as st
        if st.session_state.get("_auto_bootstrap_done"):
            return
    except Exception:
        pass

    logs: list[str] = []
    def log(msg: str): logs.append(msg)

    # 0) Drive → 로컬 동기화 시도 (있으면 사용)
    folder_id = _get_drive_prepared_folder_id()
    # 동기화 목적지: 세션 지정 > ENV > 기본(~/.maic/prepared)
    preferred = None
    try:
        import streamlit as st
        preferred = st.session_state.get("prepared_dir")
    except Exception:
        pass
    dest_dir = preferred or os.environ.get("MAIC_PREPARED_DIR", "~/.maic/prepared")
    if folder_id:
        _ = _drive_sync_to_local_prepared(dest_dir=dest_dir, folder_id=folder_id, logger=log)

    # 1) 재시도 루프: 루트 후보가 잡힐 때까지 N회
    ok = False
    stage = None
# >>>>> START [A03] boot_full_index_loop (Drive-first 빌드 고정)
    for i in range(max_retries):
        # 전체 인덱스(Drive-first) 시도
        log(f"[부팅 훅] 전체 인덱스 시도 {i+1}/{max_retries} (Drive-first)")
        try:
            from pathlib import Path as _P
            from src.config import PERSIST_DIR as _PD
            from src.rag.index_build import build_index_with_checkpoint as _build

            persist_dir = str(_P(_PD))
            _build(
                update_pct=lambda *_a, **_k: None,
                update_msg=lambda *_a, **_k: None,
                gdrive_folder_id=(folder_id or ""),
                gcp_creds={},
                persist_dir=persist_dir,
                remote_manifest={},
            )
            ok = True
            stage = _P(persist_dir)
            log("Drive-first 빌드 성공")
            break
        except TypeError:
            try:
                _build()  # 레거시 서명 대비
                ok = True; stage = _P(persist_dir)
                log("Drive-first 빌드(레거시) 성공")
                break
            except Exception as e:
                log(f"레거시 빌드 실패: {type(e).__name__}: {e}")
        except Exception as e:
            log(f"빌드 실패: {type(e).__name__}: {e}")
        time.sleep(sleep_sec)
# <<<<< END [A03] boot_full_index_loop

# ===== [04E] 부팅 훅: Drive → prepared 동기화 + 자동 전체 인덱스 ========= END
# ===== [04F] 사전점검 래퍼(config 기준) =======================================
# >>>>> START [04F] precheck_build_needed
def precheck_build_needed() -> bool:
    """
    Drive-first 체계에서의 간단/신뢰성 높은 사전점검:
      - PERSIST_DIR/chunks.jsonl 존재 + 크기 > 0  (핵심 산출물)
      - MANIFEST_PATH 존재                          (인덱스 메타)
      - QUALITY_REPORT_PATH 존재 여부는 참고만     (없어도 재빌드 권장 X)

    반환값: True  → 재빌드 권장
            False → 양호
    """
    try:
        from pathlib import Path
        # config 기준 경로만 사용 (레거시 .maic 하드코딩 금지)
        from src.config import PERSIST_DIR as _PD, MANIFEST_PATH as _MF, QUALITY_REPORT_PATH as _QR

        persist_dir = Path(_PD)
        chunks_path = persist_dir / "chunks.jsonl"
        manifest_ok = Path(_MF).exists()

        chunks_ok = chunks_path.exists()
        try:
            if chunks_ok and chunks_path.stat().st_size <= 0:
                chunks_ok = False
        except Exception:
            chunks_ok = False

        # 품질 리포트는 보조 지표(없다고 바로 권장 X)
        qr_exists = False
        try:
            qr_exists = Path(_QR).exists()
        except Exception:
            qr_exists = False

        # 핵심 기준: chunks_ok & manifest_ok
        if not chunks_ok:
            return True
        if not manifest_ok:
            return True

        # 품질 리포트가 없으면 경고 수준이지만, 운영 편의상 False(양호)로 보고
        # 패널에서만 "없음" 배지만 표기하게 둡니다.
        return False
    except Exception:
        # 예외 시 보수적으로 재빌드 권장
        return True
# <<<<< END [04F] precheck_build_needed
# ===== [04F] END =============================================================

# ===== [05A] 자료 최적화/백업 패널 ==========================================
# >>>>> START [05A] 자료 최적화/백업 패널
def render_brain_prep_main():
    """
    인덱스(두뇌) 최적화/복구/백업 관리자 패널
    - 경로 표기/검사를 config 기반으로 '강제' 고정 (레거시 폴백 제거)
    - 재빌드 버튼은 Drive-first 빌더(build_index_with_checkpoint)를 폴더 ID와 함께 직접 호출
    - 모든 동작은 [05B] 타임라인 로그(_log_attach)와 연계
    """
    import os
    import json
    from pathlib import Path

    # 관리자 가드
    if not (
        st.session_state.get("is_admin")
        or st.session_state.get("admin_mode")
        or st.session_state.get("role") == "admin"
        or st.session_state.get("mode") == "admin"
    ):
        return

    # 🔽 전역 토글 상태 반영
    _expand_all = bool(st.session_state.get("_admin_expand_all", True))

    def _log(step: str, **kw):
        try:
            if "_log_attach" in globals() and callable(globals()["_log_attach"]):
                globals()["_log_attach"](step, **kw)
        except Exception:
            pass

    # === 경로: src.config 기준으로 '무조건' 고정 (폴백/재할당 금지) ===
    from src.config import (
        PERSIST_DIR as CFG_PERSIST_DIR,
        QUALITY_REPORT_PATH as CFG_QUALITY_REPORT_PATH,
        APP_DATA_DIR as CFG_APP_DATA_DIR,
    )
    PERSIST_DIR = Path(CFG_PERSIST_DIR)
    QUALITY_REPORT_PATH = Path(CFG_QUALITY_REPORT_PATH)
    BACKUP_DIR = (Path(CFG_APP_DATA_DIR) / "backup").resolve()

    # 관련 함수 핸들
    precheck_fn   = globals().get("precheck_build_needed") or globals().get("quick_precheck")
    build_fn      = globals().get("build_index_with_checkpoint")   # ✅ Drive-first 엔트리
    restore_fn    = globals().get("restore_latest_backup_to_local")
    backup_fn     = globals().get("_make_and_upload_backup_zip")
    attach_fn     = globals().get("_attach_from_local")
    auto_restore  = globals().get("_auto_attach_or_restore_silently")
    force_persist = globals().get("_force_persist_dir")

    # Drive prepared 폴더 ID 취득(시크릿 → ENV → 기본값)
    def _prepared_folder_id() -> str:
        fid = os.environ.get("GDRIVE_PREPARED_FOLDER_ID", "").strip()
        if not fid:
            try:
                fid = str(st.secrets.get("GDRIVE_PREPARED_FOLDER_ID", "")).strip()
            except Exception:
                fid = ""
        if not fid:
            # 프로젝트 합의 기본값(고정): prepared 폴더 ID
            fid = "1bltOvqYsifPtmcx-epwJTq-hYAklNp2j"
        return fid

    with st.expander("🧩 자료 최적화 · 백업(관리자)", expanded=_expand_all):
        st.subheader("자료 최적화 · 백업", anchor=False)

        # 경로/상태 요약 (config 기반)
        with st.container(border=True):
            st.markdown("### 경로 및 상태")
            st.write("• Persist 디렉터리:", f"`{PERSIST_DIR}`")
            st.write("• Backup 디렉터리:", f"`{BACKUP_DIR}`")
            qr_exists = Path(QUALITY_REPORT_PATH).exists()
            st.markdown(
                f"• 품질 리포트(quality_report.json): {'✅ 있음' if qr_exists else '❌ 없음'} "
                f"(`{QUALITY_REPORT_PATH}`)"
            )

            if callable(precheck_fn):
                try:
                    need = precheck_fn()  # bool 예상
                    badge = "🟡 재빌드 권장" if need else "🟢 양호"
                    st.write("• 사전점검 결과:", badge)
                except Exception as e:
                    st.write("• 사전점검 결과: ⚠ 오류", f"(`{type(e).__name__}: {e}`)")
            else:
                st.caption("사전점검 함수가 없어 건너뜁니다(선택 기능).")

        # 액션 버튼들
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

        # 1) 두뇌 연결(강제)
        with col1:
            if st.button("🧠 두뇌 연결(강제)", use_container_width=True):
                with st.status("강제 연결 중…", state="running") as s:
                    try:
                        if callable(force_persist):
                            force_persist()
                        ok = False
                        if callable(attach_fn):
                            _log("manual_local_attach_try")
                            ok = bool(attach_fn())
                        if not ok and callable(auto_restore):
                            _log("manual_auto_restore_try")
                            ok = bool(auto_restore())
                        if ok:
                            s.update(label="연결 완료", state="complete")
                            st.success("세션에 두뇌가 연결되었습니다.")
                            _log("manual_attach_done", ok=True)
                        else:
                            s.update(label="연결 실패", state="error")
                            st.error("두뇌 연결에 실패했습니다.")
                            _log("manual_attach_fail", ok=False)
                    except Exception as e:
                        s.update(label="연결 중 예외", state="error")
                        st.error(f"연결 중 오류: {type(e).__name__}: {e}")
                        _log("manual_attach_exception", error=f"{type(e).__name__}: {e}")

        # 2) 최신 백업 복원
        with col2:
            if st.button("⬇ 최신 백업 복원", use_container_width=True, disabled=not callable(restore_fn)):
                with st.status("최신 백업 복원 중…", state="running") as s:
                    try:
                        if not callable(restore_fn):
                            s.update(label="복원 기능 없음", state="error")
                            st.error("restore_latest_backup_to_local 함수가 없습니다.")
                            _log("restore_latest_backup_missing")
                        else:
                            r = restore_fn() or {}
                            ok = bool(r.get("ok"))
                            _log("drive_restore_result", ok=ok)
                            if ok and callable(attach_fn):
                                if callable(force_persist):
                                    force_persist()
                                _log("local_attach_try")
                                ok = bool(attach_fn())
                                if ok:
                                    _log("local_attach_ok")
                            if ok:
                                s.update(label="복원 및 연결 완료", state="complete")
                                st.success("최신 백업 복원 완료(연결됨).")
                            else:
                                s.update(label="복원 실패", state="error")
                                st.error("백업 복원에 실패했습니다.")
                    except Exception as e:
                        s.update(label="복원 중 예외", state="error")
                        st.error(f"복원 중 오류: {type(e).__name__}: {e}")
                        _log("drive_restore_exception", error=f"{type(e).__name__}: {e}")

        # 3) 인덱스 재빌드(Drive-first)
        with col3:
            if st.button("♻ 인덱스 재빌드(Drive 우선)", use_container_width=True, disabled=not callable(build_fn)):
                with st.status("인덱스 재빌드 중…", state="running") as s:
                    try:
                        if not callable(build_fn):
                            s.update(label="빌더 없음", state="error")
                            st.error("build_index_with_checkpoint 함수가 없습니다.")
                            _log("rebuild_skip", reason="build_fn_not_callable")
                        else:
                            folder_id = _prepared_folder_id()
                            persist_dir = str(PERSIST_DIR)

                            _log("rebuild_try", persist_dir=persist_dir, folder_id=folder_id)
                            try:
                                build_fn(
                                    update_pct=lambda *_a, **_k: None,
                                    update_msg=lambda *_a, **_k: None,
                                    gdrive_folder_id=folder_id,
                                    gcp_creds={},                  # 모듈 내부에서 secrets 사용 가능
                                    persist_dir=persist_dir,
                                    remote_manifest={},            # 우선 빈 dict
                                )
                            except TypeError:
                                # 서명 차이가 있는 레거시용
                                build_fn()

                            _log("rebuild_ok")
                            ok_attach = False
                            if callable(force_persist):
                                force_persist()
                            if callable(attach_fn):
                                _log("local_attach_try")
                                ok_attach = bool(attach_fn())
                                if ok_attach:
                                    _log("local_attach_ok")

                            s.update(label="재빌드 완료", state="complete")
                            st.success("인덱스 재빌드가 완료되었습니다.")
                    except Exception as e:
                        s.update(label="재빌드 실패", state="error")
                        st.error(f"재빌드 실패: {type(e).__name__}: {e}")
                        _log("rebuild_fail", error=f"{type(e).__name__}: {e}")

        # 4) 백업 만들기/업로드
        with col4:
            if st.button("⬆ 백업 만들기/업로드", use_container_width=True, disabled=not callable(backup_fn)):
                with st.status("백업 생성/업로드 중…", state="running") as s:
                    try:
                        if not callable(backup_fn):
                            s.update(label="백업기 없음", state="error")
                            st.error("백업 생성 함수가 없습니다.")
                            _log("backup_skip", reason="backup_fn_not_callable")
                        else:
                            r = backup_fn() or {}
                            ok = bool(r.get("ok", False))
                            _log("backup_result", ok=ok)
                            if ok:
                                s.update(label="백업 완료", state="complete")
                                st.success("백업 생성/업로드가 완료되었습니다.")
                            else:
                                s.update(label="백업 실패", state="error")
                                st.error(f"백업 실패: {json.dumps(r, ensure_ascii=False)}")
                    except Exception as e:
                        s.update(label="백업 중 예외", state="error")
                        st.error(f"백업 중 오류: {type(e).__name__}: {e}")
                        _log("backup_exception", error=f"{type(e).__name__}: {e}")
# <<<<< END [05A] 자료 최적화/백업 패널
# ===== [05A] END =============================================================


# ===== [05B] 간단 진단 패널(전역 토글 연동) ==================================
# >>>>> START [05B] 간단 진단 패널
def render_tag_diagnostics():
    """
    한 화면에서 모든 진단 확인:
    - BOOT-WARN 경고
    - 임포트 오류(_import_errors)
    - Attach/Restore 타임라인 (+복사/다운로드)
    - 자동 복구 상태 스냅샷
    - rag_index Persist 경로/품질 리포트 존재 여부
    (모든 섹션 expander가 전역 토글 `_admin_expand_all`과 연동됨)
    """
    import importlib, json as _json
    from datetime import datetime
    from pathlib import Path

    # 전역 토글 상태
    _expand_all = bool(st.session_state.get("_admin_expand_all", True))

    # === 경로: config 기준으로 통일 ===
    try:
        from src.config import (
            PERSIST_DIR as CFG_PERSIST_DIR,
            QUALITY_REPORT_PATH as CFG_QUALITY_REPORT_PATH,
            MANIFEST_PATH as CFG_MANIFEST_PATH,
            APP_DATA_DIR as CFG_APP_DATA_DIR,
        )
        PERSIST_DIR = Path(CFG_PERSIST_DIR)
        QUALITY_REPORT_PATH = Path(CFG_QUALITY_REPORT_PATH)
        MANIFEST_PATH = Path(CFG_MANIFEST_PATH)
        BACKUP_DIR = (Path(CFG_APP_DATA_DIR) / "backup").resolve()
    except Exception:
        # 최후 폴백(레거시) — 정상 환경에서는 도달하지 않아야 함
        base = Path.home() / ".maic"
        PERSIST_DIR = (base / "persist").resolve()
        QUALITY_REPORT_PATH = (base / "quality_report.json").resolve()
        MANIFEST_PATH = (base / "manifest.json").resolve()
        BACKUP_DIR = (base / "backup").resolve()

    # 수집 데이터
    boot_warns = globals().get("_BOOT_WARNINGS") or []
    import_errs = globals().get("_import_errors") or []
    logs = st.session_state.get("_attach_log") or []
    auto_info = st.session_state.get("_auto_restore_last")

    with st.expander("🧪 간단 진단(관리자)", expanded=_expand_all):
        st.subheader("진단 요약", anchor=False)

        # A) BOOT-WARN
        with st.expander("부팅 경고(BOOT-WARN)", expanded=_expand_all):
            if not boot_warns:
                st.caption("부팅 경고 없음.")
            else:
                for i, msg in enumerate(boot_warns, 1):
                    with st.expander(f"경고 {i}", expanded=(True if _expand_all else (i == 1))):
                        st.markdown(msg)

        # B) 임포트 오류
        with st.expander("임포트 오류(Import Errors)", expanded=_expand_all):
            if not import_errs:
                st.caption("임포트 오류 없음.")
            else:
                for i, rec in enumerate(import_errs, 1):
                    st.code(str(rec), language="text")

        # C) Attach/Restore 타임라인
        with st.expander("Attach/Restore 타임라인", expanded=_expand_all):
            if not logs:
                st.caption("타임라인 없음.")
            else:
                for rec in logs[-200:]:
                    st.write(f"- {rec}")

        # D) 자동 복구 상태
        with st.expander("자동 복구 상태 스냅샷", expanded=_expand_all):
            st.json(auto_info or {"info": "no auto-restore snapshot"})

        # E) 경로/파일 상태 (config 기준)
        with st.expander("경로/파일 상태", expanded=_expand_all):
            st.write("• Persist 디렉터리:", f"`{PERSIST_DIR}`")
            st.write("• Backup 디렉터리:", f"`{BACKUP_DIR}`")
            st.write("• Manifest 경로:", f"`{MANIFEST_PATH}`")
            st.write("• 품질 리포트:", f"`{QUALITY_REPORT_PATH}`")

            # 핵심 산출물 존재/크기 확인
            chunks = PERSIST_DIR / "chunks.jsonl"
            qr_ok = QUALITY_REPORT_PATH.exists()
            mf_ok = MANIFEST_PATH.exists()
            ch_ok = chunks.exists() and chunks.stat().st_size > 0

            st.markdown(f"• chunks.jsonl: {'✅' if ch_ok else '❌'} ({chunks})")
            st.markdown(f"• quality_report.json: {'✅' if qr_ok else '❌'} ({QUALITY_REPORT_PATH})")
            st.markdown(f"• manifest.json: {'✅' if mf_ok else '❌'} ({MANIFEST_PATH})")

            # 빠른 원본 열람(있을 때만)
            if qr_ok:
                try:
                    with open(QUALITY_REPORT_PATH, "r", encoding="utf-8") as f:
                        data = _json.load(f)
                    st.caption("quality_report.json (요약)")
                    st.json(data if isinstance(data, dict) else {"value": data})
                except Exception as e:
                    st.warning(f"품질 리포트 열람 실패: {type(e).__name__}: {e}")

# <<<<< END [05B] 간단 진단 패널
# ===== [05B] END =============================================================


# ===== [05C] 인덱스 관리(레거시) ==========================================
# >>>>> START [05C] 인덱스 관리(레거시)
def render_legacy_index_panel():
    """
    [레거시 UI] 최소/전체/롤백 인덱스 관리 패널.
    현재 앱은 [05A] '자료 최적화·백업' 패널을 표준으로 사용합니다.
    기본은 비표시하며, 환경변수 SHOW_LEGACY_INDEX_PANEL=1 일 때만 노출합니다.
    """
    import os
    show = os.environ.get("SHOW_LEGACY_INDEX_PANEL", "0").lower() in ("1", "true", "yes", "on")
    if not show:
        # 기본은 숨김
        return

    # 필요 시 임시로 과거 UI를 다시 보고자 할 때만 아래에 기존 구현을 재삽입하세요.
    # (의도적으로 빈 본문; 운영 중에는 사용하지 않습니다.)
    st.info("레거시 인덱스 패널은 기본 숨김입니다. SHOW_LEGACY_INDEX_PANEL=1 로 일시 활성화 가능합니다.")
# <<<<< END [05C] 인덱스 관리(레거시)
# ===== [05C] END =============================================================


# ===== [05D] 자료 폴더 설정(관리자) ========================================= START
def render_prepared_dir_admin():
    import streamlit as st
    from pathlib import Path

    if not (
        st.session_state.get("is_admin")
        or st.session_state.get("admin_mode")
        or st.session_state.get("role") == "admin"
        or st.session_state.get("mode") == "admin"
    ):
        return

    with st.expander("📂 자료 폴더 설정 (prepared dir)", expanded=True):
        cur_env = os.environ.get("MAIC_PREPARED_DIR", "")
        cur_ss  = st.session_state.get("prepared_dir", "")
        st.write("현재 환경변수:", cur_env or "(미설정)")
        st.write("현재 세션:", cur_ss or "(미설정)")

        new_dir = st.text_input("자료 폴더 절대경로 입력", value=cur_ss or cur_env, placeholder="/absolute/path/to/knowledge or prepared")

        colA, colB = st.columns([1,1])
        with colA:
            if st.button("경로 테스트"):
                p = Path(new_dir).expanduser()
                if p.exists() and p.is_dir():
                    cnt = sum(1 for _ in p.rglob("*") if _.is_file())
                    st.success(f"OK: {p} (파일 {cnt}개)")
                else:
                    st.error(f"경로가 폴더로 존재하지 않습니다: {p}")

        with colB:
            if st.button("이 경로 사용(세션+ENV 반영)"):
                p = Path(new_dir).expanduser()
                if p.exists() and p.is_dir():
                    st.session_state["prepared_dir"] = str(p)
                    os.environ["MAIC_PREPARED_DIR"]   = str(p)
                    st.success(f"적용 완료: {p}")
                else:
                    st.error("적용 실패: 유효한 폴더 경로가 아닙니다.")

# 즉시 렌더(관리자 전용)
render_prepared_dir_admin()
# ===== [05D] 자료 폴더 설정(관리자) =========================================== END

# ===== [05E] 시작 시 자동 인덱스 상태/토글 ================================= START
def render_auto_index_admin():
    import streamlit as st
    with st.expander("⚙️ 시작 시 자동 인덱스 설정", expanded=False):
        cur = os.environ.get("MAIC_AUTO_INDEX_ON_START", "1")
        on = cur not in ("0", "false", "False")
        st.write("현재 상태:", "**ON**" if on else "**OFF**")
        new = st.toggle("앱 시작 시 자동으로 Drive 동기화 + 전체 인덱스", value=on)
        if new != on:
            os.environ["MAIC_AUTO_INDEX_ON_START"] = "1" if new else "0"
            st.success("변경 적용 (다음 실행부터 반영)")

        logs = st.session_state.get("_auto_bootstrap_logs", [])
        if logs:
            st.caption("최근 부팅 훅 로그")
            for ln in logs:
                st.text("- " + ln)
        stage = st.session_state.get("_auto_bootstrap_stage", "")
        if stage:
            st.caption(f"마지막 자동 인덱스 스냅샷: {stage}")

# 관리자만 표시
try:
    import streamlit as st
    if st.session_state.get("is_admin") or st.session_state.get("admin_mode") or st.session_state.get("role")=="admin" or st.session_state.get("mode")=="admin":
        render_auto_index_admin()
except Exception:
    pass
# ===== [05E] 시작 시 자동 인덱스 상태/토글 =================================== END

# ===== [05] 두뇌 준비 상태 헬퍼(RAG readiness) — START =======================
def _is_brain_ready() -> bool:
    """
    인덱스/퍼시스트가 준비되었는지 판별.
    - 우선순위 경로: env PERSIST_DIR → st.secrets['PERSIST_DIR'] → ~/.maic/persist
    - 아래 마커 파일이 하나라도 있으면 준비 완료로 간주:
        manifest.json / manifest.yaml / manifest.yml / manifest.pkl
        chroma.sqlite / faiss.index / index.faiss / index.bin
        docstore.json / vector.index / collections.parquet 등
    - 마커가 없어도, persist 폴더 하위에 10KB 이상 파일이 하나라도 있으면 True
    - 실패 시 False (그리고 에러 로그에 기록)
    """
    import os, pathlib
    try:
        persist_dir = (
            os.getenv("PERSIST_DIR")
            or getattr(st, "secrets", {}).get("PERSIST_DIR")
            or os.path.expanduser("~/.maic/persist")
        )
        p = pathlib.Path(persist_dir)
        if not p.exists():
            return False

        markers = [
            "manifest.json","manifest.yaml","manifest.yml","manifest.pkl",
            "chroma.sqlite","faiss.index","index.faiss","index.bin",
            "docstore.json","vector.index","collections.parquet","collection.parquet"
        ]
        for m in markers:
            if (p / m).exists():
                return True

        # 용량 기반 휴리스틱(10KB 이상 파일이 하나라도 있으면 준비됨으로 간주)
        for q in p.rglob("*"):
            try:
                if q.is_file() and q.stat().st_size > 10 * 1024:
                    return True
            except Exception:
                continue

        return False

    except Exception as e:
        try:
            _errlog(f"두뇌 상태 확인 실패: {e}", where="[05]_is_brain_ready", exc=e)  # [00B]가 있으면 기록
        except Exception:
            pass
        return False
# ===== [05] 두뇌 준비 상태 헬퍼(RAG readiness) — END =========================

# ===== [05F] LLM STREAM CALL HELPERS — START ================================
# OpenAI/Gemini 스트리밍 호출 헬퍼
# - 규약: (ok: bool, text_or_msg: Optional[str], provider: str) 튜플 반환
# - 원칙: 빈 응답/예외/타임아웃은 반드시 ok=False (폴백 유도)
# - on_delta(str) 콜백을 넘기면 스트리밍 중간 텍스트를 점진 반영할 수 있음

from typing import Optional, Callable, List, Dict, Tuple
import os, time

def _normalize_messages(parts_or_messages) -> List[Dict[str, str]]:
    """
    다양한 입력(parts dict, messages list, 단일 str)을 OpenAI 호환 messages로 정규화.
    허용 예:
      - [{"role":"system","content":"..."}, {"role":"user","content":"..."}]
      - {"system":"...", "user":"..."}  # prompts.yaml 전개 등
      - "one-shot user prompt"
    """
    if parts_or_messages is None:
        return [{"role": "user", "content": ""}]
    # messages(list[dict]) 형태
    if isinstance(parts_or_messages, list):
        msgs = []
        for m in parts_or_messages:
            if isinstance(m, dict) and "role" in m and "content" in m:
                msgs.append({"role": m["role"], "content": str(m["content"])})
        if msgs:
            return msgs
    # dict(parts) 형태
    if isinstance(parts_or_messages, dict):
        sys = str(parts_or_messages.get("system", "")).strip()
        usr = str(parts_or_messages.get("user", "")).strip()
        msgs: List[Dict[str, str]] = []
        if sys:
            msgs.append({"role": "system", "content": sys})
        msgs.append({"role": "user", "content": usr})
        return msgs
    # 단일 문자열
    return [{"role": "user", "content": str(parts_or_messages)}]


def _call_openai_stream(
    parts_or_messages,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    on_delta: Optional[Callable[[str], None]] = None,
    timeout_s: int = 60,
) -> Tuple[bool, Optional[str], str]:
    """
    OpenAI ChatCompletion 스트리밍 호출.
    - 반환: (ok, out_or_msg, "OpenAI")
    - 빈 응답/예외/타임아웃은 ok=False
    """
    messages = _normalize_messages(parts_or_messages)

    # 키 취득: st.secrets 우선 → ENV 폴백
    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        pass
    api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        return False, "OPENAI_API_KEY가 설정되지 않았습니다.", "OpenAI"

    model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    out_buf: List[str] = []
    try:
        # 구 SDK 호환(많이 쓰이는 방식)
        import openai
        openai.api_key = api_key

        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            request_timeout=timeout_s,
        )
        for ev in resp:
            try:
                delta = ev["choices"][0]["delta"].get("content", "")
            except Exception:
                delta = ""
            if delta:
                out_buf.append(delta)
                if on_delta:
                    on_delta(delta)

        full_text = "".join(out_buf).strip()
        if not full_text:
            # ✅ 핵심: 빈 응답은 성공으로 간주하지 않음
            return False, "OpenAI가 빈 응답을 반환했습니다.", "OpenAI"
        return True, full_text, "OpenAI"

    except Exception as e:
        return False, f"OpenAI 예외: {type(e).__name__}: {e}", "OpenAI"


def _call_gemini_stream(
    parts_or_messages,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    on_delta: Optional[Callable[[str], None]] = None,
    timeout_s: int = 60,
) -> Tuple[bool, Optional[str], str]:
    """
    Gemini generate_content 스트리밍 호출.
    - 반환: (ok, out_or_msg, "Gemini")
    - **빈 응답/예외/타임아웃은 ok=False** ← (버그 픽스)
    """
    messages = _normalize_messages(parts_or_messages)
    user_text = "\n\n".join([m["content"] for m in messages if m["role"] in ("system", "user")]).strip() or " "

    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("GEMINI_API_KEY", None) or st.secrets.get("GOOGLE_API_KEY", None)
    except Exception:
        pass
    api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return False, "GEMINI_API_KEY/GOOGLE_API_KEY가 설정되지 않았습니다.", "Gemini"

    model_id = model_name or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    out_buf: List[str] = []
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)

        # 스트림 시작
        resp = model.generate_content(
            user_text,
            stream=True,
            generation_config={
                "temperature": float(temperature),
                # "max_output_tokens": max_tokens or 1024,
            },
            safety_settings=None,
            request_options={"timeout": timeout_s} if hasattr(genai, "request_options") else None,
        )
        for chunk in resp:
            piece = getattr(chunk, "text", None)
            if piece:
                out_buf.append(piece)
                if on_delta:
                    on_delta(piece)

        full_text = "".join(out_buf).strip()
        if not full_text:
            # ✅ 핵심: 빈 응답은 성공으로 간주하지 않음
            return False, "Gemini가 빈 응답을 반환했습니다.", "Gemini"
        return True, full_text, "Gemini"

    except Exception as e:
        return False, f"Gemini 예외: {type(e).__name__}: {e}", "Gemini"
# ===== [05F] LLM STREAM CALL HELPERS — END ==================================


# ===== [06] 질문/답변 패널 — 학생 화면 최소화 지원(모드ON/OFF/에러로그 연동) — START
def _render_qa_panel():
    """
    학생/관리자 겸용 Q&A 패널.
      - 학생 화면: 두뇌 상태(녹색불), 응답 모드 선택, 채팅창만 노출
      - 관리자 화면: 기존 고급 옵션 그대로
      - 응답 모드 ON/OFF: ~/.maic/mode_enabled.json 반영
      - 에러 발생 시 [00B] 헬퍼로 세션 로그 기록
    """
    import os, difflib, importlib.util, traceback
    from datetime import datetime

    # ── 공용 세션 키 ─────────────────────────────────────────────────────────
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("_chat_next_id", 1)
    st.session_state.setdefault("_supplement_for_msg_id", None)
    st.session_state.setdefault("lead_provider", "Gemini")
    st.session_state.setdefault("dual_generate", False)
    st.session_state.setdefault("gemini_model_selection", os.getenv("GEMINI_MODEL","gemini-1.5-flash"))
    st.session_state.setdefault("use_context", True)
    st.session_state.setdefault("context_turns", 8)
    st.session_state.setdefault("context_max_chars", 2500)
    st.session_state.setdefault("primary_temperature", 0.3)
    st.session_state.setdefault("supp_temperature", 0.7)
    st.session_state.setdefault("supp_top_p", 0.95)

    # ── 학생/관리자 모드 판단 ───────────────────────────────────────────────
    def _to_bool(x): return str(x).strip().lower() in ("1","true","yes","y","on")
    app_mode = (os.getenv("APP_MODE") or getattr(st, "secrets", {}).get("APP_MODE") or "student").lower()
    student_view = (app_mode == "student") or _to_bool(getattr(st, "secrets", {}).get("STUDENT_VIEW", "true"))

    # ── 모드 ON/OFF 로드 ────────────────────────────────────────────────────
    def _enabled_modes() -> list[str]:
        try:
            return _load_enabled_modes(["문법설명","문장구조분석","지문분석"])
        except Exception as e:
            _errlog(f"enabled_modes 로드 실패: {e}", where="[06]_enabled_modes", exc=e)
            return ["문법설명","문장구조분석","지문분석"]

    # ── 도우미 ──────────────────────────────────────────────────────────────
    def _ts(): return datetime.utcnow().isoformat(timespec="seconds")
    def _new_id():
        i = st.session_state["_chat_next_id"]; st.session_state["_chat_next_id"] += 1; return i
    @st.cache_data(show_spinner=False)
    def _have_libs():
        have_gemini = importlib.util.find_spec("google.generativeai") is not None
        have_openai = importlib.util.find_spec("openai") is not None
        return have_gemini, have_openai

    have_gemini_lib, have_openai_lib = _have_libs()
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY"))
    has_openai_key = bool(os.getenv("OPENAI_API_KEY") or getattr(st, "secrets", {}).get("OPENAI_API_KEY"))

    # ── 상단(학생: 녹색불/모드 선택만 · 관리자: 고급옵션 포함) ────────────────
    rag_ready = _is_brain_ready()
    if student_view:
        with st.container(border=True):
            st.markdown(f"**{'🟢 두뇌 준비됨' if rag_ready else '🟡 두뇌 연결 대기'}**")
            enabled = _enabled_modes()
            mode = st.session_state.get("qa_mode_radio", enabled[0] if enabled else "문법설명")
            mode = st.radio("응답 모드", enabled or ["문법설명"], horizontal=True,
                            index=min((enabled or ["문법설명"]).index(mode) if mode in (enabled or []) else 0, len(enabled or ["문법설명"])-1))
            st.session_state["qa_mode_radio"] = mode
    else:
        # 관리자 뷰(기존 옵션 유지)
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1,1,1,1])
            with c1:
                st.markdown(f"**{'🟢 두뇌 준비됨' if rag_ready else '🟡 두뇌 연결 대기'}**")
            with c2:
                st.session_state["lead_provider"] = st.radio("리드 모델", ["Gemini","OpenAI"],
                                                             index=0 if st.session_state.get("lead_provider","Gemini")=="Gemini" else 1, horizontal=True)
            with c3:
                st.session_state["dual_generate"] = st.toggle("보충 설명 추가 생성", value=bool(st.session_state.get("dual_generate", False)))
            with c4:
                prim_temp = st.number_input("1차 온도", value=float(st.session_state.get("primary_temperature", 0.3)),
                                            min_value=0.0, max_value=2.0, step=0.1)
                st.session_state["primary_temperature"] = prim_temp
        with st.container(border=True):
            m1, m2, m3 = st.columns([1,1,1])
            with m1:
                enabled = _enabled_modes()
                mode = st.session_state.get("qa_mode_radio", enabled[0] if enabled else "문법설명")
                mode = st.radio("질문 모드", enabled or ["문법설명"], horizontal=True,
                                index=min((enabled or ["문법설명"]).index(mode) if mode in (enabled or []) else 0, len(enabled or ["문법설명"])-1))
                st.session_state["qa_mode_radio"] = mode
            with m2:
                st.session_state["use_context"] = st.toggle("맥락 포함", value=bool(st.session_state.get("use_context", True)))
            with m3:
                cturn = st.number_input("최근 포함 턴(K)", min_value=2, max_value=20, value=int(st.session_state.get("context_turns", 8)))
                st.session_state["context_turns"] = int(cturn)

    # ── 과거 대화 렌더 ───────────────────────────────────────────────────────
    with st.container(border=True):
        for msg in st.session_state["chat"]:
            if msg["role"] == "user":
                with st.chat_message("user", avatar="🧑"): st.markdown(msg["text"])
            else:
                provider_emoji = "🟣" if msg.get("provider") == "Gemini" else "🔵"
                with st.chat_message("assistant", avatar=provider_emoji): st.markdown(msg["text"])

    # ── 입력 & 1차 생성 ─────────────────────────────────────────────────────
    question = st.chat_input("질문을 입력하세요")
    if (question or "").strip():
        qtext = question.strip()
        with st.chat_message("user", avatar="🧑"): st.markdown(qtext)
        st.session_state["chat"].append({ "id": _new_id(), "role": "user", "text": qtext, "ts": _ts() })

        # 프롬프트 빌드
        try:
            from src.prompt_modes import prepare_prompt
            parts = prepare_prompt(
                mode=st.session_state.get("qa_mode_radio","문법설명"),
                question=qtext,
                use_context=bool(st.session_state.get("use_context", True)),
                context_turns=int(st.session_state.get("context_turns", 8)),
                context_max_chars=int(st.session_state.get("context_max_chars", 2500)),
                history=list(st.session_state.get("chat", [])),
                rag_ready=rag_ready,
                disclaimers_off=True
            )
            parts["system"] = f"{parts.get('system','')}\n주의: 변명/사과/한계 설명 금지. 학생이 이해하도록 친절히."
        except Exception as e:
            _errlog(f"프롬프트 생성 실패: {e}", where="[06]prepare_prompt", exc=e)
            with st.chat_message("assistant", avatar="⚠️"):
                st.error(f"프롬프트 생성 실패: {type(e).__name__}: {e}")
                st.code(traceback.format_exc(), language="python")
            return

        prim_temp = float(st.session_state.get("primary_temperature", 0.3))
        max_toks = 800
        lead = st.session_state.get("lead_provider", "Gemini")

        with st.chat_message("assistant", avatar="🤖"):
            st.caption(f"_{lead} 생성 중…_"); out_slot = st.empty()
            try:
                if lead == "Gemini":
                    if have_gemini_lib and has_gemini_key:
                        ok, out, provider_used = _call_gemini_stream(parts, out_slot, prim_temp, None, max_toks)
                    elif have_openai_lib and has_openai_key:
                        ok, out, provider_used = _call_openai_stream(parts, out_slot, prim_temp, None, max_toks)
                    else:
                        ok, out, provider_used = False, "Gemini/OpenAI 사용 불가(패키지 또는 키 누락)", lead
                else:
                    if have_openai_lib and has_openai_key:
                        ok, out, provider_used = _call_openai_stream(parts, out_slot, prim_temp, None, max_toks)
                    elif have_gemini_lib and has_gemini_key:
                        ok, out, provider_used = _call_gemini_stream(parts, out_slot, prim_temp, None, max_toks)
                    else:
                        ok, out, provider_used = False, "OpenAI/Gemini 사용 불가(패키지 또는 키 누락)", lead
            except Exception as e:
                _errlog(f"1차 생성 호출 실패: {e}", where="[06]primary_call", exc=e)
                ok, out, provider_used = False, f"{type(e).__name__}: {e}", lead

            if ok and (out and out.strip()):
                aid = _new_id()
                st.session_state["chat"].append({
                    "id": aid, "role": "assistant", "provider": provider_used,
                    "kind": "primary", "text": out, "ts": _ts()
                })
                if bool(st.session_state.get("dual_generate", False)):
                    st.session_state["_supplement_for_msg_id"] = aid
                st.rerun()
            else:
                # 폴백
                fallback_ok, fallback_out, fallback_provider = False, None, lead
                if lead == "Gemini" and have_openai_lib and has_openai_key:
                    st.caption("_Gemini 실패 → OpenAI 폴백_")
                    fallback_ok, fallback_out, fallback_provider = _call_openai_stream(parts, out_slot, prim_temp, None, max_toks)
                elif lead != "Gemini" and have_gemini_lib and has_gemini_key:
                    st.caption("_OpenAI 실패 → Gemini 폴백_")
                    fallback_ok, fallback_out, fallback_provider = _call_gemini_stream(parts, out_slot, prim_temp, None, max_toks)

                if fallback_ok and (fallback_out and fallback_out.strip()):
                    aid = _new_id()
                    st.session_state["chat"].append({ "id": aid, "role": "assistant", "provider": fallback_provider,
                                                      "kind": "primary", "text": fallback_out, "ts": _ts() })
                    if bool(st.session_state.get("dual_generate", False)):
                        st.session_state["_supplement_for_msg_id"] = aid
                    st.rerun()
                else:
                    _errlog(f"1차 생성 실패: {(fallback_out or out) or '원인 불명'}", where="[06]primary_fail")
                    st.error(f"1차 생성 실패: {(fallback_out or out) or '원인 불명'}")

    # ── 보충 생성(관리자 옵션 켠 경우만) ─────────────────────────────────────
    if not student_view:
        target_id = st.session_state.get("_supplement_for_msg_id")
        if target_id:
            primary = None
            for msg in reversed(st.session_state["chat"]):
                if msg["id"] == target_id and msg.get("kind") == "primary":
                    primary = msg; break
            if primary:
                base_q = ""
                for m in reversed(st.session_state["chat"]):
                    if m["role"] == "user" and m["id"] < primary["id"]:
                        base_q = m["text"]; break
                try:
                    from src.prompt_modes import prepare_prompt
                    parts2 = prepare_prompt(
                        mode=st.session_state.get("qa_mode_radio","문법설명"), question=base_q,
                        use_context=bool(st.session_state.get("use_context", True)),
                        context_turns=int(st.session_state.get("context_turns", 8)),
                        context_max_chars=int(st.session_state.get("context_max_chars", 2500)),
                        history=list(st.session_state.get("chat", [])),
                        rag_ready=rag_ready, disclaimers_off=True
                    )
                    supp_temp2 = float(st.session_state.get("supp_temperature", 0.7))
                    supp_top_p2 = float(st.session_state.get("supp_top_p", 0.95))
                    other = "OpenAI" if primary.get("provider") == "Gemini" else "Gemini"
                    out_slot = st.empty()
                    if other == "OpenAI":
                        ok2, out2, _ = _call_openai_stream(parts2, out_slot, supp_temp2, supp_top_p2, 800)
                    else:
                        ok2, out2, _ = _call_gemini_stream(parts2, out_slot, supp_temp2, supp_top_p2, 800)
                except Exception as e:
                    _errlog(f"보충 생성 실패: {e}", where="[06]supplement", exc=e)
                    st.session_state["_supplement_for_msg_id"] = None
                    return

                if ok2 and out2:
                    st.session_state["chat"].append({
                        "id": _new_id(), "role": "assistant", "provider": other,
                        "kind": "supplement", "text": out2, "ts": _ts()
                    })
                    st.session_state["_supplement_for_msg_id"] = None
                    st.rerun()
                else:
                    st.session_state["_supplement_for_msg_id"] = None
# ===== [06] 질문/답변 패널 — END ==============================================

# ===== [07] MAIN — 오케스트레이터 (정리/표준화) ===============================
def _boot_and_render():
    """
    - 상단 헤더/상태
    - (선택) 관리자 툴바
    - 관리자 패널: 진단(선택), 자료 최적화/백업(인덱싱 버튼 포함) ★
    - 학생/관리자 Q&A 패널
    """
    import os, traceback

    # 0) 헤더(있으면)
    try:
        if "render_header" in globals():
            render_header()
    except Exception:
        pass

    # 1) 관리자 툴바(있으면)
    try:
        if "render_admin_toolbar" in globals():
            render_admin_toolbar()
    except Exception:
        pass

    # 2) 관리자 패널들
    # 2-1) 고급 진단 섹션은 기본 숨김(환경변수로만 노출)
    show_diag = str(os.environ.get("SHOW_ADMIN_DIAGNOSTICS", "0")).lower() in ("1","true","yes","on")
    if show_diag and "_render_admin_diagnostics_section" in globals():
        try:
            _render_admin_diagnostics_section()
        except Exception as e:
            st.error(f"관리자 진단 패널 오류: {type(e).__name__}: {e}")
            st.code(traceback.format_exc(), language="python")

    # 2-2) ★ 자료 최적화/백업(인덱싱 버튼 포함) — 항상 노출
    if "render_brain_prep_main" in globals():
        try:
            render_brain_prep_main()
        except Exception as e:
            # 예외를 숨기지 말고 보여줍니다 → 버튼이 왜 안 보이는지 즉시 파악 가능
            st.error(f"자료 최적화/백업 패널 오류: {type(e).__name__}: {e}")
            st.code(traceback.format_exc(), language="python")

    # 2-3) 레거시 패널(경로 테스트/이 경로 사용/자동 인덱스 토글 등)은 기본 숨김
    show_legacy = str(os.environ.get("SHOW_LEGACY_ADMIN_SECTIONS", "0")).lower() in ("1","true","yes","on")
    if show_legacy:
        for name in ("render_prepared_dir_admin", "render_auto_index_admin", "render_legacy_index_panel"):
            if name in globals():
                try:
                    globals()[name]()  # type: ignore[index]
                except Exception as e:
                    st.warning(f"{name} 오류: {type(e).__name__}: {e}")

    # 3) Q&A 패널
    try:
        if "_render_qa_panel" in globals():
            _render_qa_panel()
        elif "render_qa_panel" in globals():
            render_qa_panel()
        else:
            st.error("Q&A 패널 함수가 없습니다: _render_qa_panel / render_qa_panel")
    except Exception as e:
        st.error(f"질문 패널 렌더 중 오류: {type(e).__name__}: {e}")
        st.code(traceback.format_exc(), language="python")

# 진입점
_boot_and_render()
# ===== [07] MAIN — END =======================================================


# ===== [08] ADMIN — 인덱싱/강제 동기화·모드ON/OFF·에러로그 — START ============
def _load_modes_from_yaml(path: str) -> list[str]:
    """로컬 prompts.yaml에서 modes 키 목록을 읽어온다."""
    try:
        import yaml, pathlib
        p = pathlib.Path(path)
        if not p.exists(): return []
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        modes = list((data.get("modes") or {}).keys())
        return [m for m in modes if isinstance(m, str)]
    except Exception as e:
        _errlog(f"prompts.yaml 파싱 실패: {e}", where="[ADMIN]_load_modes_from_yaml", exc=e)
        return []

def _load_enabled_modes(defaults: list[str]) -> list[str]:
    """~/.maic/mode_enabled.json 에 저장된 on/off 목록 로드, 없으면 defaults 전체 사용."""
    import json, os, pathlib
    path = pathlib.Path(os.path.expanduser("~/.maic/mode_enabled.json"))
    if not path.exists(): return list(defaults)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        enabled = [m for m, on in data.items() if on]
        return enabled or list(defaults)
    except Exception as e:
        _errlog(f"mode_enabled.json 로드 실패: {e}", where="[ADMIN]_load_enabled_modes", exc=e)
        return list(defaults)

def _save_enabled_modes(state: dict[str, bool]) -> tuple[bool, str]:
    """모드 on/off 저장."""
    import json, os, pathlib
    try:
        path = pathlib.Path(os.path.expanduser("~/.maic/mode_enabled.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True, f"저장됨: {path}"
    except Exception as e:
        _errlog(f"mode_enabled 저장 실패: {e}", where="[ADMIN]_save_enabled_modes", exc=e)
        return False, f"{type(e).__name__}: {e}"

def _run_index_job(mode: str) -> tuple[bool, str]:
    """
    인덱스 실행(전체/증분). 프로젝트 인덱스 모듈을 자동 탐색해 호출.
    우선 모듈: src.rag.index_build → src.index_build → index_build → rag.index_build
    """
    import importlib, importlib.util, inspect
    from pathlib import Path

    def _find_module(names: list[str]):
        for n in names:
            if importlib.util.find_spec(n) is not None:
                return importlib.import_module(n)
        return None

    mod = _find_module(["src.rag.index_build","src.index_build","index_build","rag.index_build"])
    if not mod:
        return False, "인덱스 모듈을 찾지 못했습니다"

    PERSIST_DIR = Path.home() / ".maic" / "persist"
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)

    # prepared 폴더 ID (secrets에서 관대하게 탐색)
    def _pick_folder_id():
        for k in ["GDRIVE_PREPARED_FOLDER_ID","PREPARED_FOLDER_ID","APP_GDRIVE_FOLDER_ID","GDRIVE_FOLDER_ID"]:
            v = getattr(st, "secrets", {}).get(k)
            if v and str(v).strip(): return str(v).strip()
        return ""

    gdrive_folder_id = _pick_folder_id()

    prog = st.progress(0, text="인덱싱 준비 중…")
    msg_box = st.empty()
    def _pct(v: int, msg: str|None=None):
        try: prog.progress(max(0, min(100, int(v))), text=(msg or "인덱싱 중…"))
        except Exception: pass
    def _msg(s: str):
        try: msg_box.write(s)
        except Exception: pass

    def _try(fn_name: str, **kw):
        fn = getattr(mod, fn_name, None)
        if not callable(fn): return False, None
        try:
            sig = inspect.signature(fn)
            call_kw = {k:v for k,v in kw.items() if k in sig.parameters}
            res = fn(**call_kw)
            return True, res
        except Exception as e:
            _errlog(f"{fn_name} 실패: {e}", where="[ADMIN]_run_index_job", exc=e)
            return False, f"{fn_name} 실패: {type(e).__name__}: {e}"

    ok, res = _try("build_index_with_checkpoint",
                   update_pct=_pct, update_msg=_msg, gdrive_folder_id=gdrive_folder_id,
                   gcp_creds={}, persist_dir=str(PERSIST_DIR), remote_manifest={}, should_stop=None, mode=mode)
    if ok:
        try: st.cache_data.clear()
        except Exception: pass
        return True, "인덱싱 완료(build_index_with_checkpoint)"

    ok, res = _try("build_index", mode=mode, persist_dir=str(PERSIST_DIR),
                   gdrive_folder_id=gdrive_folder_id, update_pct=_pct, update_msg=_msg, should_stop=None)
    if ok:
        try: st.cache_data.clear()
        except Exception: pass
        return True, "인덱싱 완료(build_index)"

    if mode=="full":
        ok, res = _try("build_all", persist_dir=str(PERSIST_DIR))
        if ok:
            try: st.cache_data.clear()
            except Exception: pass
            return True, "인덱싱 완료(build_all)"
    else:
        ok, res = _try("build_incremental", persist_dir=str(PERSIST_DIR))
        if ok:
            try: st.cache_data.clear()
            except Exception: pass
            return True, "인덱싱 완료(build_incremental)"

    ok, res = _try("main", argv=["--persist", str(PERSIST_DIR), "--mode", ("full" if mode=='full' else 'inc'), "--folder", gdrive_folder_id])
    if ok:
        try: st.cache_data.clear()
        except Exception: pass
        return True, "인덱싱 완료(main)"

    return False, (res or "인덱스 엔트리포인트 호출 실패")

def render_admin_tools():
    """
    관리자 도구(모듈형, 모두 접기/펼치기 가능)
      ① 프롬프트/연결 상태
      ② 응답 모드 ON/OFF
      ③ 인덱싱(전체/신규만)
      ④ prompts.yaml 강제 동기화
      ⑤ 에러 로그(복사/다운로드/초기화)
    """
    import os, json, pathlib
    from pathlib import Path

    with st.expander("관리자 도구", expanded=True):
        # ① 상태
        with st.expander("① 진단 · 프롬프트/연결 상태", expanded=True):
            folder_id = os.getenv("PROMPTS_DRIVE_FOLDER_ID") or getattr(st, "secrets", {}).get("PROMPTS_DRIVE_FOLDER_ID")
            oauth_info = getattr(st, "secrets", {}).get("gdrive_oauth")
            who = None
            try:
                if isinstance(oauth_info, str): who = json.loads(oauth_info).get("email")
                elif isinstance(oauth_info, dict): who = oauth_info.get("email")
            except Exception: pass
            local_prompts = os.path.expanduser("~/.maic/prompts.yaml")
            exists = pathlib.Path(local_prompts).exists()
            persist_dir = Path.home() / ".maic" / "persist"

            st.write(f"• Drive 폴더 ID(프롬프트): `{folder_id or '미설정'}`")
            st.write(f"• Drive 연결: {'🟢 연결됨' if bool(oauth_info) else '🔴 미연결'} — 계정: `{who or '알 수 없음'}`")
            st.write(f"• 로컬 prompts 경로: `{local_prompts}` — 존재: {'✅ 있음' if exists else '❌ 없음'}")
            st.write(f"• 인덱스 보관 경로: `{persist_dir}`")

        # ② 모드 ON/OFF
        with st.expander("② 응답 모드 ON/OFF", expanded=True):
            prompts_path = st.session_state.get("prompts_path", os.path.expanduser("~/.maic/prompts.yaml"))
            all_modes = _load_modes_from_yaml(prompts_path) or ["문법설명","문장구조분석","지문분석"]
            st.caption(f"감지된 모드: {', '.join(all_modes)}")
            current_on = _load_enabled_modes(all_modes)
            state = {}
            cols = st.columns(min(3, len(all_modes)) or 1)
            for i, m in enumerate(all_modes):
                with cols[i % len(cols)]:
                    state[m] = st.toggle(m, value=(m in current_on), key=f"mode_on__{m}")
            if st.button("저장(학생 화면 반영)", use_container_width=True):
                ok, msg = _save_enabled_modes(state)
                (st.success if ok else st.error)(msg)

        # ③ 인덱싱
        with st.expander("③ 인덱싱(전체/신규만)", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                if st.button("전체 인덱스 다시 만들기", use_container_width=True):
                    with st.spinner("전체 인덱싱 중… 시간이 걸릴 수 있어요"):
                        ok, msg = _run_index_job("full")
                    (st.success if ok else st.error)(msg)
            with c2:
                if st.button("신규 파일만 인덱스", use_container_width=True):
                    with st.spinner("증분 인덱싱 중…"):
                        ok, msg = _run_index_job("inc")
                    (st.success if ok else st.error)(msg)

        # ④ prompts.yaml 강제 동기화
        with st.expander("④ 드라이브에서 prompts.yaml 당겨오기(강제)", expanded=False):
            if st.button("동기화 실행", use_container_width=True):
                ok, msg = sync_prompts_from_drive(
                    local_path=os.path.expanduser("~/.maic/prompts.yaml"),
                    file_name=(os.getenv("PROMPTS_FILE_NAME") or getattr(st, "secrets", {}).get("PROMPTS_FILE_NAME") or "prompts.yaml"),
                    folder_id=(os.getenv("PROMPTS_DRIVE_FOLDER_ID") or getattr(st, "secrets", {}).get("PROMPTS_DRIVE_FOLDER_ID")),
                    prefer_folder_name="prompts", verbose=True
                )
                (st.success if ok else st.error)(msg)

        # ⑤ 에러 로그
        with st.expander("⑤ 에러/오류 로그", expanded=False):
            logs = _errlog_text()
            st.text_area("세션 에러 로그 (복사 가능)", value=logs, height=200)
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("로그 내려받기", data=logs or "로그 없음", file_name="error_log.txt")
            with c2:
                if st.button("로그 초기화"):
                    st.session_state["_error_log"] = []
                    st.success("초기화 완료")
# ===== [08] ADMIN — 인덱싱/강제 동기화·모드ON/OFF·에러로그 — END =============


# ===== [23] PROMPTS 동기화 (Google Drive → Local) — START =====================
def sync_prompts_from_drive(
    *,
    local_path: str | None = None,           # None이면 ~/.maic/prompts.yaml
    file_name: str | None = None,            # None이면 "prompts.yaml"
    folder_id: str | None = None,            # 있으면 해당 폴더 안에서만 검색
    prefer_folder_name: str | None = None,   # 폴더명 힌트(없어도 됨)
    verbose: bool = True,
) -> tuple[bool, str]:
    """
    Google Drive에서 최신 'prompts.yaml'을 찾아 로컬로 저장.

    ✅ 자격증명 우선순위(요구사항 반영: 개인 계정 → OAuth 우선)
      1) st.secrets['gdrive_oauth']  (사용자 OAuth 토큰 JSON)
      2) st.secrets['gcp_service_account'] 또는 env 'GCP_SERVICE_ACCOUNT_JSON' (서비스계정)

    검색 우선순위:
      - folder_id 지정 시: 그 폴더 안에서 name = file_name 최신 1개
      - folder_id 없고 prefer_folder_name 지정 시: 폴더명으로 폴더 찾은 뒤 그 안 검색
      - 그래도 못 찾으면 전역 검색(name = file_name)

    반환: (ok, message)
    """
    try:
        import os, io, json as _json
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        from google.auth.transport.requests import Request

        # ✅ OAuth 먼저 시도 (개인 계정 시 필수)
        oauth_info = getattr(st, "secrets", {}).get("gdrive_oauth")
        sa_info = (getattr(st, "secrets", {}).get("gcp_service_account")
                   or os.getenv("GCP_SERVICE_ACCOUNT_JSON"))

        creds = None
        if oauth_info:
            from google.oauth2.credentials import Credentials
            if isinstance(oauth_info, str): oauth_info = _json.loads(oauth_info)
            creds = Credentials(
                token=oauth_info.get("access_token"),
                refresh_token=oauth_info.get("refresh_token"),
                token_uri=oauth_info.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=oauth_info.get("client_id"),
                client_secret=oauth_info.get("client_secret"),
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            using = "oauth_user"
            who = oauth_info.get("email", "unknown-user")
        elif sa_info:
            from google.oauth2 import service_account
            if isinstance(sa_info, str): sa_info = _json.loads(sa_info)
            creds = service_account.Credentials.from_service_account_info(
                sa_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
            using = "service_account"
            who = sa_info.get("client_email", "unknown-sa")
        else:
            return False, "자격증명 누락: gdrive_oauth 또는 gcp_service_account 필요"

        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        # 기본값 계산
        if local_path is None:
            local_path = os.path.expanduser("~/.maic/prompts.yaml")
        if file_name is None:
            file_name = "prompts.yaml"

        # 내부 헬퍼: 폴더 안 최신 파일 찾기
        def _latest_in_folder(fid: str) -> str | None:
            q = f"'{fid}' in parents and name = '{file_name}' and trashed = false"
            r = drive.files().list(q=q, orderBy="modifiedTime desc", pageSize=1,
                                   fields="files(id,name,modifiedTime)").execute()
            arr = r.get("files", [])
            return arr[0]["id"] if arr else None

        file_id = None

        # 1) 폴더 ID로 직접 검색
        if folder_id:
            file_id = _latest_in_folder(folder_id)

        # 2) 폴더명 힌트가 있으면 그 폴더들을 찾아 순회
        if not file_id and prefer_folder_name:
            q_folder = ("mimeType = 'application/vnd.google-apps.folder' "
                        f"and name = '{prefer_folder_name}' and trashed = false")
            r = drive.files().list(q=q_folder, fields="files(id,name)", pageSize=5).execute()
            for f in r.get("files", []):
                fid = _latest_in_folder(f["id"])
                if fid:
                    file_id = fid
                    break

        # 3) 전역 검색
        if not file_id:
            q_any = f"name = '{file_name}' and trashed = false"
            r = drive.files().list(q=q_any, orderBy="modifiedTime desc",
                                   pageSize=1, fields="files(id,name,modifiedTime,parents)").execute()
            arr = r.get("files", [])
            if arr: file_id = arr[0]["id"]

        if not file_id:
            who_hint = f"({using}: {who})"
            return False, f"Drive에서 '{file_name}'을 찾지 못했습니다 {who_hint}"

        # 4) 다운로드
        req = drive.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        # 5) 저장
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(buf.getvalue())

        if verbose:
            st.toast(f"prompts.yaml 동기화 완료 → {local_path}")

        return True, f"다운로드 성공: {local_path}"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
# ===== [23] PROMPTS 동기화 (Google Drive → Local) — END =======================
