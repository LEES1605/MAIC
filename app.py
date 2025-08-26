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

# ===== [01] APP BOOT & ENV ===================================================
# (주의) 여기에는 'from __future__'를 다시 쓰지 않습니다.
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUN_ON_SAVE"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION"] = "false"
# ===== [01] END ===============================================================

# ===== [02] IMPORTS & RAG BINDINGS ==========================================
from pathlib import Path
from typing import Any, Optional, Callable, List, Dict, Tuple

import re
import time
import importlib
import math
import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None  # type: ignore
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

# 인덱스 빌더/사전점검 (PREPARED→청크→리포트→ZIP 업로드)
precheck_build_needed: Optional[Callable[..., Any]] = None
build_index_with_checkpoint: Optional[Callable[..., Any]] = None
_import_errors: List[str] = []

def _bind_precheck(mod) -> Optional[Callable[..., Any]]:
    """precheck_build_needed | quick_precheck 어느 쪽이든 호출 가능 래퍼."""
    fn = getattr(mod, "precheck_build_needed", None) or getattr(mod, "quick_precheck", None)
    if fn is None:
        return None
    def _call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except TypeError:
            return fn()
    return _call

# 1차 경로: src.rag.index_build
try:
    _mod = importlib.import_module("src.rag.index_build")
    precheck_build_needed = _bind_precheck(_mod)
    build_index_with_checkpoint = getattr(_mod, "build_index_with_checkpoint", None)
except Exception as e:
    _import_errors.append(f"[src.rag.index_build] {type(e).__name__}: {e}")

# 2차 경로: rag.index_build (프로젝트 루트가 src일 때)
if precheck_build_needed is None or build_index_with_checkpoint is None:
    try:
        _mod2 = importlib.import_module("rag.index_build")
        precheck_build_needed = precheck_build_needed or _bind_precheck(_mod2)
        build_index_with_checkpoint = build_index_with_checkpoint or getattr(_mod2, "build_index_with_checkpoint", None)
    except Exception as e:
        _import_errors.append(f"[rag.index_build] {type(e).__name__}: {e}")

# ===== [BOOT-WARN] set_page_config 이전 경고 누적 ============================
_BOOT_WARNINGS: List[str] = []
if precheck_build_needed is None or build_index_with_checkpoint is None:
    _BOOT_WARNINGS.append(
        "사전점검/빌더 임포트에 실패했습니다.\n\n"
        + "\n".join(f"• {msg}" for msg in _import_errors)
        + "\n\n확인하세요:\n"
        + "1) 파일 존재: src/rag/index_build.py\n"
        + "2) 패키지 마커: src/__init__.py, src/rag/__init__.py\n"
        + "3) 함수 이름: precheck_build_needed **또는** quick_precheck 중 하나 필요\n"
        + "4) import 철자: index_build(언더스코어), index.build(점) 아님"
    )
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
        st.session_state["_auto_restore_last"].update(step="rebuilt_and_attached", final_]()_

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

# ===== [04B] ADMIN SETTINGS — 질문 모드 표시 여부 ============================
def render_admin_settings():
    # 관리자만 보이도록 가드
    if not (st.session_state.get("is_admin")
            or st.session_state.get("admin_mode")
            or st.session_state.get("role") == "admin"
            or st.session_state.get("mode") == "admin"):
        return

    with st.container(border=True):
        st.markdown("**관리자 설정**")
        st.caption("질문 모드 표시 여부를 선택하세요.")

        # 기본값 및 기존 키 호환
        defaults = {"문법설명": True, "문장구조분석": True, "지문분석": True}
        vis_list = st.session_state.get("qa_modes_enabled")
        if not isinstance(vis_list, list):
            vis_list = []
            if st.session_state.get("show_mode_grammar",  defaults["문법설명"]):    vis_list.append("문법설명")
            if st.session_state.get("show_mode_structure",defaults["문장구조분석"]):  vis_list.append("문장구조분석")
            if st.session_state.get("show_mode_passage",  defaults["지문분석"]):    vis_list.append("지문분석")
            if not vis_list:
                vis_list = [k for k, v in defaults.items() if v]
        enabled = set(vis_list)

        # 가로 3열 배치
        col1, col2, col3 = st.columns(3)
        with col1:
            opt_grammar = st.checkbox("문법설명", value=("문법설명" in enabled), key="cfg_show_mode_grammar")
        with col2:
            opt_structure = st.checkbox("문장구조분석", value=("문장구조분석" in enabled), key="cfg_show_mode_structure")
        with col3:
            opt_passage = st.checkbox("지문분석", value=("지문분석" in enabled), key="cfg_show_mode_passage")

        # 선택 결과 집계
        selected = []
        if opt_grammar:   selected.append("문법설명")
        if opt_structure: selected.append("문장구조분석")
        if opt_passage:   selected.append("지문분석")

        # 세션 상태 갱신(신/구 키 모두)
        st.session_state["qa_modes_enabled"]    = selected
        st.session_state["show_mode_grammar"]   = opt_grammar
        st.session_state["show_mode_structure"] = opt_structure
        st.session_state["show_mode_passage"]   = opt_passage

        st.caption("표시 중: " + (" · ".join(selected) if selected else "없음"))

def render_admin_settings_panel(*args, **kwargs):
    return render_admin_settings(*args, **kwargs)
# ===== [04B] END ==============================================================

# ===== [04C] 프롬프트 소스/드라이브 진단 패널(강화) ==========================
def _render_admin_diagnostics_section():
    """프롬프트 소스/환경 상태 점검 + 드라이브 강제 동기화 버튼"""
    import os
    import importlib
    from datetime import datetime

    # 관리자 가드
    if not (st.session_state.get("is_admin")
            or st.session_state.get("admin_mode")
            or st.session_state.get("role") == "admin"
            or st.session_state.get("mode") == "admin"):
        return

    with st.expander("🛠 진단 · 프롬프트 소스 상태", expanded=True):
        # 0) 모듈 로드
        try:
            pm = importlib.import_module("src.prompt_modes")
        except Exception as e:
            st.error(f"prompt_modes 임포트 실패: {type(e).__name__}: {e}")
            return

        # 1) 환경/secrets (마스킹)
        folder_id = os.getenv("MAIC_PROMPTS_DRIVE_FOLDER_ID")
        try:
            if (not folder_id) and ("MAIC_PROMPTS_DRIVE_FOLDER_ID" in st.secrets):
                folder_id = str(st.secrets["MAIC_PROMPTS_DRIVE_FOLDER_ID"])
        except Exception:
            pass
        def _mask(v):
            if not v: return "— 없음"
            v = str(v);  return (v[:6] + "…" + v[-4:]) if len(v) > 12 else ("*" * len(v))
        st.write("• Drive 폴더 ID:", _mask(folder_id))

        # 2) Drive 연결 및 계정 이메일
        drive_ok, drive_email = False, None
        try:
            im = importlib.import_module("src.rag.index_build")
            svc = getattr(im, "_drive_service", None)() if hasattr(im, "_drive_service") else None
            if svc:
                drive_ok = True
                try:
                    about = svc.about().get(fields="user").execute()
                    drive_email = (about or {}).get("user", {}).get("emailAddress")
                except Exception:
                    drive_email = None
        except Exception:
            pass
        st.write("• Drive 연결:", "✅ 연결됨" if drive_ok else "❌ 없음")
        if drive_email:
            st.write("• 연결 계정:", f"`{drive_email}`")

        # 3) 로컬 파일 경로/상태
        p = pm.get_overrides_path()
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

        # 4) 강제 동기화
        colA, colB = st.columns([1,1])
        with colA:
            if st.button("🔄 드라이브에서 prompts.yaml 당겨오기(강제)", use_container_width=True, key="btn_force_pull_prompts"):
                try:
                    if hasattr(pm, "_REMOTE_PULL_ONCE_FLAG"):
                        pm._REMOTE_PULL_ONCE_FLAG["done"] = False
                    pulled = None
                    if hasattr(pm, "_pull_remote_overrides_if_newer"):
                        pulled = pm._pull_remote_overrides_if_newer()
                    else:
                        _ = pm.load_overrides()
                        pulled = "loaded"
                    st.success(f"동기화 결과: {pulled}" if pulled else "동기화 결과: 변경 없음")
                except Exception as e:
                    st.error(f"동기화 실패: {type(e).__name__}: {e}")
        with colB:
            if exists and st.button("📄 로컬 파일 내용 미리보기", use_container_width=True, key="btn_preview_prompts_yaml"):
                try:
                    st.code(p.read_text(encoding="utf-8"), language="yaml")
                except Exception as e:
                    st.error(f"파일 읽기 실패: {type(e).__name__}: {e}")

        # 5) YAML 파싱 확인
        modes = []
        try:
            data = pm.load_overrides()
            if isinstance(data, dict):
                modes = list((data.get("modes") or {}).keys())
        except Exception as e:
            st.error(f"YAML 로드 오류: {type(e).__name__}: {e}")
        st.write("• 포함된 모드:", " , ".join(modes) if modes else "— (미검출)")

_render_admin_diagnostics_section()
# ===== [04C] END ==============================================================

# ===== [05A] 자료 최적화/백업 패널 (관리자 전용) =============================
def render_brain_prep_main():
    """
    - Drive 'prepared' 변화 감지(quick_precheck) → 결과 요약(+파일 목록)
    - 상태 배지(우선순위): no_prepared → delta → no_manifest → no_change
    - 인덱싱 중: 현재 파일명(아이콘) + 처리 n/총 m + ETA 표시
    - 완료 시 요약 배지 + 세션 기록(_optimize_last) + 복구 상세 표시
    - 복구 직후/자료없음일 때 manifest: '— (업데이트 시 생성)'로 표기
    - 🧠 두뇌 연결(강제) 버튼 포함
    """
    # 관리자 가드
    def _is_admin() -> bool:
        ss = st.session_state
        return bool(
            ss.get("is_admin") or ss.get("admin_mode")
            or (ss.get("role") == "admin") or (ss.get("mode") == "admin")
        )
    if not _is_admin():
        return

    # 모듈/함수 바인딩
    try:
        mod = importlib.import_module("src.rag.index_build")
    except Exception as e:
        st.error(f"인덱스 모듈 임포트 실패: {type(e).__name__}: {e}")
        return
    quick_precheck = getattr(mod, "quick_precheck", None) or getattr(mod, "precheck_build_needed", None)
    build_fn       = getattr(mod, "build_index_with_checkpoint", None)
    restore_fn     = getattr(mod, "restore_latest_backup_to_local", None)
    upload_zip_fn  = getattr(mod, "_make_and_upload_backup_zip", None)
    persist_dir    = getattr(mod, "PERSIST_DIR", Path.home() / ".maic" / "persist")
    if not callable(restore_fn):
        st.error("restore_latest_backup_to_local()를 찾지 못했습니다."); return
    if not callable(build_fn):
        st.error("build_index_with_checkpoint()를 찾지 못했습니다."); return

    # 인덱스 상태
    try:
        idx_status = get_index_status()
    except Exception:
        idx_status = "missing"
    status_badge = {"ready":"🟢 답변준비 완료","pending":"🟡 로컬 파일 감지(세션 미부착)","missing":"🔴 인덱스 없음"}.get(idx_status,"❔ 상태 미상")

    # 신규자료 점검 + 델타/사유 파싱
    prepared_cnt = manifest_cnt = 0
    reasons: List[str] = []
    added: List[str]; modified: List[str]; removed: List[str]; moved: List[str]; skipped: List[str]
    added, modified, removed, moved, skipped = [], [], [], [], []
    try:
        if callable(quick_precheck):
            pre = quick_precheck(None)  # 폴더 ID는 내부 자동 탐색
            prepared_cnt = int(pre.get("prepared_count", 0))
            manifest_cnt = int(pre.get("manifest_count", 0))
            reasons = list(pre.get("reasons", []))
            delta = pre.get("delta") or {}
            added    = list(pre.get("added",    [])) or list(delta.get("added",    []))
            modified = list(pre.get("modified", [])) or list(delta.get("modified", []))
            removed  = list(pre.get("removed",  [])) or list(delta.get("removed",  []))
            moved    = list(pre.get("moved",    [])) or list(delta.get("moved",    []))
            skipped  = list(pre.get("skipped",  [])) or list(delta.get("skipped",  []))
    except Exception as e:
        reasons = [f"precheck_failed:{type(e).__name__}"]

    # 상태 분류(우선순위)
    delta_count = len(added) + len(modified) + len(removed) + len(moved)
    if prepared_cnt == 0:
        status_kind = "no_prepared"
    elif delta_count > 0:
        status_kind = "delta"
    elif manifest_cnt == 0:
        status_kind = "no_manifest"
    else:
        status_kind = "no_change"

    kind_badge = {
        "delta":       "🟢 신규자료 감지",
        "no_manifest": "🟡 초기화 필요(매니페스트 없음)",
        "no_prepared": "⚪ 자료 없음",
        "no_change":   "✅ 변경 없음",
    }[status_kind]

    # 확장자 아이콘
    ICONS = {".pdf":"📕",".doc":"📝",".docx":"📝",".txt":"🗒️",".md":"🗒️",".ppt":"📊",".pptx":"📊",
             ".xls":"📈",".xlsx":"📈",".csv":"📑",".json":"🧩",".html":"🌐",
             ".jpg":"🖼️",".jpeg":"🖼️",".png":"🖼️",".gif":"🖼️",".webp":"🖼️",".svg":"🖼️",
             ".mp3":"🔊",".wav":"🔊",".mp4":"🎞️",".mkv":"🎞️",".py":"🐍",".ipynb":"📓"}
    def _icon_for(path: str) -> str:
        ext = os.path.splitext(str(path).lower())[1]
        return ICONS.get(ext, "📄")

    # 패널 렌더
    with st.container(border=True):
        st.subheader("자료 최적화/백업 패널")
        st.caption("Drive의 prepared 폴더와 로컬 manifest를 비교하여 업데이트 필요 여부를 판단합니다.")

        # manifest 표기 규칙(복구 직후/자료 없음 → '— (업데이트 시 생성)')
        last = st.session_state.get("_optimize_last") or {}
        restored_recently = (last.get("ok") and last.get("tag") == "restore")
        show_manifest_hint = (prepared_cnt == 0) or restored_recently
        manifest_label = ("— (업데이트 시 생성)" if (manifest_cnt == 0 and show_manifest_hint)
                          else str(manifest_cnt))

        cols = st.columns([1,1,1,1])
        cols[0].write(f"**인덱스 상태:** {status_badge}")
        cols[1].write(f"**신규자료:** {kind_badge}")
        cols[2].write(f"**prepared:** {prepared_cnt}")
        cols[3].write(f"**manifest:** {manifest_label}")

        # 델타 상세
        if status_kind == "delta":
            with st.expander("🔎 신규자료 상세(추가/수정/삭제 내역)", expanded=True):
                st.caption(
                    f"추가 {len(added)} · 수정 {len(modified)} · 삭제 {len(removed)}"
                    + (f" · 이동 {len(moved)}" if moved else "")
                    + (f" · 제외 {len(skipped)}" if skipped else "")
                )
                c1, c2, c3 = st.columns(3)
                def _render_list(col, title, rows, limit=20):
                    with col:
                        st.markdown(f"**{title}**")
                        if not rows:
                            st.caption("— 없음")
                        else:
                            for x in rows[:limit]:
                                st.write(f"{_icon_for(x)} {x}")
                            if len(rows) > limit:
                                st.caption(f"… 외 {len(rows)-limit}개")
                _render_list(c1, "추가됨", added); _render_list(c2, "수정됨", modified); _render_list(c3, "삭제됨", removed)

        if reasons and status_kind != "delta":
            with st.expander("세부 사유 보기", expanded=False):
                for r in reasons:
                    st.write("•", str(r))

        st.divider()

        # 권장 동작 배지
        RECO = {
            "delta":       "업데이트 실행을 추천합니다.",
            "no_manifest": "최신 백업 복구 또는 강제 최적화 초기화를 추천합니다.",
            "no_prepared": "최신 백업 복구를 추천합니다.",
            "no_change":   "필요 시 최신 백업 복구만 수행해도 됩니다.",
        }
        st.caption(f"**권장:** {RECO[status_kind]}")

        # 버튼 가드(상태별 노출)
        show_update = (status_kind == "delta") or (status_kind == "no_manifest" and prepared_cnt > 0)
        if show_update:
            c1, c2, c3, c4 = st.columns([1,1,1,1])
            do_update        = c1.button("🚀 업데이트 실행 (최적화→업로드→복구→연결)", use_container_width=True)
            skip_and_restore = c2.button("⏭ 업데이트 건너뛰기 (기존 백업 복구→연결)", use_container_width=True)
            force_rebuild    = c3.button("🛠 강제 최적화 초기화", use_container_width=True)
            force_attach_now = c4.button("🧠 두뇌 연결(강제)", use_container_width=True)
        else:
            c1, c2, c3 = st.columns([1,1,1])
            do_update        = False
            skip_and_restore = c1.button("📦 최신 백업 복구 → 연결", use_container_width=True)
            force_rebuild    = c2.button("🛠 강제 최적화 초기화", use_container_width=True)
            force_attach_now = c3.button("🧠 두뇌 연결(강제)", use_container_width=True)

        # 공통 헬퍼
        def _final_attach():
            with st.status("두뇌 연결 중…", state="running") as s2:
                ok = _auto_attach_or_restore_silently()
                if ok:
                    s2.update(label="두뇌 연결 완료 ✅", state="complete")
                    st.toast("🟢 답변준비 완료")
                    st.rerun()
                else:
                    s2.update(label="두뇌 연결 실패 ❌", state="error")
                    st.error("세션 부착 실패")

        def _record_result(ok: bool, took_s: float, tag: str, processed:int|None=None, total:int|None=None):
            st.session_state["_optimize_last"] = {
                "ok": bool(ok), "took_sec": round(float(took_s), 1),
                "status_kind": status_kind,
                "counts": {"added": len(added),"modified": len(modified),"removed": len(removed),"moved": len(moved),"skipped": len(skipped)},
                "processed": processed, "total": total, "tag": tag
            }
            if ok:
                extra = (f" · 처리 {processed}/{total}" if (processed and total) else "")
                st.success(f"✅ 완료: {tag} · 소요 {took_s:.1f}s{extra}")
            else:
                st.error(f"❌ 실패: {tag} · 소요 {took_s:.1f}s")

        # 진행표시 유틸 (파일명 + n/총 m + ETA)
        path_regex = re.compile(r'([A-Za-z]:\\[^:*?"<>|\n]+|/[^ \n]+?\.[A-Za-z0-9]{1,8})')
        def _fmt_eta(sec: float) -> str:
            if sec <= 0 or math.isinf(sec) or math.isnan(sec): return "—"
            m, s = divmod(int(sec+0.5), 60); return f"{m}:{s:02d}" if m else f"{s}s"
        def _progress_context(total_guess: int):
            file_slot = st.empty(); ctr_slot = st.empty(); eta_slot = st.empty(); bar = st.progress(0)
            seen = set(); t0 = time.time()
            def on_msg(msg: str):
                m = path_regex.search(str(msg)); 
                if not m: return
                path = m.group(1).replace("\\","/"); fname = os.path.basename(path)
                if fname not in seen: seen.add(fname)
                processed = len(seen); total = max(total_guess, processed) if total_guess else processed
                pct = int(min(100, (processed/total)*100)) if total else 0
                took = time.time()-t0; eta = _fmt_eta((took/processed)*(total-processed)) if processed else "—"
                file_slot.markdown(f"{_icon_for(fname)} 현재 인덱싱 파일: **`{fname}`**")
                ctr_slot.markdown(f"진행: **{processed} / {total}**"); eta_slot.caption(f"예상 남은 시간: {eta}")
                try: bar.progress(pct)
                except Exception: pass
                return processed, total, took
            def finalize():
                file_slot.markdown("✅ 인덱싱 단계 완료"); ctr_slot.empty(); eta_slot.empty()
                try: bar.progress(100)
                except Exception: pass
                return len(seen), max(total_guess, len(seen)) if total_guess else len(seen), time.time()-t0
            return on_msg, finalize
        def _guess_total_for(tag: str) -> int:
            if status_kind == "delta": return max(1, delta_count)
            return prepared_cnt or manifest_cnt or 0

        # 처리 분기 — 업데이트
        if do_update:
            t0 = time.time()
            on_msg, finalized = _progress_context(_guess_total_for("update"))
            log = st.empty()
            def _pct(v, m=None): 
                if m: log.info(str(m)); on_msg(m)
            def _msg(s): 
                log.write(f"• {s}"); on_msg(s)
            with st.status("최적화(인덱싱) 실행 중…", state="running") as s:
                try:
                    # 표준 시그니처
                    build_fn(
                        update_pct=_pct,
                        update_msg=_msg,
                        gdrive_folder_id="",
                        gcp_creds={},
                        persist_dir=str(persist_dir),
                        remote_manifest={},
                    )
                    s.update(label="최적화 완료 ✅", state="complete")
                except TypeError:
                    # 구버전 시그니처 대응
                    build_fn(_pct, _msg, "", {}, str(persist_dir), {})
                    s.update(label="최적화 완료 ✅", state="complete")
                except Exception as e:
                    s.update(label="최적화 실패 ❌", state="error")
                    st.error(f"인덱싱 오류: {type(e).__name__}: {e}")
                    return
            processed, total, _ = finalized()

            if callable(upload_zip_fn):
                with st.status("백업 ZIP 업로드 중…", state="running") as s:
                    try:
                        up = upload_zip_fn(None, None)
                        if not (up and up.get("ok")): s.update(label="업로드 실패(계속 진행) ⚠️", state="error")
                        else:                          s.update(label="업로드 완료 ✅", state="complete")
                    except Exception:
                        s.update(label="업로드 실패(계속 진행) ⚠️", state="error")

            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error")
                    _record_result(False, time.time()-t0, "update", processed, total)
                    st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}")
                    return
                s.update(label="복구 완료 ✅", state="complete")
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}): 
                        v = rr[k]; details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "update", processed, total)
            _final_attach()

        # 처리 분기 — 건너뛰고 복구
        if skip_and_restore:
            t0 = time.time()
            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error")
                    _record_result(False, time.time()-t0, "restore")
                    st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}")
                    return
                s.update(label="복구 완료 ✅", state="complete")
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}):
                        v = rr[k]; details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "restore")
            _final_attach()

        # 처리 분기 — 강제 재최적화
        if force_rebuild:
            t0 = time.time()
            on_msg, finalized = _progress_context(_guess_total_for("rebuild"))
            log = st.empty()
            def _pct(v, m=None): 
                if m: log.info(str(m)); on_msg(m)
            def _msg(s): 
                log.write(f"• {s}"); on_msg(s)
            with st.status("다시 최적화 실행 중…", state="running") as s:
                try:
                    build_fn(update_pct=_pct, update_msg=_msg, gdrive_folder_id="", gcp_creds={}, persist_dir=str(persist_dir), remote_manifest={})
                    s.update(label="다시 최적화 완료 ✅", state="complete")
                except TypeError:
                    build_fn(_pct, _msg, "", {}, str(persist_dir), {})
                    s.update(label="다시 최적화 완료 ✅", state="complete")
                except Exception as e:
                    s.update(label="다시 최적화 실패 ❌", state="error")
                    _record_result(False, time.time()-t0, "rebuild")
                    st.error(f"재최적화 오류: {type(e).__name__}: {e}")
                    return
            processed, total, _ = finalized()

            if callable(upload_zip_fn):
                with st.status("백업 ZIP 업로드 중…", state="running") as s:
                    try:
                        up = upload_zip_fn(None, None)
                        if not (up and up.get("ok")): s.update(label="업로드 실패(계속 진행) ⚠️", state="error")
                        else:                          s.update(label="업로드 완료 ✅", state="complete")
                    except Exception:
                        s.update(label="업로드 실패(계속 진행) ⚠️", state="error")

            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error")
                    _record_result(False, time.time()-t0, "rebuild", processed, total)
                    st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}")
                    return
                s.update(label="복구 완료 ✅", state="complete")
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}):
                        v = rr[k]; details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "rebuild", processed, total)
            _final_attach()

        # 🧠 두뇌 강제 연결(attach)
        if force_attach_now:
            try:
                with st.status("두뇌 연결 중…", state="running") as s:
                    st.caption(f"persist_dir: `{persist_dir}`")
                    if not _has_local_index_files():
                        s.update(label="두뇌 연결 실패 ❌", state="error")
                        st.error("로컬 인덱스 파일을 찾지 못했습니다. '최신 백업 복구' 또는 '업데이트' 후 재시도하세요.")
                    else:
                        ok = False
                        try:
                            ok = _attach_from_local()
                        except Exception as e:
                            s.update(label="두뇌 연결 실패 ❌", state="error")
                            st.error(f"예외: {type(e).__name__}: {e}")
                        if ok:
                            st.session_state["brain_attached"] = True
                            s.update(label="두뇌 연결 완료 ✅", state="complete")
                            st.toast("🟢 답변준비 완료")
                            st.rerun()
                        else:
                            s.update(label="두뇌 연결 실패 ❌", state="error")
                            st.info("힌트: persist_dir 경로/권한과 파일 유무를 확인하세요. 필요 시 '업데이트' 또는 '최신 백업 복구' 후 다시 시도.")
            except Exception as e:
                st.error(f"두뇌 연결 처리 중 예외: {type(e).__name__}: {e}")
# ===== [05A] END ==============================================================

# ===== [05B] 간단 진단 패널(선택) ===========================================
def render_tag_diagnostics():
    """자동 복구 상태, rag_index 경로, 리포트/ZIP 목록 등 간단 요약."""
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

    auto_info = st.session_state.get("_auto_restore_last")
    with st.container(border=True):
        st.markdown("### 자동 복구 상태")
        if not auto_info:
            st.caption("아직 자동 복구 시도 기록이 없습니다.")
        else:
            st.code(_json.dumps(auto_info, ensure_ascii=False, indent=2), language="json")

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

    qr_exists = QUALITY_REPORT_PATH.exists()
    qr_badge = "✅ 있음" if qr_exists else "❌ 없음"
    st.markdown(f"- **품질 리포트(quality_report.json)**: {qr_badge}  (`{QUALITY_REPORT_PATH.as_posix()}`)")
# ===== [05B] END ==============================================================

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

# ===== [06] 질문/답변 패널 — 프롬프트 연동 & LLM 호출 ========================
def render_qa_panel():
    """
    학생 질문 → (모드) → 프롬프트 빌드 → LLM 호출(OpenAI/Gemini) → 답변 표시
    - 관리자에서 켠 모드만 라디오에 노출
    - 라이브러리/키 상태에 따라 안전하게 폴백
    - ✅ 스트리밍 출력 + 세션 캐싱 + Gemini 모델 선택(관리자)
    - ✅ (NEW) 관리자용 생성 설정: temperature / max_tokens 슬라이더 적용
    """
    import traceback, importlib.util

    # 보여줄 모드 집합(관리자 설정 반영)
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
        rag_ready = _is_brain_ready()
        if rag_ready:
            st.caption("🧠 두뇌 상태: **연결됨** · 업로드 자료(RAG) 사용 가능")
        else:
            st.caption("🧠 두뇌 상태: **미연결** · 현재 응답은 **LLM-only(자료 미참조)** 입니다")

        colm, colq = st.columns([1,3])
        with colm:
            sel_mode = st.radio("모드", options=labels, horizontal=True, key="qa_mode_radio")

            # ✅ 관리자 전용: Gemini 모델 선택 + 생성 설정 슬라이더
            is_admin = (
                st.session_state.get("is_admin")
                or st.session_state.get("admin_mode")
                or st.session_state.get("role") == "admin"
                or st.session_state.get("mode") == "admin"
            )
            if is_admin:
                st.markdown("---")
                st.caption("Gemini 모델 선택(관리자)")
                default_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                st.session_state.setdefault("gemini_model_selection", default_model)
                st.session_state["gemini_model_selection"] = st.radio(
                    "Gemini 모델", options=["gemini-1.5-flash", "gemini-1.5-pro"],
                    index=0 if str(default_model).endswith("flash") else 1, key="gemini_model_radio"
                )

                st.markdown("---")
                st.caption("생성 설정(관리자)")
                # 기본값: 안정적 톤과 과도한 장문 방지
                st.session_state.setdefault("gen_temperature", 0.3)
                st.session_state.setdefault("gen_max_tokens", 700)
                st.session_state["gen_temperature"] = st.slider(
                    "Temperature (창의성)", min_value=0.0, max_value=1.0, value=float(st.session_state["gen_temperature"]), step=0.1
                )
                st.session_state["gen_max_tokens"] = st.slider(
                    "Max Tokens (응답 길이 상한)", min_value=100, max_value=2000, value=int(st.session_state["gen_max_tokens"]), step=50
                )
        with colq:
            question = st.text_area("질문을 입력하세요", height=96, placeholder="예: I had my bike repaired.")
        colA, colB = st.columns([1,1])
        go = colA.button("답변 생성", use_container_width=True)
        show_prompt = colB.toggle("프롬프트 미리보기", value=False)

    if not go:
        return

    # 프롬프트 빌드
    try:
        from src.prompt_modes import build_prompt, to_openai, to_gemini
        parts = build_prompt(sel_mode, question or "", lang="ko", extras={
            "level":  st.session_state.get("student_level"),
            "tone":   "encouraging",
        })
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
            if parts.provider_kwargs:
                st.caption(f"provider_kwargs: {parts.provider_kwargs}")

    # 라이브러리/키 상태 점검
    have_openai_lib  = importlib.util.find_spec("openai") is not None
    have_gemini_lib  = importlib.util.find_spec("google.generativeai") is not None
    has_openai_key   = bool(os.getenv("OPENAI_API_KEY") or getattr(st, "secrets", {}).get("OPENAI_API_KEY"))
    has_gemini_key   = bool(os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY"))

    # ✅ 세션 캐싱 준비
    st.session_state.setdefault("_openai_client_cache", None)
    st.session_state.setdefault("_gemini_model_cache", {})  # {model_name: genai.GenerativeModel}

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

    # ✅ 스트리밍 출력용 슬롯
    out_box = st.empty()

    # 관리자 설정값 읽기(비관리자는 기본값)
    temp = float(st.session_state.get("gen_temperature", 0.3))
    max_toks = int(st.session_state.get("gen_max_tokens", 700))
    # 안전 가드
    if not (0.0 <= temp <= 1.0): temp = 0.3
    if not (100 <= max_toks <= 2000): max_toks = 700

    # LLM 호출 (OpenAI → Gemini)
    def _call_openai_stream(p):
        try:
            client = _get_openai_client()
            payload = to_openai(p)  # {"messages":[...], ...}
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            # ✅ 스트리밍 + 생성 설정 적용
            stream = client.chat.completions.create(
                model=model,
                stream=True,
                temperature=temp,
                max_tokens=max_toks,
                **payload
            )
            buf = []
            for event in stream:
                delta = getattr(event.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    buf.append(delta.content)
                    out_box.markdown("".join(buf))
            text = "".join(buf).strip()
            return True, (text if text else None)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def _call_gemini_stream(p):
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY") or getattr(st, "secrets", {}).get("GEMINI_API_KEY")
            if not api_key:
                return False, "GEMINI_API_KEY 미설정"
            # ✅ 관리자 선택 모델 우선
            model_name = st.session_state.get("gemini_model_selection") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = _get_gemini_model(model_name)
            payload = to_gemini(p)  # {"contents":[...], ...}
            gen_cfg = {"temperature": temp, "max_output_tokens": max_toks}

            # ✅ 스트리밍
            stream = model.generate_content(payload["contents"], generation_config=gen_cfg, stream=True)
            buf = []
            for chunk in stream:
                if getattr(chunk, "text", None):
                    buf.append(chunk.text)
                    out_box.markdown("".join(buf))
            text = "".join(buf).strip()
            if not text:
                # 후보군이 있는 경우 첫 파트 텍스트 시도(비스트림 백업)
                resp = model.generate_content(payload["contents"], generation_config=gen_cfg)
                text = getattr(resp, "text", "") or (
                    resp.candidates[0].content.parts[0].text
                    if getattr(resp, "candidates", None) else ""
                )
            return True, (text if text else None)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    with st.status("답변 생성 중…", state="running") as s:
        ok, out, provider = False, None, "N/A"
        if have_openai_lib and has_openai_key:
            ok, out = _call_openai_stream(parts); provider = "OpenAI"
        if (not ok) and have_gemini_lib and has_gemini_key:
            ok, out = _call_gemini_stream(parts); provider = "Gemini" if ok else "N/A"

        if ok and (out is not None):
            s.update(label=f"{provider} 응답 수신 ✅", state="complete")
            st.caption(f"모델: {provider} · temperature={temp} · max_tokens={max_toks}")
        else:
            s.update(label="LLM 호출 실패 ❌", state="error")
            st.error("LLM 호출에 실패했습니다.")
            hints = []
            if not have_openai_lib and not have_gemini_lib:
                hints.append("requirements.txt 에 `openai`, `google-generativeai`를 추가하세요.")
            if have_openai_lib and not has_openai_key:
                hints.append("`OPENAI_API_KEY`를 secrets 또는 환경변수에 설정하세요.")
            if have_gemini_lib and not has_gemini_key:
                hints.append("`GEMINI_API_KEY`를 secrets 또는 환경변수에 설정하세요.")
            if not have_gemini_lib:
                hints.append("Gemini를 쓰려면 `google-generativeai` 설치가 필요합니다.")
            if not have_openai_lib:
                hints.append("OpenAI를 쓰려면 `openai` 패키지가 필요합니다.")
            # 관리자용 추가 힌트
            if (
                st.session_state.get("is_admin")
                or st.session_state.get("admin_mode")
                or st.session_state.get("role") == "admin"
                or st.session_state.get("mode") == "admin"
            ):
                hints.append("Gemini 실패 시 모델을 Flash ↔ Pro로 바꿔 재시도해 보세요.")
                hints.append("응답이 길면 max_tokens를 500~800 사이로 낮추면 속도가 빨라집니다.")
            if hints:
                st.info(" · ".join(hints))
            st.caption(f"원인(마지막 시도): {out or '원인 불명'}")
            st.info("프롬프트 미리보기 토글을 켜고 내용을 확인해 주세요.")
# ===== [06] END ==============================================================


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
