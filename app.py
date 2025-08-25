# ==== [HEAD] future import must be first =====================================
from __future__ import annotations  # 반드시 파일 첫 실행문

# ===== [00A-FIX] ENV BOOTSTRAP (secrets → os.environ) ========================
import os
try:
    import streamlit as st  # Streamlit Cloud에서만 존재할 수 있음
except Exception:
    st = None

def _bootstrap_env_from_secrets() -> None:
    """Streamlit secrets 값을 환경변수로 반영."""
    if st is None:
        return
    for key in ("MAIC_PROMPTS_DRIVE_FOLDER_ID", "MAIC_PROMPTS_PATH"):
        try:
            val = st.secrets.get(key, None)
        except Exception:
            val = None
        if val and not os.getenv(key):
            os.environ[key] = str(val)

_bootstrap_env_from_secrets()
# ===== [00A-FIX] END =========================================================

# ===== [01] APP BOOT & ENV ===================================================
# (주의) 여기에는 'from __future__'를 다시 쓰지 않습니다.
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUN_ON_SAVE"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION"] = "false"

# ===== [01] APP BOOT & ENV END ==============================================

# ===== [02] IMPORTS ==========================================================
from pathlib import Path
from typing import Any, Optional, Callable, List, Dict, Tuple

import re
import time
import importlib
import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None  # type: ignore
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

# 인덱스 빌더/사전점검 (PREPARED→청크→리포트→ZIP 업로드)
precheck_build_needed = None  # type: ignore
build_index_with_checkpoint = None  # type: ignore
_import_errors: List[str] = []

def _bind_precheck(mod) -> Optional[Callable[..., Any]]:
    """
    index_build가 어떤 이름으로 내보내든(precheck_build_needed | quick_precheck)
    여기서 하나로 바인딩한다.
    """
    fn = getattr(mod, "precheck_build_needed", None) or getattr(mod, "quick_precheck", None)
    if fn is None:
        return None

    # 시그니처가 다를 수 있어, 인자 미스매치면 무인자 호출로 재시도
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

# 임포트 실패 시 원인 안내
if precheck_build_needed is None or build_index_with_checkpoint is None:
    st.warning(
        "사전점검/빌더 임포트에 실패했습니다.\n\n"
        + "\n".join(f"• {msg}" for msg in _import_errors)
        + "\n\n확인하세요:\n"
        + "1) 파일 존재: src/rag/index_build.py\n"
        + "2) 패키지 마커: src/__init__.py, src/rag/__init__.py\n"
        + "3) 함수 이름: precheck_build_needed **또는** quick_precheck 중 하나가 있어야 합니다.\n"
        + "4) import 철자: index_build(언더스코어), index.build(점) 아님"
    )

# ===== [03] SESSION & HELPERS — START ========================================
st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None

# 모드/제출 플래그 (언어는 한국어 고정이므로 상태 저장하지 않음)
if "mode" not in st.session_state:
    st.session_state["mode"] = "Grammar"  # Grammar | Sentence | Passage
if "qa_submitted" not in st.session_state:
    st.session_state["qa_submitted"] = False

def _force_persist_dir() -> str:
    """
    내부 모듈들이 다른 경로를 보더라도, 런타임에서 ~/.maic/persist 로 강제 통일.
    - src.rag.index_build / rag.index_build 의 PERSIST_DIR 속성 주입
    - 환경변수 MAIC_PERSIST_DIR 도 세팅(내부 코드가 읽을 수 있음)
    """
    import importlib, os
    from pathlib import Path
    target = Path.home() / ".maic" / "persist"
    try: target.mkdir(parents=True, exist_ok=True)
    except Exception: pass

    for modname in ("src.rag.index_build", "rag.index_build"):
        try:
            m = importlib.import_module(modname)
            try: setattr(m, "PERSIST_DIR", target)
            except Exception: pass
        except Exception:
            continue
    os.environ["MAIC_PERSIST_DIR"] = str(target)
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
    # ⬅️ 붙이기 전에 경로 강제 통일
    _force_persist_dir()

    if get_or_build_index is None:
        return False
    try:
        idx = get_or_build_index()
        st.session_state["rag_index"] = idx
        return True
    except LocalIndexMissing:
        return False
    except Exception:
        return False

# ===== [PATCH-AR-01] 자동 복구 시퀀스 전체 교체 =================================
def _auto_attach_or_restore_silently() -> bool:
    """
    1) 로컬 부착 시도
    2) 실패 시: 드라이브 최신 백업 ZIP 복구 → 다시 부착
    3) 그래도 실패 시: 최소 옵션으로 인덱스 재빌드 → 다시 부착
    (모든 예외는 삼키고, 성공 시 True/실패 시 False를 명시적으로 반환)
    """
    import importlib
    from pathlib import Path

    st.session_state["_auto_restore_last"] = {
        "step": "start",
        "local_attach": None,
        "drive_restore": None,
        "rebuild": None,
        "final_attach": None,
    }

    # 모든 시도 전에 persist 경로 강제 통일
    _force_persist_dir()

    # 1) 로컬 attach
    if _attach_from_local():
        st.session_state["_auto_restore_last"]["step"] = "attached_local"
        st.session_state["_auto_restore_last"]["local_attach"] = True
        st.session_state["_auto_restore_last"]["final_attach"] = True
        return True
    st.session_state["_auto_restore_last"]["local_attach"] = False

    # 2) 드라이브에서 복구 시도
    try:
        mod = importlib.import_module("src.rag.index_build")
        restore_fn = getattr(mod, "restore_latest_backup_to_local", None)
        if callable(restore_fn):
            res = restore_fn()
            ok_restore = bool(isinstance(res, dict) and res.get("ok"))
        else:
            ok_restore = False
    except Exception:
        ok_restore = False
    st.session_state["_auto_restore_last"]["drive_restore"] = ok_restore

    if ok_restore and _has_local_index_files():
        if _attach_from_local():
            st.session_state["_auto_restore_last"]["step"] = "restored_and_attached"
            st.session_state["_auto_restore_last"]["final_attach"] = True
            return True

    # 3) 마지막 안전망: 인덱스 재생성(최소 옵션)
    ok_rebuild = None
    try:
        mod = importlib.import_module("src.rag.index_build")
        build_fn = getattr(mod, "build_index_with_checkpoint", None)
        persist_dir = getattr(mod, "PERSIST_DIR", Path.home() / ".maic" / "persist")
        if callable(build_fn):
            try:
                build_fn(
                    update_pct=lambda *_a, **_k: None,
                    update_msg=lambda *_a, **_k: None,
                    gdrive_folder_id="",
                    gcp_creds={},
                    persist_dir=str(persist_dir),
                    remote_manifest={},
                )
            except TypeError:
                # 시그니처가 다른 구현 대응
                build_fn()
            ok_rebuild = True
        else:
            ok_rebuild = False
    except Exception:
        ok_rebuild = False
    st.session_state["_auto_restore_last"]["rebuild"] = ok_rebuild

    # 재부착 최종 시도
    if _attach_from_local():
        st.session_state["_auto_restore_last"]["step"] = "rebuilt_and_attached"
        st.session_state["_auto_restore_last"]["final_attach"] = True
        return True

    st.session_state["_auto_restore_last"]["final_attach"] = False
    return False
# ===== [PATCH-AR-01] END ======================================================

# ===== [03] SESSION & HELPERS — END ========================

# ===== [04] HEADER ==========================================
def render_header():
    """
    헤더 UI는 [07] MAIN의 _render_title_with_status()가 전적으로 담당합니다.
    여기서는 중복 렌더링을 막기 위해 아무 것도 출력하지 않습니다.
    (요구사항: 'Index status: ...' 텍스트 및 중복 배지 제거)
    """
    return
# ===== [04] END =============================================

# ===== [04A] MODE & ADMIN BUTTON (모듈 분리 호출) — START ==================

from src.ui_admin import (
    ensure_admin_session_keys,
    render_admin_controls,
    render_role_caption,
)
import streamlit as st

# 1) 세션 키 보증
ensure_admin_session_keys()

# 2) 우측 상단 관리자 버튼/인증 패널 렌더 (내부에서 st.rerun 처리)
render_admin_controls()

# 3) 역할 캡션 + 구분선
render_role_caption()
st.divider()
# ===== [04A] MODE & ADMIN BUTTON (모듈 분리 호출) — END =======================

# ===== [04B] 관리자 설정 — 질문 모드 표시 여부 ===============================
def render_admin_settings():
    import streamlit as st

    # 관리자만 보이도록 가드
    if not (st.session_state.get("is_admin")
            or st.session_state.get("admin_mode")
            or st.session_state.get("role") == "admin"
            or st.session_state.get("mode") == "admin"):
        return

    with st.container(border=True):
        st.markdown("**관리자 설정**")
        st.caption("질문 모드 표시 여부를 선택하세요.")

        # ── 기본값 및 기존 키 호환 ──────────────────────────────────────────
        defaults = {"문법설명": True, "문장구조분석": True, "지문분석": True}

        # 우선순위: qa_modes_enabled 리스트 → 과거 불리언 키 → defaults
        vis_list = st.session_state.get("qa_modes_enabled")
        if not isinstance(vis_list, list):
            vis_list = []
            if st.session_state.get("show_mode_grammar",  defaults["문법설명"]):   vis_list.append("문법설명")
            if st.session_state.get("show_mode_structure",defaults["문장구조분석"]): vis_list.append("문장구조분석")
            if st.session_state.get("show_mode_passage",  defaults["지문분석"]):   vis_list.append("지문분석")
            if not vis_list:
                vis_list = [k for k, v in defaults.items() if v]

        enabled = set(vis_list)

        # ── 가로 3열 배치(문법설명 · 문장구조분석 · 지문분석) ───────────────────
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

        # ── 세션 상태 갱신(신/구 키 모두) ───────────────────────────────────
        st.session_state["qa_modes_enabled"]    = selected
        st.session_state["show_mode_grammar"]   = opt_grammar
        st.session_state["show_mode_structure"] = opt_structure
        st.session_state["show_mode_passage"]   = opt_passage

        # 요약 표시
        st.caption("표시 중: " + (" · ".join(selected) if selected else "없음"))

# (호환용 별칭: 과거 코드에서 이 이름을 호출해도 동작)
def render_admin_settings_panel(*args, **kwargs):
    return render_admin_settings(*args, **kwargs)
# ===== [04B] END ===========================================================

# ===== [04C-CALL] 관리자 진단 섹션 호출(강화판) ===============================
def _render_admin_diagnostics_section():
    """프롬프트 소스/환경 상태 점검 + 드라이브 강제 동기화 버튼"""
    import os
    from datetime import datetime
    import importlib
    import streamlit as st

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

        # 1) 환경변수 / secrets (마스킹)
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

        # 2) 드라이브 클라이언트 상태 + 사용 계정 이메일 추적
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
        if drive_ok and not drive_email:
            st.caption("  (주의: 연결 계정 이메일을 확인하지 못했습니다. 폴더 공유 대상 계정을 다시 확인하세요.)")

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

        # 4) 강제 동기화 버튼 (드라이브 → 로컬)
        colA, colB = st.columns([1,1])
        with colA:
            if st.button("🔄 드라이브에서 prompts.yaml 당겨오기(강제)", use_container_width=True, key="btn_force_pull_prompts"):
                try:
                    # pull-once 플래그 해제 후, 내부 pull 호출 시도
                    if hasattr(pm, "_REMOTE_PULL_ONCE_FLAG"):
                        pm._REMOTE_PULL_ONCE_FLAG["done"] = False  # 강제 재시도
                    pulled = None
                    if hasattr(pm, "_pull_remote_overrides_if_newer"):
                        pulled = pm._pull_remote_overrides_if_newer()
                    else:
                        # 직접 노출된 함수가 없으면 load_overrides()로 트리거
                        _ = pm.load_overrides()
                        pulled = "loaded"
                    if pulled:
                        st.success(f"동기화 결과: {pulled}")
                    else:
                        st.info("동기화 결과: 변경 없음(로컬이 최신이거나 접근 불가).")
                except Exception as e:
                    st.error(f"동기화 실패: {type(e).__name__}: {e}")
        with colB:
            if exists and st.button("📄 로컬 파일 내용 미리보기", use_container_width=True, key="btn_preview_prompts_yaml"):
                try:
                    st.code(p.read_text(encoding="utf-8"), language="yaml")
                except Exception as e:
                    st.error(f"파일 읽기 실패: {type(e).__name__}: {e}")

        # 5) YAML 파싱 결과 요약
        modes = []
        try:
            data = pm.load_overrides()
            if isinstance(data, dict):
                modes = list((data.get("modes") or {}).keys())
        except Exception as e:
            st.error(f"YAML 로드 오류: {type(e).__name__}: {e}")
        st.write("• 포함된 모드:", " , ".join(modes) if modes else "— (미검출)")

        # 6) 안내
        st.caption("힌트: 위 '연결 계정' 이메일이 보이면, 해당 이메일을 Drive 폴더에 '보기 권한'으로 공유해야 합니다.")
        st.caption("       폴더 안 파일명은 반드시 'prompts.yaml' 이어야 합니다(소문자, 확장자 .yaml).")

# 즉시 호출
_render_admin_diagnostics_section()
# ===== [04C-CALL] END ========================================================


# ===== [04C] 프롬프트 소스 진단 패널 =========================================
def render_prompt_source_diag():
    import os
    from datetime import datetime
    import streamlit as st
    try:
        from src.prompt_modes import get_overrides_path, load_overrides
    except Exception as e:
        with st.container(border=True):
            st.subheader("프롬프트 소스 상태")
            st.error(f"prompt_modes 임포트 실패: {type(e).__name__}: {e}")
        return

    with st.container(border=True):
        st.subheader("프롬프트 소스 상태")
        st.caption("Drive 폴더 연결 및 로컬 prompts.yaml 인식 여부를 점검합니다.")

        # 1) 환경변수 / secrets 확인 (값은 마스킹)
        folder_id = os.getenv("MAIC_PROMPTS_DRIVE_FOLDER_ID")
        try:
            if (not folder_id) and ("MAIC_PROMPTS_DRIVE_FOLDER_ID" in st.secrets):
                folder_id = str(st.secrets["MAIC_PROMPTS_DRIVE_FOLDER_ID"])
        except Exception:
            pass
        def _mask(v):
            v = str(v)
            return (v[:6] + "…" + v[-4:]) if len(v) > 12 else ("*" * len(v))
        st.write("• Drive 폴더 ID:", _mask(folder_id) if folder_id else "— 없음")

        # 2) 로컬 파일 경로/상태
        p = get_overrides_path()
        st.write("• 로컬 경로:", f"`{p}`")
        exists = p.exists()
        st.write("• 파일 존재:", "✅ 있음" if exists else "❌ 없음")

        data = None
        if exists:
            try:
                stat = p.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                st.write("• 크기/수정시각:", f"{stat.st_size} bytes / {mtime}")
            except Exception:
                pass
            # 3) YAML 로드 시도
            try:
                data = load_overrides()
                ok = isinstance(data, dict)
                st.write("• YAML 로드:", "✅ 성공" if ok else "⚠️ 비정상(dict 아님)")
            except Exception as e:
                st.error(f"YAML 로드 오류: {type(e).__name__}: {e}")

        # 4) modes 목록 및 핵심 블록 존재 여부
        modes = []
        if isinstance(data, dict):
            modes = list((data.get("modes") or {}).keys())
        st.write("• 포함된 모드:", " , ".join(modes) if modes else "— (미검출)")
        if modes and ("문장구조분석" not in modes):
            st.warning("`modes:` 아래에 `문장구조분석:` 블록이 없습니다. prompts.yaml을 확인하세요.")

        # 5) 필요하면 파일 내용 미리보기(개발용)
        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("📄 파일 내용 미리보기", use_container_width=True, key="btn_preview_prompts_yaml"):
                try:
                    st.code(p.read_text(encoding="utf-8"), language="yaml")
                except Exception as e:
                    st.error(f"파일 읽기 실패: {type(e).__name__}: {e}")
        with col2:
            st.caption("힌트: 서비스계정/앱 계정에 Drive 폴더 보기 권한을 공유했는지 확인하세요.")

# 호출 위치(관리자 전용 섹션 어딘가에서):
# render_prompt_source_diag()
# ===== [04C] END ====================================================

# ===== [05A] BRAIN PREP MAIN =======================================
def render_brain_prep_main():
    """
    준비/최적화 패널 (관리자 전용)
    - Drive 'prepared' 변화 감지(quick_precheck) → 결과 요약(+파일 목록)
    - 상태 배지(우선순위): no_prepared → delta → no_manifest → no_change
    - 인덱싱 중: 현재 파일명(아이콘) + 처리 n/총 m + ETA 표시
    - 완료 시 요약 배지 + 세션 기록(_optimize_last) + 복구 상세 표시
    - NEW: 복구 직후/자료없음일 때 manifest: `— (업데이트 시 생성)`로 표기
    """
    import streamlit as st
    import time, os, re, math
    import importlib
    from pathlib import Path

    # ── 역할 확인(관리자 전용) ────────────────────────────────────────────────
    def _is_admin() -> bool:
        ss = st.session_state
        return bool(
            ss.get("is_admin") or ss.get("admin_mode")
            or (ss.get("role") == "admin") or (ss.get("mode") == "admin")
        )
    if not _is_admin():
        return

    # ── 모듈/함수 바인딩 ────────────────────────────────────────────────────────
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

    # ── 인덱스 상태 ───────────────────────────────────────────────────────────
    try:
        idx_status = get_index_status()
    except Exception:
        idx_status = "missing"
    status_badge = {"ready":"🟢 답변준비 완료","pending":"🟡 로컬 파일 감지(세션 미부착)","missing":"🔴 인덱스 없음"}.get(idx_status,"❔ 상태 미상")

    # ── 신규자료 점검 + 델타/사유 파싱 ─────────────────────────────────────────
    prepared_cnt = manifest_cnt = 0
    reasons = []
    added = modified = removed = moved = skipped = []
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

    # ── 상태 분류(우선순위 고정) ──────────────────────────────────────────────
    delta_count = len(added) + len(modified) + len(removed) + len(moved)
    if prepared_cnt == 0:
        status_kind = "no_prepared"         # 최우선: 자료 자체가 없음
    elif delta_count > 0:
        status_kind = "delta"               # 실제 파일 증감 있음
    elif manifest_cnt == 0:
        status_kind = "no_manifest"         # 매니페스트 없음/유실
    else:
        status_kind = "no_change"           # 변경 없음

    kind_badge = {
        "delta":       "🟢 신규자료 감지",
        "no_manifest": "🟡 초기화 필요(매니페스트 없음)",
        "no_prepared": "⚪ 자료 없음",
        "no_change":   "✅ 변경 없음",
    }[status_kind]

    # ── 아이콘 맵(확장자별) ───────────────────────────────────────────────────
    ICONS = {".pdf":"📕",".doc":"📝",".docx":"📝",".txt":"🗒️",".md":"🗒️",".ppt":"📊",".pptx":"📊",
             ".xls":"📈",".xlsx":"📈",".csv":"📑",".json":"🧩",".html":"🌐",
             ".jpg":"🖼️",".jpeg":"🖼️",".png":"🖼️",".gif":"🖼️",".webp":"🖼️",".svg":"🖼️",
             ".mp3":"🔊",".wav":"🔊",".mp4":"🎞️",".mkv":"🎞️",".py":"🐍",".ipynb":"📓"}
    def _icon_for(path: str) -> str:
        ext = os.path.splitext(str(path).lower())[1]
        return ICONS.get(ext, "📄")

    # ── 패널 렌더 ─────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("자료 최적화/백업 패널")
        st.caption("Drive의 prepared 폴더와 로컬 manifest를 비교하여 업데이트 필요 여부를 판단합니다.")

        # NEW: manifest 표기 규칙(복구 직후/자료 없음 → '— (업데이트 시 생성)')
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

        # 실제 델타가 있을 때만 상세 펼침
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
                for r in reasons: st.write("•", str(r))

        st.divider()

        # ── 권장 동작 배지 ────────────────────────────────────────────────────
        RECO = {
            "delta":       "업데이트 실행을 추천합니다.",
            "no_manifest": "최신 백업 복구 또는 강제 최적화 초기화를 추천합니다.",
            "no_prepared": "최신 백업 복구를 추천합니다.",
            "no_change":   "필요 시 최신 백업 복구만 수행해도 됩니다.",
        }
        st.caption(f"**권장:** {RECO[status_kind]}")

        # ── 버튼 가드(상태별 노출) ────────────────────────────────────────────
        show_update = (status_kind == "delta") or (status_kind == "no_manifest" and prepared_cnt > 0)
        if show_update:
            c1, c2, c3 = st.columns([1,1,1])
            do_update        = c1.button("🚀 업데이트 실행 (최적화→업로드→복구→연결)", use_container_width=True)
            skip_and_restore = c2.button("⏭ 업데이트 건너뛰기 (기존 백업 복구→연결)", use_container_width=True)
            force_rebuild    = c3.button("🛠 강제 최적화 초기화", use_container_width=True)
        else:
            c1, c2 = st.columns([1,1])
            do_update = False
            skip_and_restore = c1.button("📦 최신 백업 복구 → 연결", use_container_width=True)
            force_rebuild    = c2.button("🛠 강제 최적화 초기화", use_container_width=True)

        # ── 공통 헬퍼 ─────────────────────────────────────────────────────────
        def _final_attach():
            with st.status("두뇌 연결 중…", state="running") as s2:
                ok = _auto_attach_or_restore_silently()
                if ok: s2.update(label="두뇌 연결 완료 ✅", state="complete"); st.toast("🟢 답변준비 완료"); st.rerun()
                else:  s2.update(label="두뇌 연결 실패 ❌", state="error"); st.error("세션 부착 실패")

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

        # 진행표시 유틸 (파일명 + n/m + ETA) ---------------------------------
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

        # ── 처리 분기(핵심 동작 동일, 복구 상세 출력 포함) ────────────────────
        if do_update:
            t0 = time.time(); on_msg, finalized = _progress_context(_guess_total_for("update")); log = st.empty()
            def _pct(v, m=None): 
                if m: log.info(str(m)); on_msg(m)
            def _msg(s): log.write(f"• {s}"); on_msg(s)
            with st.status("최적화(인덱싱) 실행 중…", state="running") as s:
                try:
                    build_fn(update_pct=_pct, update_msg=_msg, gdrive_folder_id="", gcp_creds={}, persist_dir=str(persist_dir), remote_manifest={})
                    s.update(label="최적화 완료 ✅", state="complete")
                except TypeError:
                    build_fn(_pct, _msg, "", {}, str(persist_dir), {}); s.update(label="최적화 완료 ✅", state="complete")
                except Exception as e:
                    s.update(label="최적화 실패 ❌", state="error"); _record_result(False, time.time()-t0, "update"); st.error(f"인덱싱 오류: {type(e).__name__}: {e}"); return
            processed, total, _ = finalized()
            if callable(upload_zip_fn):
                with st.status("백업 ZIP 업로드 중…", state="running") as s:
                    try:
                        up = upload_zip_fn(None, None)
                        if not (up and up.get("ok")): s.update(label="업로드 실패(계속 진행) ⚠️", state="error")
                        else:                          s.update(label="업로드 완료 ✅", state="complete")
                    except Exception:                    s.update(label="업로드 실패(계속 진행) ⚠️", state="error")
            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error"); _record_result(False, time.time()-t0, "update", processed, total); st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}"); return
                s.update(label="복구 완료 ✅", state="complete")
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}): 
                        v = rr[k]; details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "update", processed, total); _final_attach()

        if skip_and_restore:
            t0 = time.time()
            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error"); _record_result(False, time.time()-t0, "restore"); st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}"); return
                s.update(label="복구 완료 ✅", state="complete")
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}):
                        v = rr[k]; details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "restore"); _final_attach()

        if force_rebuild:
            t0 = time.time(); on_msg, finalized = _progress_context(_guess_total_for("rebuild")); log = st.empty()
            def _pct(v, m=None): 
                if m: log.info(str(m)); on_msg(m)
            def _msg(s): log.write(f"• {s}"); on_msg(s)
            with st.status("다시 최적화 실행 중…", state="running") as s:
                try:
                    build_fn(update_pct=_pct, update_msg=_msg, gdrive_folder_id="", gcp_creds={}, persist_dir=str(persist_dir), remote_manifest={})
                    s.update(label="다시 최적화 완료 ✅", state="complete")
                except TypeError:
                    build_fn(_pct, _msg, "", {}, str(persist_dir), {}); s.update(label="다시 최적화 완료 ✅", state="complete")
                except Exception as e:
                    s.update(label="다시 최적화 실패 ❌", state="error"); _record_result(False, time.time()-t0, "rebuild"); st.error(f"재최적화 오류: {type(e).__name__}: {e}"); return
            processed, total, _ = finalized()
            if callable(upload_zip_fn):
                with st.status("백업 ZIP 업로드 중…", state="running") as s:
                    try:
                        up = upload_zip_fn(None, None)
                        if not (up and up.get("ok")): s.update(label="업로드 실패(계속 진행) ⚠️", state="error")
                        else:                          s.update(label="업로드 완료 ✅", state="complete")
                    except Exception:                    s.update(label="업로드 실패(계속 진행) ⚠️", state="error")
            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error"); _record_result(False, time.time()-t0, "rebuild", processed, total); st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}"); return
                s.update(label="복구 완료 ✅", state="complete")
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}):
                        v = rr[k]; details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "rebuild", processed, total); _final_attach()
# ===== [05A] END ===========================================


# ===== [05B] TAG DIAGNOSTICS (NEW) — START ==================================
def render_tag_diagnostics():
    """
    태그/인덱스 진단 패널
    - 자동 복구 상태(_auto_restore_last) 표시
    - 현재 rag_index 객체의 persist_dir 추정 경로 표시
    - quality_report.json 유무
    - 로컬 ZIP: backup_*.zip + restored_*.zip (최신 5개)
    - 드라이브 ZIP: backup_zip 폴더의 ZIP (최신 5개)
    - 로컬 인덱스 파일(.ready, chunks.jsonl) 표시
    """
    import importlib, traceback
    from pathlib import Path
    from datetime import datetime
    import json as _json
    import streamlit as st

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

    # ── 자동 복구 상태 표시 ─────────────────────────────────────────────────────
    auto_info = st.session_state.get("_auto_restore_last")
    with st.container(border=True):
        st.markdown("### 자동 복구 상태")
        if not auto_info:
            st.caption("아직 자동 복구 시도 기록이 없습니다.")
        else:
            st.code(_json.dumps(auto_info, ensure_ascii=False, indent=2), language="json")

    # ── rag_index persist 경로 확인 ─────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("### rag_index Persist 경로 추정")
        rag = st.session_state.get("rag_index")
        if rag is None:
            st.caption("rag_index 객체가 세션에 없습니다.")
        else:
            cand = None
            # 흔히 쓰는 속성들 점검
            for attr in ("persist_dir", "storage_context", "vector_store", "index_struct"):
                try:
                    val = getattr(rag, attr, None)
                    if val:
                        cand = str(val)
                        break
                except Exception:
                    continue
            st.write("🔍 rag_index 내부 persist_dir/유사 속성:", cand or "(발견되지 않음)")

    # ── 품질 리포트 존재 ─────────────────────────────────────────────────────────
    qr_exists = QUALITY_REPORT_PATH.exists()
    qr_badge = "✅ 있음" if qr_exists else "❌ 없음"
    st.markdown(f"- **품질 리포트(quality_report.json)**: {qr_badge}  (`{QUALITY_REPORT_PATH.as_posix()}`)")

    # ── 로컬 ZIP 목록 ──────────────────────────────────────────────────────────
    local_rows = []
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        zips = list(BACKUP_DIR.glob("backup_*.zip")) + list(BACKUP_DIR.glob("restored_*.zip"))
        zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in zips[:5]:
            stt = p.stat()
            local_rows.append({"파일명": p.name, "크기": stt.st_size, "수정시각": stt.st_mtime})
    except Exception:
        pass

    # (나머지 ZIP/로컬 인덱스 체크 로직은 기존과 동일) …
# ===== [05B] TAG DIAGNOSTICS (NEW) — END ====================================


# ===== [06] 질문/답변 패널 — 프롬프트 모듈 연동 ==============================
def render_qa_panel():
    """
    학생 질문 → (모드) → 프롬프트 빌드 → LLM 호출(OpenAI/Gemini) → 답변 표시
    - 관리자에서 켠 모드만 라디오에 노출
    - 실패해도 앱이 죽지 않고 원인 안내
    """
    import os, traceback
    import streamlit as st

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
        colm, colq = st.columns([1,3])
        with colm:
            sel_mode = st.radio("모드", options=labels, horizontal=True, key="qa_mode_radio")
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

    # LLM 호출 (OpenAI → Gemini 순으로 시도)
    def _call_openai_try(p):
        try:
            from openai import OpenAI
            client = OpenAI()
            payload = to_openai(p)
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            resp = client.chat.completions.create(model=model, **payload)
            return True, resp.choices[0].message.content
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def _call_gemini_try(p):
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY") or (
                st.secrets.get("GEMINI_API_KEY") if hasattr(st, "secrets") else None
            )
            if not api_key:
                return False, "GEMINI_API_KEY 미설정"
            genai.configure(api_key=api_key)
            payload = to_gemini(p)  # {"contents":[...], ...}
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = genai.GenerativeModel(model_name=model_name)
            resp = model.generate_content(payload["contents"])
            text = getattr(resp, "text", "")
            if not text and getattr(resp, "candidates", None):
                text = resp.candidates[0].content.parts[0].text
            return True, text
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    with st.status("답변 생성 중…", state="running") as s:
        ok, out = _call_openai_try(parts)
        provider = "OpenAI"
        if not ok:
            ok, out = _call_gemini_try(parts)
            provider = "Gemini" if ok else "N/A"

        if ok and out:
            s.update(label=f"{provider} 응답 수신 ✅", state="complete")
            st.markdown(out)
        else:
            s.update(label="LLM 호출 실패 ❌", state="error")
            st.error("LLM 호출에 실패했습니다.")
            st.caption(f"원인: {out or '원인 불명'}")
            st.info("프롬프트 미리보기 토글을 켜고 내용을 확인해 주세요.")
# ===== [06] END ==============================================================


# ===== [07] MAIN — 오케스트레이터 ============================================
import streamlit as st

def _render_title_with_status():
    """
    상단 헤더: 제목 + 상태배지 + 우측 FAQ 토글
    - 학생: 🟢 LEES AI 선생님이 답변준비 완료
    - 관리자: 🟢 두뇌 준비됨
    """
    try:
        status = get_index_status()  # 'ready' | 'pending' | 'missing'
    except Exception:
        status = "missing"

    is_admin = bool(st.session_state.get("is_admin", False))

    # 상태 배지 문구(학생/관리자 분리)
    if status == "ready":
        badge_html = (
            "<span class='ui-pill ui-pill-green'>🟢 두뇌 준비됨</span>"
            if is_admin else
            "<span class='ui-pill ui-pill-green'>🟢 LEES AI 선생님이 답변준비 완료</span>"
        )
    elif status == "pending":
        badge_html = "<span class='ui-pill'>🟡 연결 대기</span>"
    else:
        badge_html = "<span class='ui-pill'>🔴 준비 안 됨</span>"

    # 레이아웃
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
        st.write("")  # 살짝 아래로 내리기
        show = bool(st.session_state.get("show_faq", False))
        label = "📚 친구들이 자주하는 질문" if not show else "📚 친구들이 자주하는 질문 닫기"
        if st.button(label, key="btn_toggle_faq", use_container_width=True):
            st.session_state["show_faq"] = not show

    # FAQ 패널
    if st.session_state.get("show_faq", False):
        popular_fn = globals().get("_popular_questions", None)
        ranked = popular_fn(top_n=5, days=14) if callable(popular_fn) else []
        with st.container(border=True):
            st.markdown("**📚 친구들이 자주하는 질문** — 최근 2주 기준")
            if not ranked:
                st.caption("아직 집계된 질문이 없어요.")
            else:
                for qtext, cnt in ranked:
                    # 클릭 시 입력창에 복구(자동검색은 하지 않음)
                    if st.button(f"{qtext}  · ×{cnt}", key=f"faq_{hash(qtext)}", use_container_width=True):
                        st.session_state["qa_q"] = qtext
                        st.rerun()  # 입력창에 즉시 반영

def main():
    # 0) 헤더
    try:
        _render_title_with_status()
    except Exception:
        pass

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

    # 2) 관리자 패널들(설정/진단)을 학생 화면 위에 배치
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
