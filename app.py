# ===== [01] APP BOOT & ENV ===================================================
from __future__ import annotations

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUN_ON_SAVE"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION"] = "false"

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

# ===== [03] SESSION & HELPERS ================================================
st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None

# 모드/제출 플래그 (언어는 한국어 고정이므로 상태 저장하지 않음)
if "mode" not in st.session_state:
    st.session_state["mode"] = "Grammar"  # Grammar | Sentence | Passage
if "qa_submitted" not in st.session_state:
    st.session_state["qa_submitted"] = False

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

def _auto_attach_or_restore_silently() -> bool:
    return _attach_from_local()


# ===== [04] HEADER ==========================================
def render_header():
    """
    헤더 UI는 [07] MAIN의 _render_title_with_status()가 전적으로 담당합니다.
    여기서는 중복 렌더링을 막기 위해 아무 것도 출력하지 않습니다.
    (요구사항: 'Index status: ...' 텍스트 및 중복 배지 제거)
    """
    return
# ===== [04] END =============================================

# ===== [04A] MODE & ADMIN BUTTON (콜백 제거: 즉시 갱신용 rerun) ================
import os as _os
import streamlit as st

# ── [04A-1] PIN 가져오기 ------------------------------------------------------
def _get_admin_pin() -> str:
    try:
        pin = st.secrets.get("ADMIN_PIN", None)  # type: ignore[attr-defined]
    except Exception:
        pin = None
    return str(pin or _os.environ.get("ADMIN_PIN") or "0000")
# ===== [04A-1] END ============================================================


# ── [04A-2] 세션키 초기화 ------------------------------------------------------
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "_admin_auth_open" not in st.session_state:
    st.session_state["_admin_auth_open"] = False
# ===== [04A-2] END ============================================================


# ── [04A-3] 상단 우측 관리자 버튼 & 인증 패널 (콜백 미사용) ----------------------
with st.container():
    _, right = st.columns([0.7, 0.3])
    with right:
        btn_slot = st.empty()

        if st.session_state["is_admin"]:
            # 관리자 모드일 때: 종료 버튼이 바로 보여야 함
            if btn_slot.button("🔓 관리자 종료", key="btn_close_admin", use_container_width=True):
                st.session_state["is_admin"] = False
                st.session_state["_admin_auth_open"] = False
                try: st.toast("관리자 모드 해제됨")
                except Exception: pass
                st.rerun()  # ← 콜백이 아닌 본문에서 rerun: 즉시 라벨 갱신
        else:
            # 학생 모드일 때: 관리자 버튼
            if btn_slot.button("🔒 관리자", key="btn_open_admin", use_container_width=True):
                st.session_state["_admin_auth_open"] = True
                st.rerun()  # 인증 패널을 즉시 표시

        # 인증 패널: 열림 상태이면 표시
        if st.session_state["_admin_auth_open"] and not st.session_state["is_admin"]:
            with st.container(border=True):
                st.markdown("**관리자 PIN 입력**")
                with st.form("admin_login_form", clear_on_submit=True, border=False):
                    pin_try = st.text_input("PIN", type="password")
                    c1, c2 = st.columns(2)
                    with c1:
                        ok = st.form_submit_button("입장")
                    with c2:
                        cancel = st.form_submit_button("취소")

                if cancel:
                    st.session_state["_admin_auth_open"] = False
                    st.rerun()
                if ok:
                    if pin_try == _get_admin_pin():
                        st.session_state["is_admin"] = True
                        st.session_state["_admin_auth_open"] = False
                        try: st.toast("관리자 모드 진입 ✅")
                        except Exception: pass
                        st.rerun()  # 입장 직후 즉시 라벨 "관리자 종료"로
                    else:
                        st.error("PIN이 올바르지 않습니다.")
# ===== [04A-3] END ============================================================


# ── [04A-4] 역할 캡션 ---------------------------------------------------------
if st.session_state.get("is_admin", False):
    st.caption("역할: **관리자** — 상단 버튼으로 종료 가능")
else:
    st.caption("역할: **학생** — 질문/답변에 집중할 수 있게 단순화했어요.")

st.divider()
# ===== [04A] END =============================================================
# ===== [04B] 관리자 설정 — 이유문법 + 모드별 ON/OFF (라디오·세로배치) ==========
import json as _json
from pathlib import Path as _Path
import streamlit as st

# ── [04B-1] 설정 파일 경로/기본값 ---------------------------------------------
def _config_path() -> _Path:
    base = _Path.home() / ".maic"
    try: base.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return base / "config.json"

_DEFAULT_CFG = {
    "reason_grammar_enabled": False,  # 출시 기본: OFF
    "mode_enabled": {
        "Grammar":  True,   # 문법설명
        "Sentence": True,   # 문장분석
        "Passage":  True,   # 지문분석
    },
}

# ── [04B-2] 설정 로드/저장 -----------------------------------------------------
def _load_cfg() -> dict:
    cfg_file = _config_path()
    if not cfg_file.exists():
        return _DEFAULT_CFG.copy()
    try:
        data = _json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    # 누락 키 보정
    merged = _DEFAULT_CFG.copy()
    me = (data or {}).get("mode_enabled", {})
    if isinstance(me, dict):
        merged["mode_enabled"].update(me)
    if "reason_grammar_enabled" in (data or {}):
        merged["reason_grammar_enabled"] = bool(data["reason_grammar_enabled"])
    return merged

def _save_cfg(data: dict) -> None:
    cfg_file = _config_path()
    # 스키마 정규화 후 저장
    norm = _DEFAULT_CFG.copy()
    try:
        me = (data or {}).get("mode_enabled", {})
        if isinstance(me, dict):
            norm["mode_enabled"].update({k: bool(v) for k, v in me.items()})
    except Exception:
        pass
    norm["reason_grammar_enabled"] = bool((data or {}).get("reason_grammar_enabled", False))
    try:
        cfg_file.write_text(_json.dumps(norm, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        st.warning(f"설정 저장 실패: {type(e).__name__}: {e}")

# ── [04B-3] 세션/전역 접근자 ---------------------------------------------------
def _cfg_cache() -> dict:
    st.session_state.setdefault("_app_cfg_cache", _load_cfg())
    return st.session_state["_app_cfg_cache"]

def _cfg_get(key: str, default=None):
    return _cfg_cache().get(key, default)

def _cfg_set(key: str, value) -> None:
    _cfg_cache()[key] = value
    _save_cfg(st.session_state["_app_cfg_cache"])

def is_reason_grammar_enabled() -> bool:
    return bool(_cfg_get("reason_grammar_enabled", False))

def get_enabled_modes() -> dict:
    merged = _DEFAULT_CFG["mode_enabled"].copy()
    me = _cfg_get("mode_enabled", {})
    if isinstance(me, dict):
        merged.update({k: bool(v) for k, v in me.items()})
    return merged

# ── [04B-4] 관리자 UI(라디오형·세로배치·컴팩트) -------------------------------
def render_admin_settings_panel():
    """관리자용 설정 카드: 이유문법 + 모드별 ON/OFF (라디오·세로배치)"""
    if not st.session_state.get("is_admin", False):
        return

    # 라디오 간격을 조금 줄여 모바일에서도 컴팩트하게
    st.markdown("""
    <style>
      .stRadio > div { row-gap: 0.25rem; }
      .st-emotion-cache-10trblm p { margin-bottom: 0.35rem; }
    </style>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("관리자 설정")
        st.caption("동그란 선택지에서 ‘켜기/끄기’를 고르면 바로 반영됩니다. (자동 저장·자동 새로고침)")

        # 현재 설정 로드
        current_rg = is_reason_grammar_enabled()
        me = get_enabled_modes()

        # (A) 이유문법 — 라디오(끄기/켜기)
        st.markdown("**이유문법 설명(Reason Grammar)**")
        rg_choice = st.radio(
            label="이유문법 설명",
            options=["끄기", "켜기"],
            index=(1 if current_rg else 0),
            horizontal=True,
            key="rg_radio",
        )

        # (B) 모드별 — 세로로 각 라디오
        st.markdown("### 질문 모드 표시 여부")
        g_choice = st.radio(
            label="문법설명 (Grammar)",
            options=["끄기", "켜기"],
            index=(1 if me.get("Grammar", True) else 0),
            horizontal=True,
            key="mode_g_radio",
        )
        s_choice = st.radio(
            label="문장분석 (Sentence)",
            options=["끄기", "켜기"],
            index=(1 if me.get("Sentence", True) else 0),
            horizontal=True,
            key="mode_s_radio",
        )
        p_choice = st.radio(
            label="지문분석 (Passage)",
            options=["끄기", "켜기"],
            index=(1 if me.get("Passage", True) else 0),
            horizontal=True,
            key="mode_p_radio",
        )

        # 값 변환
        new_rg = (rg_choice == "켜기")
        new_me = {
            "Grammar":  (g_choice == "켜기"),
            "Sentence": (s_choice == "켜기"),
            "Passage":  (p_choice == "켜기"),
        }

        # 변경 감지 → 저장 (Streamlit이 자동 rerun 하므로 st.rerun() 불필요)
        changed = (new_rg != current_rg) or any(new_me.get(k) != me.get(k) for k in ("Grammar","Sentence","Passage"))
        if changed:
            _cfg_set("reason_grammar_enabled", bool(new_rg))
            # 기존 값에 덮어쓰기 형식으로 저장
            merged = get_enabled_modes()
            merged.update(new_me)
            _cfg_set("mode_enabled", merged)
            try:
                on_list = [k for k, v in merged.items() if v]
                st.toast("저장됨 · 켜진 모드: " + (", ".join(on_list) if on_list else "없음"))
            except Exception:
                pass

        # (미리보기) 학생에게 보이는 모드 안내
        enabled_list = [name for name, on in get_enabled_modes().items() if on]
        if enabled_list:
            st.info("학생에게 표시되는 모드: " + ", ".join(enabled_list))
        else:
            st.error("모든 모드가 꺼져 있습니다. 학생 화면에서 질문 모드가 보이지 않아요.")
# ===== [04B] END =============================================================


# ===== [05A] BRAIN PREP MAIN =======================================
def render_brain_prep_main():
    """
    관리자 준비 패널(다이어트 버전)
    - ready 상태: UI 완전 숨김(아무 것도 렌더하지 않음)
    - missing/pending: 최소 안내만, 버튼 없음
    - Advanced(고급)에서만 수동 조치(강제 복구 / 다시 최적화 / 품질 리포트 재생성)
    """
    import importlib
    from pathlib import Path
    import streamlit as st

    # 현재 인덱스 상태: 'ready' | 'pending' | 'missing'
    try:
        status = get_index_status()
    except Exception:
        status = "missing"

    # 1) ready면 패널 자체를 숨김(중복 UI 제거)
    if status == "ready":
        return

    # 2) 최소 안내(버튼 없음)
    with st.container(border=True):
        if status == "missing":
            st.warning(
                "로컬 인덱스가 없습니다. 상단 플로우에서 **백업 복구→자동 연결**을 먼저 시도합니다.\n"
                "필요 시 아래 **고급(Advanced)**에서 수동으로 복구/다시 최적화를 실행할 수 있습니다."
            )
        else:  # 'pending'
            st.info(
                "로컬 인덱스 신호(.ready/chunks.jsonl)는 있으나 세션 미연결 상태입니다.\n"
                "잠시 후 자동 연결되며, 필요 시 **고급(Advanced)**에서 수동 조치가 가능합니다."
            )

    # 3) Advanced(수동 조치 전용)
    with st.expander("고급(Advanced) — 문제가 있을 때만 사용", expanded=False):
        st.caption("아래 동작은 관리자 전용 수동 조치입니다.")

        # a) 최신 백업에서 강제 복구 → 연결
        if st.button("📦 최신 백업에서 강제 복구 → 연결", key="adv_force_restore"):
            try:
                mod = importlib.import_module("src.rag.index_build")
                restore_fn = getattr(mod, "restore_latest_backup_to_local", None)
                if not callable(restore_fn):
                    st.error("복구 함수를 찾지 못했습니다. (restore_latest_backup_to_local)")
                else:
                    with st.status("백업에서 로컬로 복구 중…", state="running") as s:
                        res = restore_fn()
                        if not (res and res.get("ok")):
                            s.update(label="복구 실패 ❌", state="error")
                            st.error(f"복구 실패: {res.get('error') if res else 'unknown'}")
                        else:
                            s.update(label="복구 완료 ✅", state="complete")
                            with st.status("두뇌 연결 중…", state="running") as s2:
                                ok = _auto_attach_or_restore_silently()
                                if ok:
                                    s2.update(label="두뇌 연결 완료 ✅", state="complete")
                                    st.rerun()
                                else:
                                    s2.update(label="두뇌 연결 실패 ❌", state="error")
            except Exception as e:
                st.error(f"강제 복구 중 오류: {type(e).__name__}: {e}")

        # b) 다시 최적화 실행 → 백업 업로드 → 복구 → 연결
        if st.button("🛠 다시 최적화 실행 → 백업 업로드 → 복구 → 연결", key="adv_rebuild_pipeline"):
            try:
                try:
                    mod = importlib.import_module("src.rag.index_build")
                except Exception as e:
                    st.error(f"인덱스 빌더 모듈 임포트 실패: {type(e).__name__}: {e}")
                    mod = None

                build_fn = getattr(mod, "build_index_with_checkpoint", None) if mod else None
                upload_zip_fn = getattr(mod, "_make_and_upload_backup_zip", None) if mod else None
                persist_dir = getattr(mod, "PERSIST_DIR", Path.home() / ".maic" / "persist") if mod else (Path.home() / ".maic" / "persist")
                restore_fn = getattr(mod, "restore_latest_backup_to_local", None) if mod else None

                if not callable(build_fn):
                    st.error("인덱스 빌더 함수를 찾지 못했습니다. (build_index_with_checkpoint)")
                else:
                    prog = st.progress(0); log = st.empty()
                    def _pct(v: int, msg: str | None = None):
                        try:
                            prog.progress(max(0, min(int(v), 100)))
                        except Exception:
                            pass
                        if msg: log.info(str(msg))
                    def _msg(s: str): log.write(f"• {s}")

                    with st.status("다시 최적화 실행 중…", state="running") as s:
                        res = build_fn(
                            update_pct=_pct, update_msg=_msg,
                            gdrive_folder_id="", gcp_creds={},
                            persist_dir=str(persist_dir), remote_manifest={}
                        )
                        prog.progress(100)
                        s.update(label="다시 최적화 완료 ✅", state="complete")
                    st.json(res)

                    # ZIP 업로드(있으면)
                    try:
                        if callable(upload_zip_fn):
                            _ = upload_zip_fn(None, None)
                    except Exception:
                        pass

                    # 최신 ZIP으로 복구 후 연결
                    if callable(restore_fn):
                        with st.status("백업에서 로컬로 복구 중…", state="running") as s2:
                            rr = restore_fn()
                            if not (rr and rr.get("ok")):
                                s2.update(label="복구 실패 ❌", state="error")
                                st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}")
                            else:
                                s2.update(label="복구 완료 ✅", state="complete")

                    with st.status("두뇌 연결 중…", state="running") as s3:
                        ok = _auto_attach_or_restore_silently()
                        if ok:
                            s3.update(label="두뇌 연결 완료 ✅", state="complete")
                            st.rerun()
                        else:
                            s3.update(label="두뇌 연결 실패 ❌", state="error")
            except Exception as e:
                st.error(f"재최적화 파이프라인 중 오류: {type(e).__name__}: {e}")

        # c) 품질 리포트 다시 생성(강제)
        if st.button("📊 품질 리포트 다시 생성(강제)", key="adv_regen_quality"):
            try:
                mod = importlib.import_module("src.rag.index_build")
                force_fn = getattr(mod, "_quality_report", None)
                auto_fn  = getattr(mod, "autorun_quality_scan_if_stale", None)
                if callable(force_fn):
                    with st.status("품질 리포트 생성 중…", state="running") as s:
                        r = force_fn(None, extra_counts=None, top_n=20)
                        s.update(label="생성 완료 ✅", state="complete")
                        st.success(f"저장 경로: {r.get('path', '~/.maic/quality_report.json')}")
                elif callable(auto_fn):
                    r = auto_fn(top_n=20)
                    if r.get("ok") and not r.get("skipped"):
                        st.success("품질 리포트 갱신 완료 ✅")
                    elif r.get("skipped"):
                        st.info("이미 최신입니다. (스킵됨)")
                    else:
                        st.error("품질 리포트 갱신 실패")
                else:
                    st.error("품질 리포트 함수를 찾지 못했습니다.")
            except Exception as e:
                st.error(f"품질 리포트 생성 중 오류: {type(e).__name__}: {e}")
# ===== [05A] END ===========================================


# ===== [05B] TAG DIAGNOSTICS (NEW) ==========================================
def render_tag_diagnostics():
    """
    태그/인덱스 진단 패널
    - quality_report.json 유무
    - 로컬 ZIP: backup_*.zip + restored_*.zip (최신 5개)
    - 드라이브 ZIP: backup_zip 폴더의 ZIP (최신 5개)
    - 로컬 인덱스 파일(.ready, chunks.jsonl) 표시
    """
    import importlib, traceback
    from pathlib import Path
    from datetime import datetime
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

    def _fmt_size(n):
        try:
            n = int(n)
        except Exception:
            return "-"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        f = float(n)
        while f >= 1024 and i < len(units) - 1:
            f /= 1024.0
            i += 1
        if i == 0:
            return f"{int(f)} {units[i]}"
        return f"{f:.1f} {units[i]}"

    def _fmt_ts(ts):
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "-"

    st.subheader("진단(간단)", anchor=False)

    # ── 품질 리포트 존재 ─────────────────────────────────────────────────────────
    qr_exists = QUALITY_REPORT_PATH.exists()
    qr_badge = "✅ 있음" if qr_exists else "❌ 없음"
    st.markdown(f"- **품질 리포트(quality_report.json)**: {qr_badge}  (`{QUALITY_REPORT_PATH.as_posix()}`)")

    # ── 로컬 ZIP 목록: backup_* + restored_* (최신 5) ───────────────────────────
    local_rows = []
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        zips = list(BACKUP_DIR.glob("backup_*.zip")) + list(BACKUP_DIR.glob("restored_*.zip"))
        zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in zips[:5]:
            stt = p.stat()
            local_rows.append({"파일명": p.name, "크기": _fmt_size(stt.st_size), "수정시각": _fmt_ts(stt.st_mtime)})
    except Exception:
        pass

    # ── 드라이브 ZIP 목록(top5) ─────────────────────────────────────────────────
    drive_rows = []
    drive_msg = None
    try:
        _drive_service = getattr(_m, "_drive_service", None) if _m else None
        _pick_backup_folder_id = getattr(_m, "_pick_backup_folder_id", None) if _m else None
        svc = _drive_service() if callable(_drive_service) else None
        fid = _pick_backup_folder_id(svc) if callable(_pick_backup_folder_id) else None
        if svc and fid:
            resp = svc.files().list(
                q=f"'{fid}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
                fields="files(id,name,modifiedTime,size,mimeType)",
                includeItemsFromAllDrives=True, supportsAllDrives=True, corpora="allDrives", pageSize=1000
            ).execute()
            files = [f for f in resp.get("files", []) if (f.get("name","").lower().endswith(".zip"))]
            files.sort(key=lambda x: x.get("modifiedTime") or "", reverse=True)
            for f in files[:5]:
                drive_rows.append({
                    "파일명": f.get("name",""),
                    "크기": _fmt_size(f.get("size") or 0),
                    "수정시각(UTC)": (f.get("modifiedTime","")[:16].replace("T"," ") if f.get("modifiedTime") else "-"),
                })
        else:
            drive_msg = "드라이브 연결/권한 또는 백업 폴더 ID가 없습니다."
    except Exception:
        drive_msg = "드라이브 목록 조회 중 오류가 발생했습니다."

    # ── 렌더링 ──────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("### 백업 ZIP 현황", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.caption("로컬 백업 (최신 5)")
            if local_rows:
                st.dataframe(local_rows, use_container_width=True, hide_index=True)
            else:
                st.markdown("— 표시할 로컬 ZIP이 없습니다.")
                st.caption("※ 복구가 로컬 ZIP로 진행된 경우에는 `restored_*` 캐시가 남지 않을 수 있습니다.")
        with c2:
            st.caption("드라이브 backup_zip (최신 5)")
            if drive_rows:
                st.dataframe(drive_rows, use_container_width=True, hide_index=True)
            else:
                st.markdown("— 표시할 드라이브 ZIP이 없습니다.")
                if drive_msg:
                    st.caption(f"※ {drive_msg}")

    # ── 로컬 인덱스 파일 상태 ───────────────────────────────────────────────────
    try:
        chunks = (Path(PERSIST_DIR) / "chunks.jsonl")
        ready = (Path(PERSIST_DIR) / ".ready")
        st.markdown("- **로컬 인덱스 파일**: " + ("✅ 있음" if chunks.exists() else "❌ 없음") + f" (`{chunks.as_posix()}`)")
        st.markdown("- **.ready 마커**: " + ("✅ 있음" if ready.exists() else "❌ 없음") + f" (`{ready.as_posix()}`)")
    except Exception:
        pass

# ===== [06] SIMPLE QA DEMO — 히스토리 인라인 + 답변 직표시 + 합성응답 + Fallback ==
from pathlib import Path
from typing import Any, Dict, List, Tuple
import time
import streamlit as st

# ── [06-A] 세션/캐시 준비 -------------------------------------------------------
def _ensure_state():
    if "answer_cache" not in st.session_state:
        st.session_state["answer_cache"] = {}  # norm -> {"answer","refs","mode","ts"}
    if "last_submit_key" not in st.session_state:
        st.session_state["last_submit_key"] = None
    if "last_submit_ts" not in st.session_state:
        st.session_state["last_submit_ts"] = 0
    if "SHOW_TOP3_STICKY" not in st.session_state:
        st.session_state["SHOW_TOP3_STICKY"] = False
    if "allow_fallback" not in st.session_state:
        st.session_state["allow_fallback"] = True  # 교재 no-hit 시 일반 지식 모드 허용

# ── [06-A’] 준비/토글 통일 판단 -------------------------------------------------
def _is_ready_unified() -> bool:
    """헤더와 동일 기준: get_index_status() == 'ready'"""
    try:
        return (get_index_status() == "ready")
    except Exception:
        return bool(st.session_state.get("rag_index"))

def _get_enabled_modes_unified() -> Dict[str, bool]:
    # 1) 세션 우선
    for key in ("enabled_modes", "admin_modes", "modes"):
        m = st.session_state.get(key)
        if isinstance(m, dict):
            return {
                "Grammar": bool(m.get("Grammar", False)),
                "Sentence": bool(m.get("Sentence", False)),
                "Passage": bool(m.get("Passage", False)),
            }
    # 2) 전역 함수
    fn = globals().get("get_enabled_modes")
    if callable(fn):
        try:
            m = fn()
            if isinstance(m, dict):
                return {
                    "Grammar": bool(m.get("Grammar", False)),
                    "Sentence": bool(m.get("Sentence", False)),
                    "Passage": bool(m.get("Passage", False)),
                }
        except Exception:
            pass
    # 3) 기본값 — 비관리자만 임시 허용, 관리자는 보수적 차단
    if not st.session_state.get("is_admin", False):
        return {"Grammar": True, "Sentence": True, "Passage": True}
    return {"Grammar": False, "Sentence": False, "Passage": False}

# ── [06-B] 파일 I/O (히스토리) -------------------------------------------------
def _history_path() -> Path:
    p = Path.home() / ".maic"
    try: p.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return p / "qa_history.jsonl"

def _sanitize_user(name: str | None) -> str:
    import re as _re
    s = (name or "").strip()
    s = _re.sub(r"\s+", " ", s)[:40]
    return s or "guest"

def _append_history_file_only(q: str, user: str | None = None):
    try:
        q = (q or "").strip()
        if not q: return
        user = _sanitize_user(user)
        import json as _json
        with _history_path().open("a", encoding="utf-8") as f:
            f.write(_json.dumps({"ts": int(time.time()), "q": q, "user": user}, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _read_history_lines(max_lines: int = 5000) -> List[Dict[str, Any]]:
    import json as _json
    hp = _history_path()
    if not hp.exists(): return []
    rows: List[Dict[str, Any]] = []
    try:
        with hp.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max_lines:]
        for ln in lines:
            try:
                r = _json.loads(ln); r.setdefault("user","guest"); rows.append(r)
            except Exception: continue
    except Exception:
        return []
    rows.reverse()
    return rows

def _normalize_question(s: str) -> str:
    import re as _re
    s = (s or "").strip().lower()
    s = _re.sub(r"[!?。．！?]+$", "", s)
    s = _re.sub(r"[^\w\sㄱ-ㅎ가-힣]", " ", s)
    s = _re.sub(r"\s+", " ", s).strip()
    return s

# ── [06-C] 인기/Top3(파일 기준) ------------------------------------------------
def _top3_users(days: int = 7) -> List[Tuple[str, int]]:
    from collections import Counter
    rows = _read_history_lines(max_lines=5000)
    if not rows: return []
    cutoff = int(time.time()) - days * 86400
    users: List[str] = []
    for r in rows:
        ts = int(r.get("ts") or 0)
        if ts < cutoff: continue
        if (r.get("q") or "").strip(): users.append(_sanitize_user(r.get("user")))
    ctr = Counter(users); return ctr.most_common(3)

def _popular_questions(top_n: int = 10, days: int = 14) -> List[Tuple[str, int]]:
    from collections import Counter
    rows = _read_history_lines(max_lines=5000)
    if not rows: return []
    cutoff = int(time.time()) - days * 86400 if days and days > 0 else 0
    counter: Counter[str] = Counter(); exemplar: Dict[str, str] = {}
    for r in rows:
        ts = int(r.get("ts") or 0)
        if cutoff and ts and ts < cutoff: continue
        q = (r.get("q") or "").strip()
        key = _normalize_question(q)
        if not key: continue
        counter[key] += 1
        if key not in exemplar or len(q) < len(exemplar[key]): exemplar[key] = q
    return [(exemplar[k], c) for k, c in counter.most_common(top_n)]

def _render_top3_badges():
    if not st.session_state.get("SHOW_TOP3_STICKY"):
        return
    data = list(_top3_users()[:3])
    while len(data) < 3: data.append(("…", 0))
    medals = ["🥇","🥈","🥉"]
    css = """
    <style>
      .sticky-top3 { position: sticky; top: 0; z-index: 999; padding: 6px 8px;
                     background: rgba(0,0,0,0.25); border-bottom: 1px solid #333; }
      .pill { margin-right:6px; padding:4px 8px; border-radius:999px; font-size:0.9rem;
              background: rgba(37,99,235,0.18); color:#cfe0ff; border:1px solid rgba(37,99,235,0.45); }
    </style>"""
    pills = " ".join(f"<span class='pill'>{medals[i]} {n} · {c}회</span>" for i,(n,c) in enumerate(data))
    st.markdown(css + f"<div class='sticky-top3'>{pills}</div>", unsafe_allow_html=True)

# ── [06-D] 과거 답변 캐시 ------------------------------------------------------
def _cache_put(q: str, answer: str, refs: List[Dict[str,str]], mode_label: str):
    _ensure_state()
    norm = _normalize_question(q)
    st.session_state["answer_cache"][norm] = {
        "answer": (answer or "").strip(),
        "refs": refs or [],
        "mode": mode_label,
        "ts": int(time.time()),
    }

def _cache_get(norm: str) -> Dict[str, Any] | None:
    _ensure_state()
    return st.session_state["answer_cache"].get(norm)

def _render_cached_block(norm: str):
    """히스토리 펼침: 답변 본문을 즉시 보여주고, 근거만 선택사항(expander)"""
    data = _cache_get(norm)
    if not data:
        st.info("이 질문의 저장된 답변이 없어요. 아래 ‘다시 검색’으로 최신 답변을 받아보세요.")
        return
    st.write(data.get("answer","—"))
    refs = data.get("refs") or []
    if refs:
        with st.expander("근거 자료(상위 2개)"):
            for i, r0 in enumerate(refs[:2], start=1):
                name = r0.get("doc_id") or r0.get("source") or f"ref{i}"
                url = r0.get("url") or r0.get("source_url") or ""
                st.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

# ── [06-D’] 일반 지식 Fallback -------------------------------------------------
def _fallback_general_answer(q: str, mode_key: str) -> str | None:
    prompt = (
        "너는 한국 학생에게 영어를 쉽게 설명하는 선생님이야. 아래 질문에 대해 "
        "핵심 개념을 3~5문장으로 설명하고, 간단한 예문 2개를 제시하고, 마지막에 한 줄 요령을 적어줘.\n"
        f"[질문유형:{mode_key}] 질문: {q}\n"
        "형식: 1) 핵심 설명 2) 예문-해석 3) 한 줄 요령\n"
        "주의: 과도한 배경 지식은 생략하고, 정확하게. 한국어로 답변."
    )
    for key in ("general_llm", "llm", "chat_llm"):
        llm = st.session_state.get(key)
        if llm:
            try:
                if hasattr(llm, "complete"):
                    r = llm.complete(prompt); return getattr(r, "text", None) or str(r)
                if hasattr(llm, "predict"):
                    return llm.predict(prompt)
                if hasattr(llm, "chat"):
                    r = llm.chat(prompt); return getattr(r, "text", None) or str(r)
            except Exception:
                pass
    for fn_name in ("call_general_llm", "call_openai_chat", "call_gemini_chat", "generate_general_answer"):
        fn = globals().get(fn_name)
        if callable(fn):
            try:
                r = fn(prompt)
                if isinstance(r, str) and r.strip(): return r
                if hasattr(r, "text"): return r.text
            except Exception:
                pass
    return ("일반 지식 모드가 비활성화되어 있어요. 관리자에서 일반 지식 LLM 연결을 켜면 "
            "교재에 없더라도 기본 설명을 제공할 수 있어요.")

# ── [06-D’’] 한국어→영어 용어 확장(Grammar 중심) -------------------------------
def _expand_query_for_rag(q: str, mode_key: str) -> str:
    q0 = (q or "").strip()
    if not q0: return q0
    ko_en = {
        "관계대명사": "relative pronoun|relative pronouns|relative clause",
        "관계절": "relative clause",
        "관계부사": "relative adverb|relative adverbs",
        "현재완료": "present perfect",
        "과거완료": "past perfect",
        "진행형": "progressive|continuous",
        "수동태": "passive voice",
        "가정법": "subjunctive|conditional",
        "비교급": "comparative",
        "최상급": "superlative",
        "to부정사": "to-infinitive|infinitive",
        "동명사": "gerund",
        "분사구문": "participial construction|participial phrase",
        "명사절": "noun clause",
        "형용사절": "adjective clause|relative clause",
        "부사절": "adverbial clause",
        "간접화법": "reported speech|indirect speech",
        "시제": "tenses|tense",
        "조동사": "modal verb|modal verbs",
        "가주어": "expletive there/it|dummy subject",
        "도치": "inversion",
        "대동사": "do-support|pro-verb do",
        "강조구문": "cleft sentence|it-cleft|wh-cleft",
    }
    extras = []
    for ko, en in ko_en.items():
        if ko in q0:
            extras.extend([en, f'"{en}"'])
    if mode_key == "Grammar":
        extras += ["grammar explanation", "ESL", "examples", "usage"]
    merged = []
    for t in [q0] + extras:
        if t and t not in merged:
            merged.append(t)
    return " ".join(merged)

# ── [06-D’’’] ★합성 응답: 매치 목록 → 학생용 설명으로 변환 -----------------------
def _looks_like_debug_listing(text: str) -> bool:
    t = (text or "").strip().lower()
    return (not t) or t.startswith("top matches") or "score=" in t

def _extract_hit_text(h) -> str:
    for attr in ("text", "content", "page_content"):
        t = getattr(h, attr, None)
        if t: return str(t)
    node = getattr(h, "node", None)
    if node:
        for cand in ("get_content", "get_text"):
            fn = getattr(node, cand, None)
            if callable(fn):
                try:
                    t = fn()
                    if t: return str(t)
                except Exception:
                    pass
        t = getattr(node, "text", None)
        if t: return str(t)
    return ""

def _compose_answer_from_hits(q: str, hits: Any, mode_key: str) -> str:
    """매치된 교재 조각들로부터 학생용 설명 합성(LLM 사용)."""
    # 1) 컨텍스트 추출/절단
    ctx_parts: List[str] = []
    if hits:
        for h in list(hits)[:4]:
            t = _extract_hit_text(h)
            if not t: continue
            t = t.replace("\n", " ").strip()
            if t:
                ctx_parts.append(t)
            if sum(len(x) for x in ctx_parts) > 2000:
                break
    context = "\n\n".join(ctx_parts).strip()
    if not context:
        return ""

    # 2) 합성 프롬프트
    prompt = (
        "너는 한국 중고등학생에게 영어 문법을 가르치는 선생님이야. "
        "아래 [교재 발췌]를 근거로, 질문에 대해 간단하지만 정확한 한국어 설명을 만들어줘. "
        "형식: 1) 핵심 설명(3~5문장) 2) 예문 2개(영문+한국어 해석) 3) 한 줄 요령.\n\n"
        f"[질문] {q}\n\n[교재 발췌]\n{context}\n"
        "주의: 교재에 없는 정보는 상상하지 말고, 용어는 영어/한국어 병기해도 좋아."
    )

    # 3) LLM 호출 (세션/헬퍼 동원)
    for key in ("general_llm", "llm", "chat_llm"):
        llm = st.session_state.get(key)
        if llm:
            try:
                if hasattr(llm, "complete"):
                    r = llm.complete(prompt); return getattr(r, "text", None) or str(r)
                if hasattr(llm, "predict"):
                    return llm.predict(prompt)
                if hasattr(llm, "chat"):
                    r = llm.chat(prompt); return getattr(r, "text", None) or str(r)
            except Exception:
                pass
    for fn_name in ("call_general_llm", "call_openai_chat", "call_gemini_chat", "generate_general_answer"):
        fn = globals().get(fn_name)
        if callable(fn):
            try:
                r = fn(prompt)
                if isinstance(r, str) and r.strip(): return r
                if hasattr(r, "text"): return r.text
            except Exception:
                pass
    # 4) 최후: LLM이 전혀 없을 때는 발췌 그대로 반환(디버그 노출 방지)
    return "아래 교재 발췌를 참고해서 정리해 볼래?\n\n" + context[:1200]

# ── [06-E] 메인 렌더 -----------------------------------------------------------
def render_simple_qa():
    _ensure_state()
    is_admin = st.session_state.get("is_admin", False)

    _render_top3_badges()
    st.markdown("### 💬 질문은 모든 천재들이 가장 많이 사용하는 공부 방법이다!")

    # 관리자 토글 반영: 라디오 옵션
    enabled = _get_enabled_modes_unified()
    radio_opts: List[str] = []
    if enabled.get("Grammar", False):  radio_opts.append("문법설명(Grammar)")
    if enabled.get("Sentence", False): radio_opts.append("문장분석(Sentence)")
    if enabled.get("Passage", False):  radio_opts.append("지문분석(Passage)")
    if not radio_opts:
        st.error("관리자에서 모든 질문 모드를 OFF로 설정했습니다. 관리자에게 문의하세요.")
        return

    mode_choice = st.radio("질문의 종류를 선택하세요", options=radio_opts, key="mode_radio", horizontal=True)
    if "문법" in mode_choice: mode_key, mode_label = "Grammar", "문법설명(Grammar)"
    elif "문장" in mode_choice: mode_key, mode_label = "Sentence", "문장분석(Sentence)"
    else: mode_key, mode_label = "Passage", "지문분석(Passage)"
    st.session_state["mode"] = mode_key

    if not is_admin:
        st.text_input("내 이름(임시)", key="student_name", placeholder="예: 지민 / 민수 / 유나")

    # 질문 폼
    placeholder = (
        "예: 관계대명사 which 사용법을 알려줘" if mode_key == "Grammar"
        else "예: I seen the movie yesterday 문장 문제점 분석해줘" if mode_key == "Sentence"
        else "예: 이 지문 핵심 요약과 제목 3개, 주제 1개 제안해줘"
    )
    with st.form("qa_form", clear_on_submit=False):
        q = st.text_input("질문 입력", value=st.session_state.get("qa_q",""), placeholder=placeholder, key="qa_q_form")
        k = st.slider("검색 결과 개수(top_k)", 1, 10, 5, key="qa_k") if is_admin else 5
        submitted = st.form_submit_button("🧑‍🏫 쌤에게 물어보기")
    if "qa_q_form" in st.session_state:
        st.session_state["qa_q"] = st.session_state["qa_q_form"]

    # 제출 차단: 꺼진 모드는 실행 불가
    if submitted and not enabled.get(mode_key, False):
        st.warning("이 질문 유형은 지금 관리자에서 꺼져 있어요. 다른 유형을 선택해 주세요.")
        return

    # 새 질문 처리 — 곧바로 답변 본문 출력
    if submitted and (st.session_state.get("qa_q","").strip()):
        q = st.session_state["qa_q"].strip()
        guard_key = f"{_normalize_question(q)}|{mode_key}"
        now = time.time()
        if not (st.session_state.get("last_submit_key") == guard_key and (now - st.session_state.get("last_submit_ts",0) < 1.5)):
            st.session_state["last_submit_key"] = guard_key
            st.session_state["last_submit_ts"] = now

            user = _sanitize_user(st.session_state.get("student_name") if not is_admin else "admin")
            _append_history_file_only(q, user)

            answer_box = st.container()
            index_ready = _is_ready_unified()

            if index_ready:
                try:
                    with answer_box:
                        # 한국어→영어 용어 확장 적용
                        q_expanded = _expand_query_for_rag(q, mode_key)

                        # 1차 검색
                        qe = st.session_state["rag_index"].as_query_engine(top_k=k)
                        r = qe.query(q_expanded)
                        raw = getattr(r, "response", "") or ""
                        hits = getattr(r, "source_nodes", None) or getattr(r, "hits", None)

                        # no-hit 판단
                        def _is_nohit(raw_txt, hits_obj) -> bool:
                            txt = (raw_txt or "").strip().lower()
                            bad_phrases = ["관련 결과를 찾지 못", "no relevant", "no result", "not find"]
                            cond_txt = (not txt) or any(p in txt for p in bad_phrases)
                            cond_hits = (not hits_obj) or (hasattr(hits_obj, "__len__") and len(hits_obj) == 0)
                            return cond_txt or cond_hits

                        if _is_nohit(raw, hits):
                            # 2차: 더 넓게 재검색
                            qe_wide = st.session_state["rag_index"].as_query_engine(top_k=max(10, int(k) if isinstance(k,int) else 5))
                            r2 = qe_wide.query(q_expanded)
                            raw2 = getattr(r2, "response", "") or ""
                            hits2 = getattr(r2, "source_nodes", None) or getattr(r2, "hits", None)
                            if not _is_nohit(raw2, hits2):
                                raw, hits = raw2, hits2
                            else:
                                # Fallback: 일반 지식
                                if st.session_state.get("allow_fallback", True):
                                    fb = _fallback_general_answer(q, mode_key) or ""
                                    st.write(fb.strip() or "—")
                                    st.caption("※ 교재 근거 없음 — 일반 지식으로 답변했어요.")
                                    _cache_put(q, fb, [], f"{mode_label} · Fallback")
                                else:
                                    st.warning("교재에서 딱 맞는 근거를 찾지 못했어요. 질문을 더 구체적으로 써 주세요.\n예: “현재완료 기본형을 예문 2개로 설명해줘”")
                                return

                        # 🔁 합성 단계: 응답이 비었거나 디버그 목록이면 교재 기반으로 합성
                        if _looks_like_debug_listing(raw):
                            raw = _compose_answer_from_hits(q, hits, mode_key)

                        # ✅ 학생용 답변 본문
                        st.write((raw or "").strip() or "—")

                        # 근거 자료(선택)
                        refs: List[Dict[str, str]] = []
                        if hits:
                            for h in hits[:2]:
                                meta = getattr(h, "metadata", None) or getattr(h, "node", {}).get("metadata", {})
                                refs.append({
                                    "doc_id": (meta or {}).get("doc_id") or (meta or {}).get("file_name", ""),
                                    "url": (meta or {}).get("source") or (meta or {}).get("url", ""),
                                })
                        if refs:
                            with st.expander("근거 자료(상위 2개)"):
                                for i, r0 in enumerate(refs[:2], start=1):
                                    name = r0.get("doc_id") or r0.get("source") or f"ref{i}"
                                    url = r0.get("url") or r0.get("source_url") or ""
                                    st.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

                        _cache_put(q, raw, refs, mode_label)
                except Exception as e:
                    st.error(f"검색 실패: {type(e).__name__}: {e}")
            else:
                st.info("아직 두뇌가 준비되지 않았어요. 상단에서 **복구/연결** 또는 **다시 최적화**를 먼저 완료해 주세요.")

    # 📒 나의 질문 히스토리 — 인라인 펼치기(답변 직표시)
    rows = _read_history_lines(max_lines=5000)
    st.markdown("#### 📒 나의 질문 히스토리")
    uniq: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        qtext = (r.get("q") or "").strip()
        if not qtext: continue
        key = _normalize_question(qtext)
        if key in seen: continue
        seen.add(key); uniq.append({"q": qtext, "norm": key})
        if len(uniq) >= 3: break

    if not uniq:
        for i in range(1, 4):
            st.caption(f"{i}. …")
    else:
        for i in range(3):
            if i < len(uniq):
                title = f"{i+1}. {uniq[i]['q']}"
                with st.expander(title, expanded=False):
                    _render_cached_block(uniq[i]["norm"])
                    if st.button("🔄 이 질문으로 다시 검색", key=f"rehit_{uniq[i]['norm']}", use_container_width=True):
                        st.session_state["qa_q"] = uniq[i]["q"]
                        st.rerun()
            else:
                st.caption(f"{i+1}. …")

# ===== [06] END ===============================================================



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
    _render_title_with_status()

    # 1) 자동 연결/복구(가능하면 1회 시도) — missing/pending 모두 처리
    try:
        before = get_index_status()
    except Exception:
        before = "missing"

    try:
        needs_recovery = (before in ("missing", "pending")) and (not _is_attached_session())
        if needs_recovery:
            # 내부에서: 백업 복구 → 인덱스 attach (인자 없이 호출)
            _auto_attach_or_restore_silently()
            # 상태가 바뀌면 헤더/배지 동기화를 위해 재실행
            after = get_index_status()
            if after != before:
                st.rerun()
    except Exception:
        # 학생 화면에서는 조용히 통과(관리자 로그는 별도 영역에서 노출)
        pass

    # 2) 준비 패널(ready면 내부에서 자연히 최소 표시), 질문 패널
    try:
        render_brain_prep_main()
    except Exception:
        pass  # 모듈이 없으면 무시

    try:
        render_simple_qa()
    except Exception as e:
        st.error(f"질문 패널 렌더 중 오류: {type(e).__name__}: {e}")

    # 3) 관리자 전용 패널
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

if __name__ == "__main__":
    main()
# ===== [07] END ===============================================================
