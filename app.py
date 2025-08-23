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

# 모드/언어/제출 플래그
if "mode" not in st.session_state:
    st.session_state["mode"] = "Grammar"  # Grammar | Sentence | Passage
if "lang" not in st.session_state:
    st.session_state["lang"] = "한국어"     # 한국어 | English
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

def _index_status_badge() -> None:
    """헤더용 라벨(단일 기준 기반)."""
    status = get_index_status()
    if status == "ready":
        st.caption("Index status: ✅ ready")
    elif status == "pending":
        st.caption("Index status: 🟡 pending (연결 대기)")
    else:
        st.caption("Index status: ❌ missing (빌드 또는 복구 필요)")

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


# ===== [04A] MODE & LANG SWITCH =============================================
with st.container():
    c_mode, c_lang, c_info = st.columns([0.35, 0.20, 0.45])
    with c_mode:
        mode = st.segmented_control(
            "모드 선택",
            options=["Grammar", "Sentence", "Passage"],
            default=st.session_state.get("mode", "Grammar"),
            key="ui_mode_segmented",
        )
        st.session_state["mode"] = mode
    with c_lang:
        lang = st.segmented_control(
            "출력 언어",
            options=["한국어", "English"],
            default=st.session_state.get("lang", "한국어"),
            key="ui_lang_segmented",
        )
        st.session_state["lang"] = lang
    with c_info:
        if mode == "Grammar":
            st.caption("모드: **Grammar** — 문법 Q&A (태깅/부스팅 중심)")
        elif mode == "Sentence":
            st.caption("모드: **Sentence** — 문장 분석 (품사/구문/교정 프롬프트 중심)")
        else:
            st.caption("모드: **Passage** — 지문 설명 (요약→비유→제목/주제 프롬프트 중심)")

st.divider()

# ===== [05] RAG: Build/Restore Panels =======================================
def render_brain_prep_main():
    st.markdown("### 🧠 강의 준비 (자동 사전점검 기반)")

    # 자동 사전점검 결과
    pre = st.session_state.get("_precheck_res")
    had_auto = st.session_state.get("_precheck_auto_done", False)

    # 실제 PERSIST_DIR / 로컬 인덱스 존재 여부 --------------------------------
    import importlib
    from pathlib import Path
    try:
        _mod = importlib.import_module("src.rag.index_build")
        _PERSIST_DIR = getattr(_mod, "PERSIST_DIR", Path.home() / ".maic" / "persist")
    except Exception:
        _PERSIST_DIR = Path.home() / ".maic" / "persist"
    _chunks_path = _PERSIST_DIR / "chunks.jsonl"
    local_index_exists = _chunks_path.exists()

    # 상태 배너 ---------------------------------------------------------------
    banner = st.container()
    with banner:
        if pre:
            would = bool(pre.get("would_rebuild"))
            total = pre.get("total_files", 0)
            new_n = pre.get("new_docs", 0)
            upd_n = pre.get("updated_docs", 0)
            unchg = pre.get("unchanged_docs", 0)

            if not local_index_exists:
                st.warning("로컬 인덱스가 없습니다. **최초 빌드(재최적화)**가 필요합니다.")
            if would:
                st.info(f"🔎 자동 사전점검 결과: **신규 {new_n} / 변경 {upd_n} 건** 감지됨 · 총 {total}개 (변경 없음 {unchg})")
            else:
                st.success(f"🔎 자동 사전점검 결과: **변경 없음** · 총 {total}개 (변경 없음 {unchg})")
        else:
            if had_auto:
                st.warning("자동 사전점검을 시도했지만 결과를 가져오지 못했습니다. 네트워크/권한을 확인하거나 ‘다시 점검’을 눌러 주세요.")
            else:
                st.caption("자동 사전점검 준비 중…")

    st.divider()

    # 흐름형 CTA 패널 ---------------------------------------------------------
    cta = st.container()
    with cta:
        cols = st.columns([0.5, 0.5])
        with cols[0]:
            st.caption("현재 두뇌 상태")
            _index_status_badge()
        with cols[1]:
            st.caption("작업 선택")

        # 버튼 영역
        c1, c2 = st.columns([0.6, 0.4])

        # [A] 사전점검 결과가 있는 경우
        if pre:
            would = bool(pre.get("would_rebuild"))

            # (핵심) 로컬 인덱스가 없으면 ⇒ ‘최초 빌드(재최적화)’를 1차 CTA로 항상 표시
            if not local_index_exists:
                with c1:
                    if st.button("🛠 최초 빌드(재최적화)", type="primary", key="cta_first_build"):
                        if build_index_with_checkpoint is None:
                            st.error("인덱스 빌더 모듈을 찾지 못했습니다. (src.rag.index_build)")
                        else:
                            # 실제 PERSIST_DIR로 빌드
                            _persist_dir_arg = str(_PERSIST_DIR)
                            prog = st.progress(0)
                            log = st.empty()

                            def _pct(v: int, msg: str | None = None):
                                prog.progress(max(0, min(int(v), 100)))
                                if msg:
                                    log.info(str(msg))

                            def _msg(s: str):
                                log.write(f"• {s}")

                            try:
                                with st.status("재최적화 중…", state="running") as s:
                                    res = build_index_with_checkpoint(
                                        update_pct=_pct,
                                        update_msg=_msg,
                                        gdrive_folder_id="",
                                        gcp_creds={},
                                        persist_dir=_persist_dir_arg,
                                        remote_manifest={},
                                    )
                                    prog.progress(100)
                                    s.update(label="최적화 완료 ✅", state="complete")
                                st.success("최초 빌드가 완료되었습니다.")
                                st.json(res)
                                # 완료 후 자동 연결
                                try:
                                    with st.status("두뇌 연결을 준비 중…", state="running") as s2:
                                        bar = st.progress(0)
                                        bar.progress(15); time.sleep(0.12)
                                        ok = _auto_attach_or_restore_silently()
                                        bar.progress(100)
                                        if ok:
                                            s2.update(label="두뇌 연결 완료 ✅", state="complete")
                                            st.rerun()
                                        else:
                                            s2.update(label="두뇌 연결 실패 ❌", state="error")
                                except Exception:
                                    ok = _auto_attach_or_restore_silently()
                                    if ok:
                                        st.success("두뇌 연결 완료 ✅")
                                        st.rerun()
                                    else:
                                        st.error("두뇌 연결 실패. 다시 점검 후 재최적화를 실행하세요.")
                                # 사전점검 결과 초기화(다시 점검 유도)
                                st.session_state.pop("_precheck_res", None)
                            except Exception as e:
                                st.error(f"최적화 실패: {type(e).__name__}: {e}")

                with c2:
                    if st.button("🔄 다시 점검", key="cta_recheck_when_no_local"):
                        try:
                            if precheck_build_needed is None:
                                st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
                            else:
                                res = precheck_build_needed("")
                                st.session_state["_precheck_res"] = res
                                st.success("사전점검이 완료되었습니다.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"사전점검 실패: {type(e).__name__}: {e}")

            else:
                # 로컬 인덱스가 있는 경우: would에 따라 분기
                if would:
                    # 1차 CTA: 재최적화
                    with c1:
                        if st.button("🛠 재최적화 실행 (변경 반영)", type="primary", key="cta_build"):
                            if build_index_with_checkpoint is None:
                                st.error("인덱스 빌더 모듈을 찾지 못했습니다. (src.rag.index_build)")
                            else:
                                _persist_dir_arg = str(_PERSIST_DIR)
                                prog = st.progress(0)
                                log = st.empty()

                                def _pct(v: int, msg: str | None = None):
                                    prog.progress(max(0, min(int(v), 100)))
                                    if msg:
                                        log.info(str(msg))

                                def _msg(s: str):
                                    log.write(f"• {s}")

                                try:
                                    with st.status("재최적화 중…", state="running") as s:
                                        res = build_index_with_checkpoint(
                                            update_pct=_pct,
                                            update_msg=_msg,
                                            gdrive_folder_id="",
                                            gcp_creds={},
                                            persist_dir=_persist_dir_arg,  # ✅ 경로 고정
                                            remote_manifest={},
                                        )
                                        prog.progress(100)
                                        s.update(label="최적화 완료 ✅", state="complete")
                                    st.success("최적화가 완료되었습니다.")
                                    st.json(res)
                                    # 완료 후 자동 연결
                                    try:
                                        with st.status("두뇌 연결을 준비 중…", state="running") as s2:
                                            bar = st.progress(0)
                                            bar.progress(15); time.sleep(0.12)
                                            ok = _auto_attach_or_restore_silently()
                                            bar.progress(100)
                                            if ok:
                                                s2.update(label="두뇌 연결 완료 ✅", state="complete")
                                                st.rerun()
                                            else:
                                                s2.update(label="두뇌 연결 실패 ❌", state="error")
                                    except Exception:
                                        ok = _auto_attach_or_restore_silently()
                                        if ok:
                                            st.success("두뇌 연결 완료 ✅")
                                            st.rerun()
                                        else:
                                            st.error("두뇌 연결 실패. 다시 점검 후 재최적화를 실행하세요.")
                                    st.session_state.pop("_precheck_res", None)
                                except Exception as e:
                                    st.error(f"최적화 실패: {type(e).__name__}: {e}")

                    # 2차 CTA: 지금은 연결만
                    with c2:
                        if st.button("지금은 연결만", key="cta_connect_anyway"):
                            try:
                                with st.status("두뇌 연결을 준비 중…", state="running") as s:
                                    bar = st.progress(0)
                                    bar.progress(10); time.sleep(0.12)
                                    ok = _auto_attach_or_restore_silently()
                                    bar.progress(100)
                                    if ok:
                                        s.update(label="두뇌 연결 완료 ✅", state="complete")
                                        st.rerun()
                                    else:
                                        s.update(label="두뇌 연결 실패 ❌", state="error")
                                        st.error("먼저 재최적화를 실행해 인덱스를 만들어 주세요.")
                            except Exception:
                                with st.spinner("두뇌 연결 중…"):
                                    ok = _auto_attach_or_restore_silently()
                                if ok:
                                    st.success("두뇌 연결 완료 ✅")
                                    st.rerun()
                                else:
                                    st.error("두뇌 연결 실패. 먼저 재최적화를 실행해 인덱스를 만들어 주세요.")

                else:
                    # 변경 없음 → 1차 CTA: 바로 연결
                    with c1:
                        if st.button("🧠 두뇌 연결", type="primary", key="cta_connect"):
                            try:
                                with st.status("두뇌 연결을 준비 중…", state="running") as s:
                                    bar = st.progress(0)
                                    bar.progress(20); time.sleep(0.12)
                                    ok = _auto_attach_or_restore_silently()
                                    bar.progress(100)
                                    if ok:
                                        s.update(label="두뇌 연결 완료 ✅", state="complete")
                                        st.rerun()
                                    else:
                                        s.update(label="두뇌 연결 실패 ❌", state="error")
                                        st.error("두뇌 연결 실패. 필요 시 ‘다시 점검’ 후 재최적화를 실행하세요.")
                            except Exception:
                                with st.spinner("두뇌 연결 중…"):
                                    ok = _auto_attach_or_restore_silently()
                                if ok:
                                    st.success("두뇌 연결 완료 ✅")
                                    st.rerun()
                                else:
                                    st.error("두뇌 연결 실패. 필요 시 ‘다시 점검’ 후 재최적화를 실행하세요.")

                    with c2:
                        # 보조: 다시 점검
                        if st.button("🔄 다시 점검", key="cta_recheck"):
                            try:
                                if precheck_build_needed is None:
                                    st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
                                else:
                                    res = precheck_build_needed("")
                                    st.session_state["_precheck_res"] = res
                                    st.success("사전점검이 완료되었습니다.")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"사전점검 실패: {type(e).__name__}: {e}")

        # [B] 사전점검 결과가 없는 경우(자동 점검 실패 등)
        else:
            with c1:
                if st.button("🔎 사전점검 실행", type="primary", key="cta_precheck_manual"):
                    if precheck_build_needed is None:
                        st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
                    else:
                        try:
                            res = precheck_build_needed("")
                            st.session_state["_precheck_res"] = res
                            st.success("사전점검이 완료되었습니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"사전점검 실패: {type(e).__name__}: {e}")
            with c2:
                if st.button("🧠 두뇌 연결 시도", key="cta_connect_when_no_precheck"):
                    try:
                        with st.status("두뇌 연결을 준비 중…", state="running") as s:
                            bar = st.progress(0)
                            bar.progress(10); time.sleep(0.12)
                            ok = _auto_attach_or_restore_silently()
                            bar.progress(100)
                            if ok:
                                s.update(label="두뇌 연결 완료 ✅", state="complete")
                                st.rerun()
                            else:
                                s.update(label="두뇌 연결 실패 ❌", state="error")
                                st.error("먼저 사전점검/재최적화를 실행하세요.")
                    except Exception:
                        with st.spinner("두뇌 연결 중…"):
                            ok = _auto_attach_or_restore_silently()
                        if ok:
                            st.success("두뇌 연결 완료 ✅")
                            st.rerun()
                        else:
                            st.error("두뇌 연결 실패. 먼저 사전점검/재최적화를 실행하세요.")

    # Advanced(접기) — 강제 초기화 등 ----------------------------------------
    with st.expander("고급(Advanced)", expanded=False):
        st.caption("일반적으로는 필요 없습니다. 문제가 있을 때만 사용하세요.")
        if st.button("🧹 강제 초기화 (두뇌 캐시 삭제)", key="btn_reset_local_advanced"):
            try:
                base = Path.home() / ".maic"
                persist = base / "persist"
                if persist.exists():
                    import shutil
                    shutil.rmtree(persist)
                if "rag_index" in st.session_state:
                    st.session_state["rag_index"] = None
                st.success("두뇌 파일이 초기화되었습니다. 위의 ‘사전점검/재최적화→연결’ 순서로 다시 준비해 주세요.")
            except Exception as e:
                st.error(f"초기화 중 오류: {type(e).__name__}")
                st.exception(e)

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


# ===== [06] SIMPLE QA DEMO (mode-aware, ENTER SUBMIT, CHAT-AREA SPINNER) =====
def _sentence_quick_fix(user_q: str) -> List[Tuple[str, str]]:
    tips: List[Tuple[str, str]] = []
    if re.search(r"\bI\s+seen\b", user_q, flags=re.I):
        tips.append(("I seen", "I **saw** the movie / I **have seen** the movie"))
    if re.search(r"\b(he|she|it)\s+don'?t\b", user_q, flags=re.I):
        tips.append(("he/she/it don't", "**doesn't**"))
    if re.search(r"\ba\s+[aeiouAEIOU]", user_q):
        tips.append(("a + 모음 시작 명사", "가능하면 **an** + 모음 시작 명사"))
    return tips

def _render_clean_answer(mode: str, answer_text: str, refs: List[Dict[str, str]], lang: str):
    st.markdown(f"**선택 모드:** `{mode}` · **출력 언어:** `{lang}`")

    if lang == "한국어":
        st.markdown("#### ✅ 요약/안내 (한국어)")
        st.write("아래는 자료 기반 엔진의 원문 응답입니다. 현재 단계에서는 원문이 영어일 수 있어요.")
        with st.expander("원문 응답 보기(영문)"):
            st.write(answer_text.strip() or "—")
    else:
        st.markdown("#### ✅ Answer")
        st.write(answer_text.strip() or "—")

    if refs:
        with st.expander("근거 자료(상위 2개)"):
            for i, r in enumerate(refs[:2], start=1):
                name = r.get("doc_id") or r.get("source") or f"ref{i}"
                url = r.get("url") or r.get("source_url") or ""
                st.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

# Enter 제출용 on_change 콜백
def _on_q_enter():
    st.session_state["qa_submitted"] = True
    try:
        st.toast("✳️ 답변 준비 중…")
    except Exception:
        pass

def render_simple_qa():
    st.markdown("### 💬 질문해 보세요 (간단 데모)")
    if not _index_ready():
        st.info("아직 두뇌가 준비되지 않았어요. 상단의 **AI 두뇌 준비** 또는 **사전점검→재최적화**를 먼저 실행해 주세요.")
        return

    mode = st.session_state.get("mode", "Grammar")
    lang = st.session_state.get("lang", "한국어")

    if mode == "Grammar":
        placeholder = "예: 관계대명사 which 사용법을 알려줘"
    elif mode == "Sentence":
        placeholder = "예: I seen the movie yesterday 문장 문제점 분석해줘"
    else:
        placeholder = "예: 이 지문 핵심 요약과 제목 3개, 주제 1개 제안해줘"

    # --- 입력부 ---------------------------------------------------------------
    q = st.text_input("질문 입력", placeholder=placeholder, key="qa_q", on_change=_on_q_enter)
    k = st.slider("검색 결과 개수(top_k)", 1, 10, 5, key="qa_k")

    clicked = st.button("검색", key="qa_go")
    submitted = clicked or st.session_state.get("qa_submitted", False)

    # 답변 표시 영역(채팅 위치) 컨테이너
    answer_box = st.container()

    if submitted and (q or "").strip():
        st.session_state["qa_submitted"] = False
        try:
            with answer_box:
                with st.status("✳️ 답변 준비 중…", state="running") as s:
                    qe = st.session_state["rag_index"].as_query_engine(top_k=k)
                    r = qe.query(q)
                    raw_text = getattr(r, "response", "") or str(r)

                    refs: List[Dict[str, str]] = []
                    hits = getattr(r, "source_nodes", None) or getattr(r, "hits", None)
                    if hits:
                        for h in hits[:2]:
                            meta = getattr(h, "metadata", None) or getattr(h, "node", {}).get("metadata", {})
                            refs.append({
                                "doc_id": (meta or {}).get("doc_id") or (meta or {}).get("file_name", ""),
                                "url": (meta or {}).get("source") or (meta or {}).get("url", ""),
                            })

                    if mode == "Sentence":
                        fixes = _sentence_quick_fix(q)
                        if fixes:
                            st.markdown("#### ✍️ 빠른 교정 제안 (한국어)")
                            for bad, good in fixes:
                                st.markdown(f"- **{bad}** → {good}")

                    _render_clean_answer(mode, raw_text, refs, lang)
                    s.update(label="완료 ✅", state="complete")
        except Exception:
            with answer_box:
                with st.spinner("✳️ 답변 준비 중…"):
                    try:
                        qe = st.session_state["rag_index"].as_query_engine(top_k=k)
                        r = qe.query(q)
                        raw_text = getattr(r, "response", "") or str(r)
                        refs: List[Dict[str, str]] = []
                        hits = getattr(r, "source_nodes", None) or getattr(r, "hits", None)
                        if hits:
                            for h in hits[:2]:
                                meta = getattr(h, "metadata", None) or getattr(h, "node", {}).get("metadata", {})
                                refs.append({
                                    "doc_id": (meta or {}).get("doc_id") or (meta or {}).get("file_name", ""),
                                    "url": (meta or {}).get("source") or (meta or {}).get("url", ""),
                                })
                        if mode == "Sentence":
                            fixes = _sentence_quick_fix(q)
                            if fixes:
                                st.markdown("#### ✍️ 빠른 교정 제안 (한국어)")
                                for bad, good in fixes:
                                    st.markdown(f"- **{bad}** → {good}")
                        _render_clean_answer(mode, raw_text, refs, lang)
                    except Exception as e:
                        st.error(f"검색 실패: {type(e).__name__}: {e}")

# ===== [07] MAIN =============================================================
def main():
    # (A) 호환성 shim -----------------------------------------------------------
    # render_simple_qa 등 모듈 전역에서 사용할 수 있도록 전역 심볼로도 노출
    def _index_ready() -> bool:
        try:
            return get_index_status() == "ready"
        except Exception:
            return False
    globals()['_index_ready'] = _index_ready  # NameError 방지 전역 공개

    # 로컬 인덱스 존재 여부(간단판·폴백)
    from pathlib import Path as __Path
    def _has_local_index_files() -> bool:
        p = __Path.home() / ".maic" / "persist"
        return (p / "chunks.jsonl").exists() or (p / ".ready").exists()

    # (B) 타이틀+상태 배지 ------------------------------------------------------
    def _render_title_with_status():
        status = get_index_status()  # 'ready' | 'pending' | 'missing'
        if status == "ready":
            badge = '<span class="pill pill-green">🟢 두뇌 준비됨</span>'
        elif status == "pending":
            badge = '<span class="pill pill-amber">🟡 연결 대기</span>'
        else:
            badge = '<span class="pill pill-gray">🔴 준비 안 됨</span>'

        css = """
        <style>
        .topbar {display:flex; align-items:center; justify-content: space-between; gap:12px; margin-bottom: 6px;}
        .title {font-size: 1.75rem; font-weight: 700; line-height: 1.2; margin: 0;}
        .pill {display:inline-block; padding:6px 10px; border-radius:999px; font-weight:600; font-size:0.95rem;}
        .pill-green {background:#16a34a22; color:#16a34a; border:1px solid #16a34a55;}
        .pill-amber {background:#f59e0b22; color:#b45309; border:1px solid #f59e0b55;}
        .pill-gray {background:#6b728022; color:#374151; border:1px solid #6b728055;}
        </style>
        """
        html = f"""
        <div class="topbar">
          <div class="title">AI Teacher — MAIC</div>
          <div>{badge}</div>
        </div>
        """
        st.markdown(css + html, unsafe_allow_html=True)

    _render_title_with_status()

    # (C) 유틸: 품질스캐너 트리거 / 연결 / 복구 / 빌드 ----------------------------
    import time
    import importlib as _importlib
    from pathlib import Path as _Path

    def _trigger_quality_autoscan():
        """attach 성공 직후 품질 리포트 자동 갱신(없거나 오래되면). UI에 짧게 로그."""
        try:
            m = _importlib.import_module("src.rag.index_build")
            fn = getattr(m, "autorun_quality_scan_if_stale", None)
        except Exception:
            fn = None
        if callable(fn):
            try:
                res = fn()
                if res.get("ok") and not res.get("skipped"):
                    st.toast("품질 리포트 갱신 완료 ✅", icon="✅")
                elif res.get("skipped"):
                    # 최신이라 스킵
                    pass
                else:
                    st.toast("품질 리포트 갱신 실패", icon="⚠️")
            except Exception:
                st.toast("품질 리포트 갱신 실패", icon="⚠️")

    def _attach_with_status(label="두뇌 자동 연결 중…") -> bool:
        """로컬에 있는 인덱스로 세션 부착(복구 이후 호출 가정)."""
        try:
            with st.status(label, state="running") as s:
                bar = st.progress(0)
                bar.progress(25); time.sleep(0.08)
                ok = _auto_attach_or_restore_silently()
                st.session_state["brain_attached"] = bool(ok)
                bar.progress(100)
                if ok:
                    s.update(label="두뇌 자동 연결 완료 ✅", state="complete")
                    # ★ attach 성공 직후 품질스캐너 자동 실행
                    _trigger_quality_autoscan()
                else:
                    s.update(label="두뇌 자동 연결 실패 ❌", state="error")
                if ok and not st.session_state.get("_post_attach_rerun_done"):
                    st.session_state["_post_attach_rerun_done"] = True
                    st.rerun()
                else:
                    _render_title_with_status()
                return bool(ok)
        except Exception:
            ok = _auto_attach_or_restore_silently()
            st.session_state["brain_attached"] = bool(ok)
            if ok:
                _trigger_quality_autoscan()
            if ok and not st.session_state.get("_post_attach_rerun_done"):
                st.session_state["_post_attach_rerun_done"] = True
                st.rerun()
            elif ok:
                st.success("두뇌 자동 연결 완료 ✅"); _render_title_with_status()
            else:
                st.error("두뇌 자동 연결 실패")
            return bool(ok)

    def _restore_then_attach():
        """최신 백업 ZIP을 정본으로 복구 → attach."""
        try:
            _m = _importlib.import_module("src.rag.index_build")
        except Exception as e:
            st.error(f"복구 모듈 임포트 실패: {type(e).__name__}: {e}")
            return False

        _restore = getattr(_m, "restore_latest_backup_to_local", None)
        if not callable(_restore):
            st.error("복구 함수를 찾지 못했습니다. (restore_latest_backup_to_local)")
            return False

        with st.status("백업에서 로컬로 복구 중…", state="running") as s:
            try:
                r = _restore()
            except Exception as e:
                s.update(label="복구 실패 ❌", state="error")
                st.error(f"복구 실패: {type(e).__name__}: {e}")
                return False

            if not r or not r.get("ok"):
                s.update(label="복구 실패 ❌", state="error")
                st.error(f"복구 실패: {r.get('error') if r else 'unknown'}")
                return False

            s.update(label="복구 완료 ✅", state="complete")

        return _attach_with_status("복구 후 두뇌 연결 중…")

    def _build_then_backup_then_attach():
        """업데이트(다시 최적화) → 새 백업 업로드 → 그 ZIP으로 복구 → attach."""
        try:
            _m = _importlib.import_module("src.rag.index_build")
        except Exception as e:
            st.error(f"인덱스 빌더 모듈 임포트 실패: {type(e).__name__}: {e}")
            return False

        build_index_with_checkpoint = getattr(_m, "build_index_with_checkpoint", None)
        _make_and_upload_backup_zip_fn = getattr(_m, "_make_and_upload_backup_zip", None)
        _PERSIST_DIR_OBJ = getattr(_m, "PERSIST_DIR", _Path.home() / ".maic" / "persist")

        if not callable(build_index_with_checkpoint):
            st.error("인덱스 빌더 함수를 찾지 못했습니다. (build_index_with_checkpoint)")
            return False

        prog = st.progress(0); log = st.empty()
        def _pct(v: int, msg: str | None = None):
            prog.progress(max(0, min(int(v), 100)))
            if msg: log.info(str(msg))
        def _msg(s: str): log.write(f"• {s}")

        try:
            with st.status("변경 반영을 위한 다시 최적화 실행 중…", state="running") as s:
                res = build_index_with_checkpoint(
                    update_pct=_pct, update_msg=_msg,
                    gdrive_folder_id="", gcp_creds={},
                    persist_dir=str(_PERSIST_DIR_OBJ), remote_manifest={},
                )
                prog.progress(100)
                s.update(label="다시 최적화 완료 ✅", state="complete")
            st.json(res)
            try:
                if callable(_make_and_upload_backup_zip_fn):
                    _ = _make_and_upload_backup_zip_fn(None, None)
            except Exception:
                pass
            if _restore_then_attach():
                return True
            # 복구 실패 시 로컬 attach 폴백 + 품질스캐너 실행
            ok = _attach_with_status("두뇌 연결 중…")
            return bool(ok)
        except Exception as e:
            st.error(f"다시 최적화 실패: {type(e).__name__}: {e}")
            return False

    # (D) 0단계: 로컬 인덱스가 없으면 **무조건 선(先)복구** ---------------------------
    local_ok = _has_local_index_files()
    if not local_ok and not _index_ready():
        log = st.empty()
        log.info("boot: local_missing → try_restore_first")
        if _restore_then_attach():
            st.rerun()
        else:
            st.info("백업을 찾지 못했거나 손상되었습니다. ‘업데이트(다시 최적화)’를 실행해 주세요.")
            btn = st.button("업데이트 (다시 최적화 실행)", type="primary", key="boot_build_when_local_missing")
            if btn:
                if _build_then_backup_then_attach():
                    st.rerun()
                else:
                    st.stop()
        st.stop()

    # (E) 사전점검(내용 중심) → 변경 있으면 질문 -----------------------------------
    _mod = None
    _quick_precheck = None
    _PERSIST_DIR = _Path.home() / ".maic" / "persist"
    try:
        _mod = _importlib.import_module("src.rag.index_build")
        _quick_precheck = getattr(_mod, "quick_precheck", None)
        _PERSIST_DIR = getattr(_mod, "PERSIST_DIR", _PERSIST_DIR)
    except Exception:
        pass

    pre = {}
    if callable(_quick_precheck):
        try:
            pre = _quick_precheck("")
        except Exception as e:
            st.warning(f"사전점검 실패: {type(e).__name__}: {e}")
            pre = {}
    changed_flag = bool(pre.get("changed"))
    reasons_list = list(pre.get("reasons") or [])

    if changed_flag and not st.session_state.get("_admin_update_prompt_done"):
        with st.container(border=True):
            if "no_local_manifest" in reasons_list:
                st.info("📎 아직 인덱스가 없습니다. **최초 빌드가 필요**합니다.")
            else:
                st.info("📎 prepared 폴더에서 **새 자료(변경/신규)** 가 감지되었습니다.")
            c1, c2 = st.columns(2)
            with c1:
                do_update = st.button("업데이트 (다시 최적화 실행)", type="primary", key="admin_update_now")
            with c2:
                later = st.button("다음에 업데이트", key="admin_update_later")

        if do_update:
            st.session_state["_admin_update_prompt_done"] = True
            if _build_then_backup_then_attach():
                st.rerun()
            else:
                st.stop()

        if later:
            st.session_state["_admin_update_prompt_done"] = True
            # 합의: 기본은 최신 백업 ZIP으로 복구 후 연결
            if _restore_then_attach():
                st.rerun()
            else:
                st.info("백업을 찾지 못했거나 손상되었습니다. ‘업데이트(다시 최적화)’를 실행해 주세요.")
                st.stop()
        st.stop()

    # (F) 일반 플로우 ------------------------------------------------------------
    decision_log = st.empty()
    decision_log.info("auto-boot(admin): local_ok={} | changed={} reasons={}".format(local_ok, changed_flag, reasons_list))

    if _index_ready():
        _render_title_with_status()
    else:
        # 로컬은 있으니 바로 연결 시도(복구는 위에서 처리됨)
        if _attach_with_status():
            st.rerun()
        else:
            st.info("두뇌 연결 실패. 필요 시 ‘업데이트(다시 최적화)’를 실행해 주세요.")

    # (G) 관리자 화면 섹션 --------------------------------------------------------
    render_brain_prep_main()
    st.divider()
    render_tag_diagnostics()
    st.divider()
    render_simple_qa()

if __name__ == "__main__":
    main()
