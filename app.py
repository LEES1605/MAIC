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

def _force_persist_dir() -> str:
    """
    내부 모듈들이 다른 경로를 보더라도, 런타임에서 ~/.maic/persist 로 강제 통일.
    - src.rag.index_build / rag.index_build 의 PERSIST_DIR 속성 주입
    - 환경변수 MAIC_PERSIST_DIR 도 세팅(내부 코드가 읽을 수 있음)
    """
    import importlib, os
    target = Path.home() / ".maic" / "persist"
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

def _has_local_index_files() -> bool:
    """로컬 PERSIST_DIR 안에 .ready 또는 chunks.jsonl 이 있는지 신호만 확인."""
    import importlib
    from pathlib import Path as _P
    try:
        _mod = importlib.import_module("src.rag.index_build")
        _PERSIST_DIR = getattr(_mod, "PERSIST_DIR", _P.home() / ".maic" / "persist")
    except Exception:
        _PERSIST_DIR = _P.home() / ".maic" / "persist"
    chunks_ok = (_PERSIST_DIR / "chunks.jsonl").exists()
    ready_ok  = (_PERSIST_DIR / ".ready").exists()
    return bool(chunks_ok or ready_ok)

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

    st.session_state.setdefault("_admin_expand_all", True)  # 기본: 펼침
    st.markdown("### 관리자 도구")
    st.session_state["_admin_expand_all"] = st.toggle(
        "📂 관리자 패널 모두 펼치기", value=bool(st.session_state["_admin_expand_all"]),
        help="켜면 아래 관리자용 패널들이 모두 펼쳐져 보입니다. 끄면 모두 접힙니다.",
        key="_admin_expand_all"
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


# ===== [05A] 자료 최적화/백업 패널 ==========================================
def render_brain_prep_main():
    """
    인덱스(두뇌) 최적화/복구/백업을 위한 관리자 패널
    - 강제 부착, 최신 백업 복원, 인덱스 재빌드, 백업 생성/업로드
    - 모든 동작은 [05B] 타임라인 로그(_log_attach)와 연계
    """
    import os
    import json
    import importlib  # ✅ NameError 방지: 함수 내부 임포트
    from pathlib import Path
    from datetime import datetime

    # 관리자 가드
    if not (
        st.session_state.get("is_admin")
        or st.session_state.get("admin_mode")
        or st.session_state.get("role") == "admin"
        or st.session_state.get("mode") == "admin"
    ):
        return

    def _log(step: str, **kw):
        try:
            if "_log_attach" in globals() and callable(globals()["_log_attach"]):
                globals()["_log_attach"](step, **kw)
        except Exception:
            pass

    # 기본 경로 추정
    PERSIST_DIR = Path.home() / ".maic" / "persist"
    BACKUP_DIR  = Path.home() / ".maic" / "backup"
    QUALITY_REPORT_PATH = Path.home() / ".maic" / "quality_report.json"

    # src.rag.index_build 의 경로 상수/함수들 (있으면 사용)
    idx_mod = None
    try:
        idx_mod = importlib.import_module("src.rag.index_build")
        PERSIST_DIR = getattr(idx_mod, "PERSIST_DIR", PERSIST_DIR)
        BACKUP_DIR  = getattr(idx_mod, "BACKUP_DIR",  BACKUP_DIR)
        QUALITY_REPORT_PATH = getattr(idx_mod, "QUALITY_REPORT_PATH", QUALITY_REPORT_PATH)
    except Exception as e:
        # 모듈이 없어도 패널은 동작(버튼 중 일부만 제한됨)
        _log("index_module_import_warn", error=f"{type(e).__name__}: {e}")

    # 관련 함수 핸들(없으면 None)
    precheck_fn   = globals().get("precheck_build_needed") or globals().get("quick_precheck")
    build_fn      = globals().get("build_index_with_checkpoint")
    restore_fn    = globals().get("restore_latest_backup_to_local")
    backup_fn     = globals().get("_make_and_upload_backup_zip")
    attach_fn     = globals().get("_attach_from_local")
    auto_restore  = globals().get("_auto_attach_or_restore_silently")
    force_persist = globals().get("_force_persist_dir")

    st.subheader("자료 최적화 · 백업", anchor=False)

    # 경로/상태 요약
    with st.container(border=True):
        st.markdown("### 경로 및 상태")
        st.write("• Persist 디렉터리:", f"`{Path(PERSIST_DIR)}`")
        st.write("• Backup 디렉터리:", f"`{Path(BACKUP_DIR)}`")
        qr_exists = Path(QUALITY_REPORT_PATH).exists()
        st.markdown(f"• 품질 리포트(quality_report.json): {'✅ 있음' if qr_exists else '❌ 없음'} "
                    f"(`{Path(QUALITY_REPORT_PATH)}`)")

        # 사전점검(precheck)
        if callable(precheck_fn):
            try:
                need = precheck_fn()  # bool 예상
                badge = "🟡 재빌드 권장" if need else "🟢 양호"
                st.write("• 사전점검 결과:", badge)
            except Exception as e:
                st.write("• 사전점검 결과: ⚠ 오류",
                         f"(`{type(e).__name__}: {e}`)")
        else:
            st.caption("사전점검 함수가 없어 건너뜁니다(선택 기능).")

    # 액션 버튼들
    col1, col2, col3, col4 = st.columns([1,1,1,1])
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

    with col3:
        if st.button("♻ 인덱스 재빌드(최소 옵션)", use_container_width=True, disabled=not callable(build_fn)):
            with st.status("인덱스 재빌드 중…", state="running") as s:
                try:
                    if not callable(build_fn):
                        s.update(label="빌더 없음", state="error")
                        st.error("build_index_with_checkpoint 함수가 없습니다.")
                        _log("rebuild_skip", reason="build_fn_not_callable")
                    else:
                        persist_dir = str(PERSIST_DIR)
                        _log("rebuild_try", persist_dir=persist_dir)
                        try:
                            build_fn(
                                update_pct=lambda *_a, **_k: None,
                                update_msg=lambda *_a, **_k: None,
                                gdrive_folder_id="",
                                gcp_creds={},
                                persist_dir=persist_dir,
                                remote_manifest={},
                            )
                        except TypeError:
                            # 시그니처가 다른 배포본 지원
                            build_fn()
                        _log("rebuild_ok")
                        # 재부착
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
# ===== [05A] END =============================================================


# ===== [05B] 간단 진단 패널(선택) ===========================================
def render_tag_diagnostics():
    """
    자동 복구 상태, rag_index 경로, 품질 리포트 등 간단 요약 +
    ✅ attach/restore 타임라인, ✅ BOOT-WARN 경고, ✅ 임포트 오류(_import_errors)까지
    한 화면에서 확인하는 진단 패널.
    + ✅ 로그 복사/다운로드(텍스트 병합본)
    """
    import importlib, json as _json
    from datetime import datetime

    # 기본 경로
    PERSIST_DIR = Path.home() / ".maic" / "persist"
    BACKUP_DIR = Path.home() / ".maic" / "backup"
    QUALITY_REPORT_PATH = Path.home() / ".maic" / "quality_report.json"

    # src.rag.index_build 값 우선
    try:
        _m = importlib.import_module("src.rag.index_build")
        PERSIST_DIR = getattr(_m, "PERSIST_DIR", PERSIST_DIR)
        BACKUP_DIR = getattr(_m, "BACKUP_DIR", BACKUP_DIR)
        QUALITY_REPORT_PATH = getattr(_m, "QUALITY_REPORT_PATH", QUALITY_REPORT_PATH)
    except Exception:
        _m = None

    st.subheader("진단(간단)", anchor=False)

    # 수집 데이터
    boot_warns = globals().get("_BOOT_WARNINGS") or []
    import_errs = globals().get("_import_errors") or []
    logs = st.session_state.get("_attach_log") or []
    auto_info = st.session_state.get("_auto_restore_last")

    # ✅ A) BOOT-WARN 경고 묶음
    with st.container(border=True):
        st.markdown("### 부팅 경고(BOOT-WARN)")
        if not boot_warns:
            st.caption("부팅 경고 없음.")
        else:
            for i, msg in enumerate(boot_warns, 1):
                with st.expander(f"경고 {i}", expanded=(i == 1)):
                    st.markdown(msg)

    # ✅ B) 임포트 오류 원문(_import_errors)
    with st.container(border=True):
        st.markdown("### 임포트 오류 원문")
        if not import_errs:
            st.caption("기록된 임포트 오류 없음.")
        else:
            for i, err in enumerate(import_errs, 1):
                st.write(f"• `{err}`")

    # ✅ C) Attach/Restore 타임라인 로그(최근 100개 역순) + 복사/다운로드
    with st.container(border=True):
        st.markdown("### Attach/Restore 타임라인")
        colL, colR = st.columns([0.75, 0.25])
        with colR:
            if st.button("🧹 로그 비우기", use_container_width=True):
                st.session_state["_attach_log"] = []
                st.toast("로그를 비웠습니다.")
                st.experimental_rerun()

        if not logs:
            st.caption("아직 기록된 로그가 없습니다. 자동 연결 또는 복구를 수행하면 여기에 단계별 로그가 표시됩니다.")
        else:
            # 표시
            for item in reversed(logs[-100:]):
                ts = item.get("ts")
                step = item.get("step")
                rest = {k: v for k, v in item.items() if k not in ("ts", "step")}
                st.write(f"• **{ts}** — `{step}`", (f" · `{_json.dumps(rest, ensure_ascii=False)}`" if rest else ""))

            # ✅ 병합 텍스트(복사용) + 다운로드
            merged_lines = []
            for item in logs:
                ts = item.get("ts", "")
                step = item.get("step", "")
                rest = {k: v for k, v in item.items() if k not in ("ts", "step")}
                merged_lines.append(f"{ts}\t{step}\t{_json.dumps(rest, ensure_ascii=False)}")
            merged_txt = "\n".join(merged_lines) if merged_lines else "(no logs)"

            st.markdown("---")
            st.caption("▼ 로그 복사/다운로드")
            # st.code 는 자체 복사 버튼을 제공함
            st.code(merged_txt, language="text")
            st.download_button(
                "⬇ 로그 텍스트 다운로드",
                data=merged_txt.encode("utf-8"),
                file_name="maic_attach_logs.txt",
                mime="text/plain",
                use_container_width=True,
            )

    # ✅ D) 자동 복구 상태 스냅샷
    with st.container(border=True):
        st.markdown("### 자동 복구 상태")
        if not auto_info:
            st.caption("아직 자동 복구 시도 기록이 없습니다.")
        else:
            st.code(_json.dumps(auto_info, ensure_ascii=False, indent=2), language="json")

    # ✅ E) rag_index Persist 경로 추정
    with st.container(border=True):
        st.markdown("### rag_index Persist 경로 추정")
        rag = st.session_state.get("rag_index")
        if rag is None:
            st.caption("rag_index 객체가 세션에 없습니다.")
        else:
            cand = None
            for attr in ("persist_dir", "storage_context", "vector_store", "index_struct"):
                try:
                    val = getattr(rag, attr, None)
                    if val:
                        cand = str(val)
                        break
                except Exception:
                    continue
            st.write("🔍 rag_index 내부 persist_dir/유사 속성:", cand or "(발견되지 않음)")

    # ✅ F) 품질 리포트 존재 여부
    qr_exists = QUALITY_REPORT_PATH.exists()
    qr_badge = "✅ 있음" if qr_exists else "❌ 없음"
    st.markdown(f"- **품질 리포트(quality_report.json)**: {qr_badge}  (`{QUALITY_REPORT_PATH.as_posix()}`)")
# ===== [05B] END ===========================================================



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
        ss.get("rag_index"),
        last.get("final_attach"),
    )
    return any(bool(x) for x in flags)
# ===== [PATCH-BRAIN-HELPER] END ==============================================

# ===== [06] 질문/답변 패널 — 프롬프트 연동 & LLM 호출(선두→보충) ===============
def render_qa_panel():
    """
    학생 질문 → (선두 모델) 1차 답변 스트리밍 → [보충 설명] 버튼으로 2차 모델 호출
    - 선두 모델: 기본 Gemini, 관리자에서 OpenAI로 변경 가능
    - '두 모델 모두 자동 생성' 토글: 켜면 1차 후 2차도 자동 호출
    - 스트리밍 출력 + 세션 캐시 + Gemini 모델 선택(관리자) + 생성 설정 슬라이더 유지
    - 출처 규칙:
        · 근거 발견: 문서명/소단원/페이지 등 구체 표기
        · 근거 미발견 또는 RAG 미사용: 'AI지식 활용' 한 줄
    - 디클레이머 금지: '일반적인 지식...' 등의 포괄적 문구 출력 금지
    """
    import os
    import traceback, importlib.util

    # 0) 표시할 모드 집합(관리자 설정 반영)
    try:
        modes_enabled = _get_enabled_modes_unified()
    except Exception:
        modes_enabled = {"Grammar": True, "Sentence": True, "Passage": True}

    label_order = [("문법설명","Grammar"), ("문장구조분석","Sentence"), ("지문분석","Passage")]
    labels = [ko for ko,_ in label_order if (
        (ko == "문법설명"      and modes_enabled.get("Grammar",  True)) or
        (ko == "문장구조분석"  and modes_enabled.get("Sentence", True)) or
        (ko == "지문분석"      and modes_enabled.get("Passage",  True))
    )]
    if not labels:
        st.info("표시할 질문 모드가 없습니다. 관리자에서 한 개 이상 켜 주세요.")
        return

    with st.container(border=True):
        st.subheader("질문/답변")

        # 두뇌 상태 배지
        rag_ready = _is_attached_session()
        if rag_ready:
            st.caption("🧠 두뇌 상태: **연결됨** · 업로드 자료(RAG) 사용 가능")
        else:
            st.caption("🧠 두뇌 상태: **미연결** · 현재 응답은 **LLM-only(자료 미참조)** 입니다")

        colm, colq = st.columns([1,3])
        with colm:
            sel_mode = st.radio("모드", options=labels, horizontal=True, key="qa_mode_radio")

            # 관리자 가드
            is_admin = (
                st.session_state.get("is_admin")
                or st.session_state.get("admin_mode")
                or st.session_state.get("role") == "admin"
                or st.session_state.get("mode") == "admin"
            )

            # ── 선두 모델 / 듀얼 토글(관리자) ───────────────────────────────────
            st.session_state.setdefault("lead_provider", "Gemini")  # "Gemini" | "OpenAI"
            st.session_state.setdefault("dual_generate", False)     # 두 모델 모두 자동 생성
            if is_admin:
                st.markdown("---")
                st.caption("응답 전략(관리자)")
                st.session_state["lead_provider"] = st.radio(
                    "선두 모델", options=["Gemini", "OpenAI"],
                    index=(0 if st.session_state["lead_provider"] == "Gemini" else 1),
                    key="lead_provider_radio"
                )
                st.session_state["dual_generate"] = st.toggle(
                    "두 모델 모두 자동 생성(비용↑)", value=bool(st.session_state["dual_generate"]),
                    help="켜면 선두 모델 스트리밍 후 다른 모델도 자동으로 생성합니다."
                )

            # ── Gemini 모델 선택(관리자) ───────────────────────────────────────
            if is_admin:
                st.markdown("---")
                st.caption("Gemini 모델 선택(관리자)")
                default_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                st.session_state.setdefault("gemini_model_selection", default_model)
                st.session_state["gemini_model_selection"] = st.radio(
                    "Gemini 모델", options=["gemini-1.5-flash", "gemini-1.5-pro"],
                    index=0 if str(default_model).endswith("flash") else 1, key="gemini_model_radio"
                )

            # ── 생성 설정(temperature / max_tokens) ────────────────────────────
            if is_admin:
                st.markdown("---")
                st.caption("생성 설정(관리자)")
                st.session_state.setdefault("gen_temperature", 0.3)
                st.session_state.setdefault("gen_max_tokens", 700)
                st.session_state["gen_temperature"] = st.slider(
                    "Temperature (창의성)", min_value=0.0, max_value=1.0,
                    value=float(st.session_state["gen_temperature"]), step=0.1
                )
                st.session_state["gen_max_tokens"] = st.slider(
                    "Max Tokens (응답 길이 상한)", min_value=100, max_value=2000,
                    value=int(st.session_state["gen_max_tokens"]), step=50
                )

        with colq:
            question = st.text_area("질문을 입력하세요", height=96, placeholder="예: I had my bike repaired.")

        colA, colB = st.columns([1,1])
        go = colA.button("답변 생성", use_container_width=True)
        show_prompt = colB.toggle("프롬프트 미리보기", value=False)

    if not go:
        return

    # 1) 프롬프트 빌드 (+ 규칙 주입)
    try:
        from src.prompt_modes import build_prompt, to_openai, to_gemini
        parts = build_prompt(sel_mode, question or "", lang="ko", extras={
            "level":  st.session_state.get("student_level"),
            "tone":   "encouraging",
        })

        # (NEW) 출처 규칙/디클레이머 금지
        rules = []
        if rag_ready:
            rules.append(
                "출처 표기 규칙: 업로드 자료에서 근거를 찾으면 문서명/소단원명/페이지 등 구체적으로 표기합니다. "
                "근거를 찾지 못했다면 'AI지식 활용'이라고만 간단히 표기합니다."
            )
        else:
            rules.append(
                "출처 표기 규칙: 현재 업로드 자료(RAG)를 사용하지 못하므로, 답변 맨 끝에 'AI지식 활용'이라고만 표기합니다."
            )
        rules.append(
            "출처/근거 표기는 답변 맨 끝에 '근거/출처: '로 시작하는 한 줄로만 작성하십시오. 여러 개면 세미콜론(;)으로 구분합니다."
        )
        rules.append("금지: '일반적인 지식/일반 학습자료' 등에 기반했다는 포괄적 디클레이머를 출력하지 마십시오.")
        if parts and getattr(parts, "system", None):
            parts.system = parts.system + "\n\n" + "\n".join(rules)

    except Exception as e:
        st.error(f"프롬프트 생성 실패: {type(e).__name__}: {e}")
        st.code(traceback.format_exc(), language="python")
        return

    if show_prompt:
        with st.expander("프롬프트(미리보기)", expanded=True):
            st.markdown("**System:**")
            st.code(parts.system, language="markdown")
            st.markdown("**User:**")
            st.code(parts.user, language="markdown")
            if getattr(parts, "provider_kwargs", None):
                st.caption(f"provider_kwargs: {parts.provider_kwargs}")

    # 2) 라이브러리/키 상태
    have_openai_lib  = importlib.util.find_spec("openai") is not None
    have_gemini_lib  = importlib.util.find_spec("google.generativeai") is not None
    has_openai_key   = bool(os.getenv("OPENAI_API_KEY") or getattr(st, "secrets", {}).get("OPENAI_API_KEY"))
    has_gemini_key   = bool(os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY"))

    # 3) 세션 캐시
    st.session_state.setdefault("_openai_client_cache", None)
    st.session_state.setdefault("_gemini_model_cache", {})  # {model_name: genai.GenerativeModel}
    st.session_state.setdefault("_answer_primary", None)
    st.session_state.setdefault("_answer_secondary", None)

    def _get_openai_client():
        if st.session_state["_openai_client_cache"] is None:
            from openai import OpenAI
            st.session_state["_openai_client_cache"] = OpenAI()
        return st.session_state["_openai_client_cache"]

    def _get_gemini_model(model_name: str):
        cache = st.session_state["_gemini_model_cache"]
        if model_name in cache:
            return cache[model_name]
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name)
        cache[model_name] = model
        return model

    # 4) 관리자 설정값 읽기
    temp = float(st.session_state.get("gen_temperature", 0.3))
    max_toks = int(st.session_state.get("gen_max_tokens", 700))
    if not (0.0 <= temp <= 1.0): temp = 0.3
    if not (100 <= max_toks <= 2000): max_toks = 700

    # 5) 스트리밍 출력 슬롯
    st.markdown("#### 1차 답변")
    primary_out = st.empty()

    # 6) LLM 호출 구현(스트리밍)
    def _call_openai_stream(p, out_slot):
        try:
            client = _get_openai_client()
            payload = to_openai(p)  # {"messages":[...], ...}
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            stream = client.chat.completions.create(
                model=model, stream=True, temperature=temp, max_tokens=max_toks, **payload
            )
            buf = []
            for event in stream:
                delta = getattr(event.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    buf.append(delta.content)
                    out_slot.markdown("".join(buf))
            text = "".join(buf).strip()
            return True, (text if text else None)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def _call_gemini_stream(p, out_slot):
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY")
            if not api_key:
                return False, "GEMINI_API_KEY 미설정"
            model_name = st.session_state.get("gemini_model_selection") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = _get_gemini_model(model_name)
            payload = to_gemini(p)  # {"contents":[...], ...}
            gen_cfg = {"temperature": temp, "max_output_tokens": max_toks}
            stream = model.generate_content(payload["contents"], generation_config=gen_cfg, stream=True)
            buf = []
            for chunk in stream:
                if getattr(chunk, "text", None):
                    buf.append(chunk.text)
                    out_slot.markdown("".join(buf))
            text = "".join(buf).strip()
            if not text:
                resp = model.generate_content(payload["contents"], generation_config=gen_cfg)
                text = getattr(resp, "text", "") or (
                    resp.candidates[0].content.parts[0].text
                    if getattr(resp, "candidates", None) else ""
                )
            return True, (text if text else None)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    # 7) 선두 모델 실행
    lead = st.session_state["lead_provider"]
    with st.status(f"{lead}로 1차 답변 생성 중…", state="running") as s1:
        ok1, out1, provider1 = False, None, lead
        if lead == "Gemini":
            if have_gemini_lib and has_gemini_key:
                ok1, out1 = _call_gemini_stream(parts, primary_out)
            elif have_openai_lib and has_openai_key:
                # 키/라이브러리 부족 시 OpenAI로 자동 대체
                provider1 = "OpenAI"
                ok1, out1 = _call_openai_stream(parts, primary_out)
            else:
                ok1, out1 = False, "Gemini/OpenAI 사용 불가(패키지 또는 키 누락)"
        else:  # lead == "OpenAI"
            if have_openai_lib and has_openai_key:
                ok1, out1 = _call_openai_stream(parts, primary_out)
            elif have_gemini_lib and has_gemini_key:
                provider1 = "Gemini"
                ok1, out1 = _call_gemini_stream(parts, primary_out)
            else:
                ok1, out1 = False, "OpenAI/Gemini 사용 불가(패키지 또는 키 누락)"

        if ok1 and (out1 is not None):
            s1.update(label=f"{provider1} 1차 응답 수신 ✅", state="complete")
        else:
            s1.update(label="1차 모델 호출 실패 ❌", state="error")
            st.error(f"1차 모델 실패: {out1 or '원인 불명'}")
            return

    st.session_state["_answer_primary"] = out1

    # 8) 보충 설명(2차) — 버튼/자동 토글
    other = "OpenAI" if provider1 == "Gemini" else "Gemini"
    st.markdown("---")
    st.markdown("#### 보충 설명")
    colS1, colS2 = st.columns([1,1])
    auto_dual = bool(st.session_state.get("dual_generate", False))
    run_secondary = False
    with colS1:
        if not auto_dual:
            run_secondary = st.button(f"💬 {other}로 보충 설명 보기", use_container_width=True)
    with colS2:
        if auto_dual:
            st.info("관리자 설정: 두 모델 모두 자동 생성 모드입니다.")
            run_secondary = True

    # 9) 2차 호출을 위한 보조 프롬프트(요약/차이점 지시 추가)
    def _make_secondary_parts(primary_text: str):
        # 같은 parts를 복사해 '보충 설명' 지시를 사용자 프롬프트에 덧붙입니다.
        import copy
        p2 = copy.deepcopy(parts)
        # 지시: 요점 3줄 + 상세 + 차이점 3개 이내, 동일 출처 규칙 준수
        extra = (
            "\n\n[보충 설명 지시]\n"
            "학생이 이해하기 쉽게 다음 형식으로 응답하세요:\n"
            "1) 요점 3줄 정리\n"
            "2) 상세 설명\n"
            "3) 앞선 답변과의 차이점/추가 포인트 (최대 3개)\n"
            "출처 규칙은 동일하게 따르십시오.\n"
        )
        # 앞선 1차 응답의 일부를 힌트로 제공(너무 길면 절단)
        prim = (primary_text or "")[:3000]
        p2.user = f"{p2.user}\n\n[참고: 앞선 1차 응답 요지]\n{prim}\n"
        p2.user = p2.user + extra
        return p2

    # 10) 2차 호출 실행 및 출력
    if run_secondary:
        with st.expander(f"{other} 보충 설명", expanded=True):
            secondary_out = st.empty()
            p2 = _make_secondary_parts(st.session_state["_answer_primary"] or "")
            with st.status(f"{other}로 보충 설명 생성 중…", state="running") as s2:
                ok2, out2 = False, None
                if other == "OpenAI":
                    if have_openai_lib and has_openai_key:
                        ok2, out2 = _call_openai_stream(p2, secondary_out)
                    else:
                        ok2, out2 = False, "OpenAI 사용 불가(패키지 또는 키 누락)"
                else:  # other == "Gemini"
                    if have_gemini_lib and has_gemini_key:
                        ok2, out2 = _call_gemini_stream(p2, secondary_out)
                    else:
                        ok2, out2 = False, "Gemini 사용 불가(패키지 또는 키 누락)"

                if ok2 and (out2 is not None):
                    s2.update(label=f"{other} 보충 응답 수신 ✅", state="complete")
                else:
                    s2.update(label="보충 설명 실패 ❌", state="error")
                    st.error(f"보충 설명 실패: {out2 or '원인 불명'}")
            st.session_state["_answer_secondary"] = out2
# ===== [06] END ===============================================================


# ===== [07] MAIN — 오케스트레이터 ============================================
def _render_title_with_status():
    """상단 헤더: 제목 + 상태배지 + FAQ 토글"""
    try:
        status = get_index_status()  # 'ready' | 'pending' | 'missing'
    except Exception:
        status = "missing"
    is_admin = bool(st.session_state.get("is_admin", False))

    if status == "ready":
        badge_html = ("<span class='ui-pill ui-pill-green'>🟢 두뇌 준비됨</span>" if is_admin
                      else "<span class='ui-pill ui-pill-green'>🟢 LEES AI 선생님이 답변준비 완료</span>")
    elif status == "pending":
        badge_html = "<span class='ui-pill'>🟡 연결 대기</span>"
    else:
        badge_html = "<span class='ui-pill'>🔴 준비 안 됨</span>"

    c1, c2 = st.columns([0.78, 0.22])
    with c1:
        st.markdown("""
        <style>
          .hdr-row { display:flex; align-items:center; gap:.5rem; line-height:1.3; }
          .hdr-title { font-size:1.25rem; font-weight:800; }
          .ui-pill { display:inline-block; padding:2px 10px; border-radius:999px; 
                     border:1px solid #e5e7eb; background:#f8fafc; font-size:0.9rem; }
          .ui-pill-green { background:#10b98122; border-color:#10b98166; color:#065f46; }
        </style>
        <div class='hdr-row'>
          <span class='hdr-title'>LEES AI 쌤</span>
          """ + badge_html + """
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.write("")
        show = bool(st.session_state.get("show_faq", False))
        label = "📚 친구들이 자주하는 질문" if not show else "📚 친구들이 자주하는 질문 닫기"
        if st.button(label, key="btn_toggle_faq", use_container_width=True):
            st.session_state["show_faq"] = not show

    if st.session_state.get("show_faq", False):
        popular_fn = globals().get("_popular_questions", None)
        ranked = popular_fn(top_n=5, days=14) if callable(popular_fn) else []
        with st.container(border=True):
            st.markdown("**📚 친구들이 자주하는 질문** — 최근 2주 기준")
            if not ranked:
                st.caption("아직 집계된 질문이 없어요.")
            else:
                for qtext, cnt in ranked:
                    if st.button(f"{qtext}  · ×{cnt}", key=f"faq_{hash(qtext)}", use_container_width=True):
                        st.session_state["qa_q"] = qtext
                        st.rerun()

def main():
    # 0) 헤더
    try:
        _render_title_with_status()
    except Exception:
        pass

    # 부트 경고 출력(있을 때만)
    for _msg in globals().get("_BOOT_WARNINGS", []):
        st.warning(_msg)

    # 1) 자동 연결/복구
    try:
        before = get_index_status()
    except Exception:
        before = "missing"
    try:
        needs_recovery = (before in ("missing", "pending")) and (not _is_attached_session())
        if needs_recovery:
            _auto_attach_or_restore_silently()
            after = get_index_status()
            if after != before:
                st.rerun()
    except Exception:
        pass

    # 2) 관리자 패널들(설정/진단)
    if st.session_state.get("is_admin", False):
        try:
            render_admin_settings_panel()
        except Exception:
            pass
        with st.expander("진단/로그(관리자 전용)", expanded=False):
            try:
                render_tag_diagnostics()
            except Exception:
                st.caption("진단 모듈이 비활성화되어 있습니다.")

    # 3) 준비/브레인 패널
    try:
        render_brain_prep_main()
    except Exception:
        pass

    # 4) 학생 질문 패널
    try:
        render_qa_panel()
    except Exception as e:
        st.error(f"질문 패널 렌더 중 오류: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
# ===== [07] END ===============================================================
