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

# ===== [04C] 프롬프트 소스/드라이브 진단 패널(고급) ==========================
def _render_admin_diagnostics_section():
    """프롬프트 소스/환경 상태 점검 + 드라이브 강제 동기화 + Δ(차이) 요약 + 로그 연계"""
    import os
    import importlib  # ✅ NameError 방지: 함수 내부 임포트
    from datetime import datetime
    from pathlib import Path as _P
    import json as _json

    def _log(step: str, **kw):
        """[05B] 타임라인에 기록(있으면), 없으면 무시."""
        try:
            _lf = globals().get("_log_attach")
            if callable(_lf):
                _lf(step, **kw)
        except Exception:
            pass

    # 관리자 가드
    if not (st.session_state.get("is_admin")
            or st.session_state.get("admin_mode")
            or st.session_state.get("role") == "admin"
            or st.session_state.get("mode") == "admin"):
        return

    # 🔽 전역 토글 상태 반영
    _expand_all = bool(st.session_state.get("_admin_expand_all", True))

    with st.expander("🛠 진단 · 프롬프트 소스 상태(고급)", expanded=_expand_all):
        # 0) 모듈 로드
        try:
            pm = importlib.import_module("src.prompt_modes")
        except Exception as e:
            st.error(f"prompt_modes 임포트 실패: {type(e).__name__}: {e}")
            _log("prompts_import_fail", error=f"{type(e).__name__}: {e}")
            return

        # 인덱스 모듈 로드 경로 힌트 배지
        st.write("• 인덱스 로드 경로 힌트:",
                 f"`{os.getenv('MAIC_IMPORT_INDEX_BUILD_RESOLVE', 'unknown')}`")

        # 1) 환경/secrets (마스킹)
        folder_id = os.getenv("MAIC_PROMPTS_DRIVE_FOLDER_ID")
        try:
            if (not folder_id) and ("MAIC_PROMPTS_DRIVE_FOLDER_ID" in st.secrets):
                folder_id = str(st.secrets["MAIC_PROMPTS_DRIVE_FOLDER_ID"])
        except Exception:
            pass

        def _mask(v):
            if not v: return "— 없음"
            s = str(v)
            return (s[:6] + "…" + s[-4:]) if len(s) > 12 else ("*" * len(s))

        st.write("• Drive 폴더 ID:", _mask(folder_id))

        # 2) Drive 연결 및 계정 이메일
        drive_ok, drive_email, drive_err = False, None, None
        try:
            im = importlib.import_module("src.rag.index_build")
            svc_factory = getattr(im, "_drive_service", None)
            svc = svc_factory() if callable(svc_factory) else None
            if svc:
                drive_ok = True
                try:
                    about = svc.about().get(fields="user").execute()
                    drive_email = (about or {}).get("user", {}).get("emailAddress")
                except Exception as e:
                    drive_err = f"{type(e).__name__}: {e}"
        except Exception as e:
            drive_err = f"{type(e).__name__}: {e}"
        st.write("• Drive 연결:", "✅ 연결됨" if drive_ok else "❌ 없음")
        if drive_email:
            st.write("• 연결 계정:", f"`{drive_email}`")
        if drive_err and not drive_ok:
            st.info(f"Drive 서비스 감지 실패: {drive_err}")

        # 3) 로컬 파일 경로/상태
        try:
            p = pm.get_overrides_path()
            p = _P(p) if not isinstance(p, _P) else p
        except Exception as e:
            st.error(f"get_overrides_path 실패: {type(e).__name__}: {e}")
            _log("prompts_path_fail", error=f"{type(e).__name__}: {e}")
            return

        st.write("• 로컬 경로:", f"`{p}`")
        exists = p.exists()
        st.write("• 파일 존재:", "✅ 있음" if exists else "❌ 없음")
        if exists:
            try:
                stat = p.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                st.write("• 크기/수정시각:", f"{stat.st_size} bytes / {mtime}")
            except Exception:
                pass

        # 4) 마지막 동기화 메타
        st.session_state.setdefault("prompts_sync_meta", {"last": None, "result": None})
        meta = st.session_state["prompts_sync_meta"]
        st.caption(f"마지막 동기화: {meta.get('last') or '—'} / 결과: {meta.get('result') or '—'}")

        # 5) 강제 동기화 + 미리보기/다운로드 + Δ(차이) 요약
        colA, colB, colC = st.columns([1,1,1])

        with colA:
            if st.button("🔄 드라이브에서 prompts.yaml 당겨오기(강제)",
                         use_container_width=True, key="btn_force_pull_prompts"):
                _log("prompts_pull_start")
                with st.status("드라이브 동기화 중…", state="running") as stt:
                    pulled = None
                    try:
                        # 5-1) 강제 새로고침 플래그
                        if hasattr(pm, "_REMOTE_PULL_ONCE_FLAG"):
                            pm._REMOTE_PULL_ONCE_FLAG["done"] = False
                        # 5-2) 가능한 경우: 최신본만 당김
                        if hasattr(pm, "_pull_remote_overrides_if_newer"):
                            pulled = pm._pull_remote_overrides_if_newer()
                        else:
                            # 5-3) 폴백: 로컬 로드
                            _ = pm.load_overrides()
                            pulled = "loaded"
                        # 5-4) 메타 기록
                        meta["last"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        meta["result"] = pulled or "nochange"
                        st.session_state["prompts_sync_meta"] = meta
                        stt.update(label=f"동기화 완료: {pulled or '변경 없음'}", state="complete")
                        st.success(f"동기화 결과: {pulled}" if pulled else "동기화 결과: 변경 없음")
                        _log("prompts_pull_done", result=(pulled or "nochange"))
                    except Exception as e:
                        meta["last"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        meta["result"] = f"fail:{type(e).__name__}"
                        st.session_state["prompts_sync_meta"] = meta
                        stt.update(label="동기화 실패", state="error")
                        st.error(f"동기화 실패: {type(e).__name__}: {e}")
                        _log("prompts_pull_fail", error=f"{type(e).__name__}: {e}")

        with colB:
            if exists and st.button("📄 로컬 파일 내용 미리보기",
                                    use_container_width=True, key="btn_preview_prompts_yaml"):
                try:
                    st.code(p.read_text(encoding="utf-8"), language="yaml")
                except Exception as e:
                    st.error(f"파일 읽기 실패: {type(e).__name__}: {e}")

        with colC:
            if exists:
                try:
                    st.download_button(
                        "⬇ 로컬 prompts.yaml 다운로드",
                        data=p.read_bytes(),
                        file_name="prompts.yaml",
                        mime="text/yaml",
                        use_container_width=True,
                        key="btn_download_prompts_yaml",
                    )
                except Exception as e:
                    st.error(f"다운로드 준비 실패: {type(e).__name__}: {e}")

        st.markdown("---")

        # 6) Δ(차이) 요약
        st.caption("Δ(차이) 요약: 이전 스냅샷 ↔ 현재 로드된 overrides 비교")
        st.session_state.setdefault("prompts_last_loaded", None)

        prev = st.session_state.get("prompts_last_loaded")
        curr = None
        load_err = None
        try:
            curr = pm.load_overrides()
        except Exception as e:
            load_err = f"{type(e).__name__}: {e}"
            st.error(f"YAML 로드 오류: {load_err}")
            _log("prompts_yaml_load_fail", error=load_err)

        if curr is not None:
            if prev is None:
                st.session_state["prompts_last_loaded"] = curr

            modes_prev = set(((prev or {}).get("modes") or {}).keys())
            modes_curr = set(((curr or {}).get("modes") or {}).keys())
            added = sorted(list(modes_curr - modes_prev))
            removed = sorted(list(modes_prev - modes_curr))
            common = sorted(list(modes_curr & modes_prev))

            col1, col2 = st.columns(2)
            with col1:
                st.write("➕ 추가된 모드:", ", ".join(added) if added else "— 없음")
            with col2:
                st.write("➖ 제거된 모드:", ", ".join(removed) if removed else "— 없음")

            changed_summary = []
            for m in common:
                a = (prev or {}).get("modes", {}).get(m, {})
                b = (curr or {}).get("modes", {}).get(m, {})
                changes = []
                for k in sorted(set(a.keys()) | set(b.keys())):
                    if a.get(k) != b.get(k):
                        try:
                            va = _json.dumps(a.get(k), ensure_ascii=False)[:120]
                            vb = _json.dumps(b.get(k), ensure_ascii=False)[:120]
                        except Exception:
                            va, vb = str(a.get(k)), str(b.get(k))
                        changes.append(f"{k}: {va} → {vb}")
                if changes:
                    changed_summary.append((m, changes[:8]))

            if changed_summary:
                with st.expander("📝 변경된 모드 상세 (상위 일부)", expanded=_expand_all):
                    for m, chs in changed_summary:
                        st.markdown(f"- **{m}**")
                        for line in chs:
                            st.write("  • ", line)
            else:
                st.caption("모드 구성 값 변경 없음(얕은 비교 기준).")

            if st.button("📌 현재 구성을 기준 스냅샷으로 저장", use_container_width=True, key="btn_save_prompts_snapshot"):
                st.session_state["prompts_last_loaded"] = curr
                st.success("현재 로드된 overrides를 스냅샷으로 저장했습니다.")
                _log("prompts_snapshot_saved")

        try:
            modes = list(((curr or {}).get("modes") or {}).keys())
        except Exception:
            modes = []
        st.write("• 현재 포함된 모드:", " , ".join(modes) if modes else "— (미검출)")

_render_admin_diagnostics_section()
# ===== [04C] END ==============================================================

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

# ===== [06] 질문/답변 패널 — 채팅창 UI + 맥락 + 보충 차별화/유사도 가드 ========

# ===== [PATCH-BRAIN-HELPER] 두뇌(인덱스) 연결 여부 감지 =======================
def _is_brain_ready() -> bool:
    """
    세션에 저장된 여러 플래그를 종합해 RAG 인덱스가 '부착됨' 상태인지 추정.
    기존/미래 키와 호환되도록 넓게 본다.
    """
    ss = st.session_state
    last = ss.get("_auto_restore_last") or {}
    flags = (
        ss.get("rag_attached"),
        ss.get("rag_index_ready"),
        ss.get("rag_index_attached"),
        ss.get("index_attached"),
        ss.get("attached_local"),
        last.get("attached_local"),
    )
    return any(bool(x) for x in flags)

# ===== [06] 질문/답변 패널 — 채팅창 UI + 맥락 + 보충 차별화/유사도 가드 ========
def _render_qa_panel():
    """
    질문/답변 패널 전체:
      - 상단: 두뇌 준비 배지/상태
      - 질문 모드 선택(문법설명/문장구조분석/지문분석)
      - 대화 맥락 포함/길이 조절
      - 1차/2차 생성 파라미터 분리(온도/토큰/탑P)
      - 디클레이머 금지
      - 맥락 엔진: 최근 K턴 + 길이 상한, 관리자 옵션
      - 보충 다양화: 1차/2차 온도 분리 + 2차 top_p + 유사도 가드(자동 재생성 1회)
    """
    import os, difflib
    import traceback, importlib.util
    from datetime import datetime

    # ── 세션 기본키 ───────────────────────────────────────────────────────────
    st.session_state.setdefault("chat", [])              # [{id,role,text,provider,kind,ts}]
    st.session_state.setdefault("_chat_next_id", 1)
    st.session_state.setdefault("_supplement_for_msg_id", None)

    # 기존 상태키(안전 유지)
    st.session_state.setdefault("lead_provider", "Gemini")  # "Gemini" | "OpenAI"
    st.session_state.setdefault("dual_generate", False)
    st.session_state.setdefault("gemini_model_selection",
                                os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))

    # ── (C1) 대화 맥락 옵션(관리자) ─────────────────────────────────────────
    st.session_state.setdefault("use_context", True)         # 맥락 사용 여부
    st.session_state.setdefault("context_turns", 8)          # 최근 포함 턴 수(K)
    st.session_state.setdefault("context_max_chars", 2500)   # 맥락 길이 상한(문자)
    st.session_state.setdefault("_session_summary", "")      # 필요시 요약 저장(옵션)

    # ── (NEW) 생성 파라미터(1차/2차 분리) ───────────────────────────────────
    st.session_state.setdefault("primary_temperature", 0.3)
    st.session_state.setdefault("supp_temperature", 0.7)
    st.session_state.setdefault("supp_top_p", 0.95)

    # ── (C2) 디클레이머 금지, 스타일 ────────────────────────────────────────
    DECL_NO = (
        "주의: 변명/사과/한계 설명(디클레이머) 금지. 학생이 이해할 수 있게 친절히 설명."
    )

    # ── (H) 보조 헬퍼 ───────────────────────────────────────────────────────
    def _ts(): return datetime.utcnow().isoformat(timespec="seconds")
    def _new_id():
        i = st.session_state["_chat_next_id"]; st.session_state["_chat_next_id"] += 1; return i

    @st.cache_data(show_spinner=False)
    def _have_libs():
        have_gemini_lib = importlib.util.find_spec("google.generativeai") is not None
        # OpenAI SDK v1 계열: openai 모듈 + client.chat.completions.create 사용
        have_openai_lib = importlib.util.find_spec("openai") is not None
        return have_gemini_lib, have_openai_lib

    have_gemini_lib, have_openai_lib = _have_libs()
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY"))
    has_openai_key = bool(os.getenv("OPENAI_API_KEY") or getattr(st, "secrets", {}).get("OPENAI_API_KEY"))

    # ── (U0) 상단 상태/옵션 바 ───────────────────────────────────────────────
    rag_ready = _is_brain_ready()
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        with c1:
            badge = "🟢 두뇌 준비됨" if rag_ready else "🟡 두뇌 연결 대기"
            st.markdown(f"**{badge}**")
        with c2:
            st.session_state["lead_provider"] = st.radio(
                "리드 모델", options=["Gemini", "OpenAI"], horizontal=True,
                index=0 if st.session_state.get("lead_provider","Gemini")=="Gemini" else 1
            )
        with c3:
            st.session_state["dual_generate"] = st.toggle("보충 설명 추가 생성", value=bool(st.session_state.get("dual_generate", False)))
        with c4:
            prim_temp = st.number_input("1차 온도", value=float(st.session_state.get("primary_temperature", 0.3)), min_value=0.0, max_value=2.0, step=0.1)
            st.session_state["primary_temperature"] = prim_temp

    # 프롬프트 모드 셀렉터
    with st.container(border=True):
        m1, m2, m3 = st.columns([1,1,1])
        with m1:
            mode = st.session_state.get("qa_mode_radio", "문법설명")
            mode = st.radio("질문 모드", ["문법설명","문장구조분석","지문분석"], index=["문법설명","문장구조분석","지문분석"].index(mode), horizontal=True)
            st.session_state["qa_mode_radio"] = mode
        with m2:
            st.session_state["use_context"] = st.toggle("맥락 포함", value=bool(st.session_state.get("use_context", True)))
        with m3:
            cturn = st.number_input("최근 포함 턴(K)", min_value=2, max_value=20, value=int(st.session_state.get("context_turns", 8)))
            st.session_state["context_turns"] = int(cturn)

    # 프롬프트 미리보기 토글(전역)
    show_prompt = st.toggle("프롬프트 미리보기", value=False, key="show_prompt_toggle")

    # ===== [06A] (U1+Builder) 채팅창 CSS + 프롬프트 빌더(맥락·출처 규칙) = START
    # ── (U1) 채팅창 말풍선/패널 스타일(CSS) ──────────────────────────────────
    st.markdown("""
    <style>
      div[data-testid="stChatMessage"]{
        background:#EAF5FF; border:1px solid #BCDFFF; border-radius:12px;
        padding:6px 10px; margin:6px 0;
      }
      div[data-testid="stChatMessage"] .stMarkdown p{ margin-bottom:0.4rem; }
    </style>
    """, unsafe_allow_html=True)

    # ── (U2) 말풍선 컨텍스트 ──────────────────────────────────────────────────
    from contextlib import contextmanager
    @contextmanager
    def _chatbox(role: str, avatar: str="🤖"):
        with st.chat_message(role, avatar=avatar):
            yield

    # ── (B0) OpenAI/Gemini 공통 페이로드 생성 ───────────────────────────────
    def _build_parts(mode: str, qtext: str, rag_ok: bool):
        # (요약) prompts + DECL_NO + 사용자의 질문 + 선택적 맥락/출처
        from src.prompt_modes import prepare_prompt  # 내부에서 prompts.yaml/폴백YAML 처리
        parts = prepare_prompt(
            mode=mode, question=qtext, use_context=bool(st.session_state.get("use_context", True)),
            context_turns=int(st.session_state.get("context_turns", 8)),
            context_max_chars=int(st.session_state.get("context_max_chars", 2500)),
            history=list(st.session_state.get("chat", [])),
            rag_ready=rag_ok,
            disclaimers_off=True
        )
        # 디클레이머 금지 규칙 삽입(시스템)
        parts["system"] = f"{parts.get('system','')}\n{DECL_NO}".strip()
        if show_prompt:
            with st.expander("프롬프트 미리보기", expanded=False):
                st.code(parts, language="json")
        return parts

# ===== [21] OPENAI 스트림 호출 헬퍼 (표준화/안정화) — START =====================
def _call_openai_stream(parts, out_slot, temperature: float, top_p: float | None, max_tokens: int):
    """
    OpenAI Chat Completions 스트리밍 호출 (표준화 버전)
    - SDK v1/구버전 혼선 방지: 모듈식 호출(openai.chat.completions.create)
    - 예외 분기 명확화: 인증/요금제/레이트리밋/연결/기타
    - 빈 응답 방지: 최종 텍스트가 공백이면 실패(폴백 신호 전달)
    """
    try:
        import os, openai

        # 1) 키 확인
        api_key = os.getenv("OPENAI_API_KEY") or getattr(st, "secrets", {}).get("OPENAI_API_KEY")
        if not api_key:
            return False, "OPENAI_API_KEY 미설정", "OpenAI"
        openai.api_key = api_key  # 모듈 전역에 키 설정

        # 2) 페이로드 구성
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        messages = [
            {"role": "system", "content": parts.get("system", "")},
            *parts.get("messages", []),
        ]
        kwargs = dict(
            model=model,
            messages=messages,
            stream=True,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
        if top_p is not None:
            kwargs["top_p"] = float(top_p)

        # 3) 스트리밍 루프
        buf: list[str] = []
        stream = openai.chat.completions.create(**kwargs)
        for event in stream:
            # v0.28 계열: event.choices[0].delta.content
            # v1 계열 래핑에서도 동일 경로가 노출됨(호환 레이어)
            try:
                delta = getattr(event.choices[0], "delta", None)
                chunk = getattr(delta, "content", None) if delta else None
            except Exception:
                chunk = None
            if chunk:
                buf.append(chunk)
                out_slot.markdown("".join(buf))

        text = "".join(buf).strip()
        if not text:
            # 스트림 중 내용이 전혀 없었다면 실패로 간주 (폴백 신호)
            return False, "OpenAI 빈 응답", "OpenAI"

        return True, text, "OpenAI"

    # 4) 예외 분기: SDK 버전에 따라 에러 클래스가 다를 수 있어 넓게 처리
    except Exception as e:
        # 가능한 한 의미 있는 에러 메시지로 매핑
        et = type(e).__name__
        msg = str(e) or et
        # 대표적인 경우들 키워드 스캔 (간이 매핑)
        if "RateLimit" in msg or "rate limit" in msg.lower():
            return False, f"RateLimitError: {msg}", "OpenAI"
        if "authentication" in msg.lower() or "api key" in msg.lower():
            return False, f"AuthenticationError: {msg}", "OpenAI"
        if "connection" in msg.lower() or "timeout" in msg.lower():
            return False, f"APIConnectionError: {msg}", "OpenAI"
        return False, f"{et}: {msg}", "OpenAI"
# ===== [21] OPENAI 스트림 호출 헬퍼 (표준화/안정화) — END =======================
# ===== [22] GEMINI 모델 팩토리 안정화 — START =================================
def _get_gemini_model(name: str):
    """
    Gemini 모델명 안전 매핑 + 최종 폴백까지 보장.
    - 입력: 사용자가 선택/환경변수로 준 모델명(대소문자/레거시/별칭 포함 가능)
    - 동작:
        1) API 키 확인 및 genai.configure
        2) 별칭/레거시 -> 정식 모델명으로 매핑
        3) 모델 생성 실패 시 1차 폴백(1.5-flash), 그마저 실패 시 마지막 폴백(1.5-pro)
    """
    import os
    import google.generativeai as genai

    # 0) 키 확인 + 설정
    api_key = os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY")
    if not api_key:
        # 호출부에서 ok=False로 처리하도록 예외를 명시적으로 올린다
        raise RuntimeError("GEMINI_API_KEY 미설정")
    genai.configure(api_key=api_key)

    # 1) 정규화
    raw = (name or "").strip()
    key = raw.lower().replace("models/", "")  # 일부 예전 문서의 'models/' prefix 제거

    # 2) 별칭/레거시 매핑
    #    - 최신 계열 우선: 2.0 > 1.5
    #    - 'pro','flash' 단독, 하이픈 유무 등 관대한 처리
    aliases = {
        # 2.0 계열 (있으면 이쪽 우선 사용)
        "2.0-flash": "gemini-2.0-flash",
        "2.0-pro":   "gemini-2.0-pro",
        "gemini-2.0-flash": "gemini-2.0-flash",
        "gemini-2.0-pro":   "gemini-2.0-pro",

        # 1.5 계열
        "1.5-flash": "gemini-1.5-flash",
        "1.5-pro":   "gemini-1.5-pro",
        "gemini-1.5-flash": "gemini-1.5-flash",
        "gemini-1.5-pro":   "gemini-1.5-pro",

        # 단축/별칭
        "flash": "gemini-1.5-flash",
        "pro":   "gemini-1.5-pro",

        # 레거시 명칭
        "gemini-pro": "gemini-1.0-pro",
        "1.0-pro":    "gemini-1.0-pro",
        "gemini-pro-vision": "gemini-1.0-pro-vision",
    }

    # 정식 이름으로 보정
    if key in aliases:
        canonical = aliases[key]
    elif key.startswith("gemini-"):
        canonical = key  # 이미 정식 이름일 가능성
    else:
        # 환경 기본값 → 없으면 flash
        canonical = os.getenv("GEMINI_MODEL_DEFAULT", "gemini-1.5-flash")

    # 3) 모델 생성 + 다단 폴백
    try:
        return genai.GenerativeModel(canonical)
    except Exception:
        # 1차 폴백: flash
        try:
            return genai.GenerativeModel("gemini-1.5-flash")
        except Exception:
            # 2차 폴백: pro
            return genai.GenerativeModel("gemini-1.5-pro")
# ===== [22] GEMINI 모델 팩토리 안정화 — END ===================================

    # ── (B2) Gemini 호환 — 스트림 호출 ───────────────────────────────────────
    def _call_gemini_stream(parts, out_slot, temperature: float, top_p: float | None, max_tokens: int):
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY")
            if not api_key: return False, "GEMINI_API_KEY 미설정", "Gemini"
            model_name = st.session_state.get("gemini_model_selection") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = _get_gemini_model(model_name)
            payload = _to_gemini_payload(parts)  # {"contents":[...], ...}
            gen_cfg = {"temperature": temperature, "max_output_tokens": max_tokens}
            if top_p is not None: gen_cfg["top_p"] = top_p
            stream = model.generate_content(payload["contents"], generation_config=gen_cfg, stream=True)
            buf = []
            for chunk in stream:
                if getattr(chunk, "text", None):
                    buf.append(chunk.text); out_slot.markdown("".join(buf))
            text = "".join(buf).strip()
            if not text:
                resp = model.generate_content(payload["contents"], generation_config=gen_cfg)
                text = getattr(resp, "text", "") or (
                    resp.candidates[0].content.parts[0].text if getattr(resp, "candidates", None) else ""
                )
            # ✅ 빈 응답이면 실패로 간주하여 폴백 가능하도록 반환
            if not (text and text.strip()):
                return False, "Gemini 빈 응답", "Gemini"
            return True, text, "Gemini"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}", "Gemini"

    # ── 과거 대화 렌더(채팅창 테두리 안) ──────────────────────────────────────
    with st.container(border=True):
        for msg in st.session_state["chat"]:
            if msg["role"] == "user":
                with _chatbox("user", avatar="🧑"):
                    st.markdown(msg["text"])
            else:
                provider_emoji = "🟣" if msg.get("provider") == "Gemini" else "🔵"
                with _chatbox("assistant", avatar=provider_emoji):
                    st.markdown(msg["text"])

    # ── 입력(Enter 전송 & 자동 비우기): 내 말풍선 즉시 렌더 ────────────────────
    question = st.chat_input("질문을 입력하세요")
    if (question or "").strip():
        qtext = question.strip()
        with _chatbox("user", avatar="🧑"): st.markdown(qtext)
        st.session_state["chat"].append({ "id": _new_id(), "role": "user", "text": qtext, "ts": _ts() })

        # 프롬프트 생성(+ 맥락/출처)
        try:
            parts = _build_parts(st.session_state.get("qa_mode_radio","문법설명"), qtext, rag_ready)
        except Exception as e:
            with _chatbox("assistant", avatar="⚠️"):
                st.error(f"프롬프트 생성 실패: {type(e).__name__}: {e}")
                st.code(traceback.format_exc(), language="python")
            return

        # 1차/2차 파라미터
        prim_temp = float(st.session_state.get("primary_temperature", 0.3))
        supp_temp = float(st.session_state.get("supp_temperature", 0.7))
        max_toks = 800

        # 1차 스트리밍
        lead = st.session_state.get("lead_provider", "Gemini")
        with _chatbox("assistant", avatar="🤖"):
            st.caption(f"_{lead} 생성 중…_")
            out_slot = st.empty()
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

            # ✅ 성공 판정 강화: 공백 응답 방지
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
                # ✅ 폴백 시도: 리드 실패 시 반대 모델로 재시도
                fallback_ok, fallback_out, fallback_provider = False, None, lead
                if lead == "Gemini" and have_openai_lib and has_openai_key:
                    st.caption("_Gemini 실패 → OpenAI로 폴백 시도_")
                    fallback_ok, fallback_out, fallback_provider = _call_openai_stream(parts, out_slot, prim_temp, None, max_toks)
                elif lead != "Gemini" and have_gemini_lib and has_gemini_key:
                    st.caption("_OpenAI 실패 → Gemini로 폴백 시도_")
                    fallback_ok, fallback_out, fallback_provider = _call_gemini_stream(parts, out_slot, prim_temp, None, max_toks)

                if fallback_ok and (fallback_out and fallback_out.strip()):
                    aid = _new_id()
                    st.session_state["chat"].append({
                        "id": aid, "role": "assistant", "provider": fallback_provider,
                        "kind": "primary", "text": fallback_out, "ts": _ts()
                    })
                    if bool(st.session_state.get("dual_generate", False)):
                        st.session_state["_supplement_for_msg_id"] = aid
                    st.rerun()
                else:
                    st.error(f"1차 생성 실패: {(fallback_out or out) or '원인 불명'}")

    # ── 보충 설명 실행(예약된 경우; 차별화 프롬프트 + 유사도 가드) ───────────────
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
                # 2차 프롬프트: 더 창의적이고, 유사도/중복 방지
                parts2 = _build_parts(st.session_state.get("qa_mode_radio","문법설명"), base_q, rag_ready)
                # 2차 생성 파라미터
                supp_temp2 = float(st.session_state.get("supp_temperature", 0.7))
                supp_top_p2 = float(st.session_state.get("supp_top_p", 0.95))
                other = "OpenAI" if primary.get("provider") == "Gemini" else "Gemini"

                def _gen_supp_retry(p):
                    # 2차는 기본적으로 '다른 모델'을 시도
                    out_slot = st.empty()
                    if other == "OpenAI":
                        if have_openai_lib and has_openai_key:
                            return _call_openai_stream(p, out_slot, supp_temp2, supp_top_p2, max_toks)
                        return False, "OpenAI 사용 불가(패키지 또는 키 누락)", other
                    else:
                        if have_gemini_lib and has_gemini_key:
                            return _call_gemini_stream(p, out_slot, supp_temp2, supp_top_p2, max_toks)
                        return False, "Gemini 사용 불가(패키지 또는 키 누락)", other

                ok2, out2, _ = _gen_supp_retry(parts2)

                # ── 유사도 가드(필요 시 자동 재생성 1회) ───────────────────────────
                if ok2 and out2 and primary["text"]:
                    sim = difflib.SequenceMatcher(a=primary["text"], b=out2).ratio()
                    if sim >= 0.85:
                        # 너무 비슷하면 톤/관점 분화 재시도
                        parts2b = parts2.copy()
                        # (간단) 사용자 메시지에 "다른 관점/예시" 요청 추가
                        parts2b["messages"] = parts2["messages"] + [
                            {"role":"user", "content":"같은 내용을 다른 관점/예시로, 초등학생도 이해할 수 있게 다시 설명해줘."}
                        ]
                        def _gen_supp_retry2(p):
                            out_slot = st.empty()
                            if other == "OpenAI":
                                if have_openai_lib and has_openai_key:
                                    return _call_openai_stream(p, out_slot, supp_temp2, supp_top_p2, max_toks)
                                return False, "OpenAI 사용 불가(패키지 또는 키 누락)", other
                            else:
                                if have_gemini_lib and has_gemini_key:
                                    return _call_gemini_stream(p, out_slot, supp_temp2, supp_top_p2, max_toks)
                                return False, "Gemini 사용 불가(패키지 또는 키 누락)", other
                        ok2b, out2b, _ = _gen_supp_retry(parts2)
                        if ok2b and out2b: out2 = out2b  # 더 나은 재작성으로 교체

            except Exception as e:
                with _chatbox("assistant", avatar="⚠️"):
                    st.error(f"보충 생성 실패: {type(e).__name__}: {e}")
                    st.code(traceback.format_exc(), language="python")
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

# ===== [06] END ===============================================================

# ===== [07] MAIN — 부팅 훅 + 프롬프트 동기화 연결 ============================

def _boot_and_render():
    """
    앱 부팅 시점에 Google Drive의 prompts.yaml을 최신으로 동기화(옵션)하고
    이후 기존 UI 렌더링 흐름(_render_qa_panel 등)으로 진입합니다.
    - 토글: AUTO_SYNC_PROMPTS = true/1/yes/on (env 또는 st.secrets)
    - 성공 시: st.session_state['prompts_path'] 에 로컬 경로(~/.maic/prompts/prompts.yaml) 저장
    """
    import os

    # 0) 프롬프트 동기화 토글 읽기 (env 우선, 없으면 st.secrets)
    def _to_bool(x):
        return str(x).strip().lower() in ("1", "true", "yes", "y", "on")

    auto_env = os.getenv("AUTO_SYNC_PROMPTS")
    auto_sec = getattr(st, "secrets", {}).get("AUTO_SYNC_PROMPTS")
    auto_sync = _to_bool(auto_env) if auto_env is not None else _to_bool(auto_sec)

    local_prompts_path = os.path.expanduser("~/.maic/prompts.yaml")

    # 1) 동기화 시도 (토글이 켜진 경우에만)
    if auto_sync:
        try:
            ok, msg = sync_prompts_from_drive(local_path=local_prompts_path, verbose=True)
            if ok:
                st.session_state["prompts_path"] = local_prompts_path
                st.toast("프롬프트 동기화 완료 ✅")
            else:
                st.session_state.setdefault("prompts_path", local_prompts_path)
                st.warning(f"프롬프트 동기화 실패: {msg}")
        except Exception as e:
            st.session_state.setdefault("prompts_path", local_prompts_path)
            st.warning(f"프롬프트 동기화 예외: {type(e).__name__}: {e}")
    else:
        # 토글이 꺼져 있으면 로컬 기본 경로만 기록 (없으면 이후 prepare_prompt에서 기존 경로 사용)
        st.session_state.setdefault("prompts_path", local_prompts_path)

    # 2) (선택) 헤더 렌더 시도 — 모듈 유무에 따라 안전 호출
    try:
        if "render_header" in globals():
            render_header()
    except Exception:
        pass

    # 3) 기존 질문/답변 패널 진입 (우리가 앞 단계에서 이미 안정화한 구획)
    _render_qa_panel()


# 모듈 로딩 시 즉시 진입 (Streamlit은 스크립트 실행형이므로 __main__ 가드 불필요)
_boot_and_render()

# ===== [07] MAIN — END =======================================================


# ===== [23] PROMPTS 동기화 (Google Drive → Local) — START =====================
def sync_prompts_from_drive(
    *,
    local_path: str = os.path.expanduser("~/.maic/prompts/prompts.yaml"),
    file_name: str = "prompts.yaml",
    prefer_folder_name: str | None = "prompts",   # 폴더명이 다르면 None 유지(전역 검색)
    verbose: bool = True,
) -> tuple[bool, str]:
    """
    Google Drive에서 최신 'prompts.yaml'을 찾아 로컬로 저장.
    - Service Account 키는 st.secrets 또는 환경변수에서 로드
    - 우선순위: (1) prefer_folder_name 내 최신 -> (2) 전체 Drive에서 최신
    - 반환: (ok, message)

    필요 시 다음 시크릿 키 사용(예시):
      st.secrets['gcp_service_account']  # 서비스계정 JSON (3중 작은따옴표 템플릿 권장)
    """
    try:
        import io
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        # 0) 자격 증명 불러오기
        sa_info = (getattr(st, "secrets", {}).get("gcp_service_account")
                   or os.getenv("GCP_SERVICE_ACCOUNT_JSON"))
        if not sa_info:
            return False, "gcp_service_account 시크릿/환경변수 누락"

        if isinstance(sa_info, str):
            # 문자열(JSON) → dict
            import json as _json
            sa_info = _json.loads(sa_info)

        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        # 1) 검색 쿼리 구성
        #   - 폴더명 힌트가 있으면 그 폴더를 먼저 찾고, 안 되면 전역 검색
        file_id: str | None = None

        def _search_latest_in_folder_id(folder_id: str) -> str | None:
            q = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
            res = drive.files().list(q=q, orderBy="modifiedTime desc", pageSize=1,
                                     fields="files(id, name, modifiedTime)").execute()
            arr = res.get("files", [])
            return arr[0]["id"] if arr else None

        # 1-a) 폴더명으로 폴더 ID 추정 → 그 안에서 검색
        if prefer_folder_name:
            q_folder = f"mimeType = 'application/vnd.google-apps.folder' and name = '{prefer_folder_name}' and trashed = false"
            r = drive.files().list(q=q_folder, fields="files(id,name)", pageSize=5).execute()
            for f in r.get("files", []):
                fid = _search_latest_in_folder_id(f["id"])
                if fid:
                    file_id = fid
                    break

        # 1-b) 폴더 힌트로 못 찾으면 전역에서 파일명 최신 검색
        if not file_id:
            q_any = f"name = '{file_name}' and trashed = false"
            r = drive.files().list(q=q_any, orderBy="modifiedTime desc", pageSize=1,
                                   fields="files(id, name, modifiedTime, parents)").execute()
            arr = r.get("files", [])
            if arr:
                file_id = arr[0]["id"]

        if not file_id:
            return False, f"Drive에서 '{file_name}'을 찾지 못했습니다"

        # 2) 다운로드
        req = drive.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        # 3) 저장 경로 보장 후 기록
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(buf.getvalue())

        if verbose:
            st.toast(f"prompts.yaml 동기화 완료 → {local_path}")

        return True, f"다운로드 성공: {local_path}"

    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
# ===== [23] PROMPTS 동기화 (Google Drive → Local) — END =======================
