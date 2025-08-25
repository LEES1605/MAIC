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

def _auto_attach_or_restore_silently() -> bool:
    """
    1) 로컬에서 부착 시도
    2) 실패하면: 드라이브 최신 backup_zip → 로컬로 복구 → 다시 부착
    3) 그래도 실패하면: 최소 옵션으로 build_index_with_checkpoint() 실행 → 다시 부착
    (에러는 모두 삼키고 False 반환)
    """
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
        return True
    st.session_state["_auto_restore_last"]["local_attach"] = False

    # 2) 드라이브에서 복구 시도
    try:
        import importlib
        mod = importlib.import_module("src.rag.index_build")
        restore_fn = getattr(mod, "restore_latest_backup_to_local", None)
        if callable(restore_fn):
            res = restore_fn()
            ok = bool(isinstance(res, dict) and res.get("ok"))
            st.session_state["_auto_restore_last"]["drive_restore"] = ok
            if ok and _has_local_index_files():
                if _attach_from_local():
                    st.session_state["_auto_restore_last"]["step"] = "restored_and_attached"
                    st.session_state["_auto_restore_last"]["final_attach"] = True
                    return True
    except Exception:
        st.session_state["_auto_restore_last"]["drive_restore"] = False

    # 3) 마지막 안전망: 인덱스 재생성(최소 옵션)
    try:
        import importlib
        if callable(build_index_with_checkpoint):
            from pathlib import Path
            try:
                mod2 = importlib.import_module("src.rag.index_build")
                persist_dir = getattr(mod2, "PERSIST_DIR", Path.home() / ".maic" / "persist")
            except Exception:
                persist_dir = Path.home() / ".maic" / "persist"

            try:
                build_index_with_checkpoint(
                    update_pct=lambda *_a, **_k: None,
                    update_msg=lambda *_a, **_k: None,
                    gdrive_folder_id="",
                    gcp_creds={},
                    persist_dir=str(persist_dir),
                    remote_manifest={},
                )
                st.session_state["_auto_restore_last"]["rebuild"] = True
            except TypeError:
                build_index_with_checkpoint()
                st.session_state["_auto_restore_last"]["rebuild"] = True
        else:
            st.session_state["_auto_restore_last"]["rebuild"] = False
    except Exception:
        st.session_state["_auto_restore_last"]["rebuild"] = False

    # 재부착 최종 시도
    if _attach_from_local():
        st.session_state["_auto_restore_last"]["step"] = "rebuilt_and_attached"
        st.session_state["_auto_restore_last"]["final_attach"] = True
        return True

        st.session_state["_auto_restore_last"]["final_attach"] = False
        return False
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

        # ── 가로 3열 배치 ──────────────────────────────────────────────────
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
        st.session_state["qa_modes_enabled"]  = selected
        st.session_state["show_mode_grammar"] = opt_grammar
        st.session_state["show_mode_structure"] = opt_structure
        st.session_state["show_mode_passage"] = opt_passage

        # 요약 표시
        st.caption("표시 중: " + (" · ".join(selected) if selected else "없음"))

# 호출
render_admin_settings()
# ===== [04B] END ======================================================

# ===== [05A] BRAIN PREP MAIN =======================================
def render_brain_prep_main():
    """
    준비/최적화 패널 (관리자 전용)
    - Drive 'prepared' 변화 감지(quick_precheck) → 결과 요약(+파일 목록)
    - 상태 배지(우선순위): no_prepared → delta → no_manifest → no_change
    - 인덱싱 중: 현재 파일명(아이콘) + 처리 n/총 m + ETA 표시
    - 완료 시 요약 배지 + 세션 기록(_optimize_last) + 복구 상세 표시
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
        cols = st.columns([1,1,1,1])
        cols[0].write(f"**인덱스 상태:** {status_badge}")
        cols[1].write(f"**신규자료:** {kind_badge}")
        cols[2].write(f"**prepared:** {prepared_cnt}")
        cols[3].write(f"**manifest:** {manifest_cnt}")

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
            seen = set(); current = {"name": None}; t0 = time.time()
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

        # ── 처리 분기(핵심 동작 동일, 복구 상세 출력 추가) ────────────────────
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
            # 업로드 → 복구
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
                # 복구 상세
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}): 
                        v = rr[k]
                        details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
                if details: st.caption("복구 상세: " + " · ".join(details))
            _record_result(True, time.time()-t0, "update", processed, total); _final_attach()

        if skip_and_restore:
            t0 = time.time()
            with st.status("최신 백업 ZIP 복구 중…", state="running") as s:
                rr = restore_fn()
                if not (rr and rr.get("ok")):
                    s.update(label="복구 실패 ❌", state="error"); _record_result(False, time.time()-t0, "restore"); st.error(f"복구 실패: {rr.get('error') if rr else 'unknown'}"); return
                s.update(label="복구 완료 ✅", state="complete")
                # 복구 상세
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}):
                        v = rr[k]
                        details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
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
                # 복구 상세
                details = []
                for k in ("zip_name","restored_count","files"):
                    if k in (rr or {}):
                        v = rr[k]
                        details.append(f"{k}:{v if not isinstance(v,list) else len(v)}")
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


# ===== [06] SIMPLE QA DEMO — 히스토리 인라인 + 답변 직표시 + 골든우선 + 규칙기반 합성기 + 피드백(라디오, 항상 유지) ==
from pathlib import Path
from typing import Any, Dict, List, Tuple
import time
import streamlit as st

# ── [06-A] 세션/캐시/상태 준비 ---------------------------------------------------
def _ensure_state():
    if "answer_cache" not in st.session_state:
        st.session_state["answer_cache"] = {}  # norm -> {"answer","refs","mode","ts","source"}
    if "last_submit_key" not in st.session_state:
        st.session_state["last_submit_key"] = None
    if "last_submit_ts" not in st.session_state:
        st.session_state["last_submit_ts"] = 0
    if "SHOW_TOP3_STICKY" not in st.session_state:
        st.session_state["SHOW_TOP3_STICKY"] = False
    if "allow_fallback" not in st.session_state:
        st.session_state["allow_fallback"] = True
    if "rating_values" not in st.session_state:
        st.session_state["rating_values"] = {}   # guard_key -> 1~5 (UI 유지용)
    if "active_result" not in st.session_state:
        # {"q","q_norm","mode_key","user","origin"}
        st.session_state["active_result"] = None

# ── [06-A’] 준비/토글 통일 판단 -------------------------------------------------
def _is_ready_unified() -> bool:
    try:
        return (get_index_status() == "ready")
    except Exception:
        return bool(st.session_state.get("rag_index"))

def _get_enabled_modes_unified() -> Dict[str, bool]:
    for key in ("enabled_modes", "admin_modes", "modes"):
        m = st.session_state.get(key)
        if isinstance(m, dict):
            return {
                "Grammar": bool(m.get("Grammar", False)),
                "Sentence": bool(m.get("Sentence", False)),
                "Passage": bool(m.get("Passage", False)),
            }
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
    if not st.session_state.get("is_admin", False):
        return {"Grammar": True, "Sentence": True, "Passage": True}
    return {"Grammar": False, "Sentence": False, "Passage": False}

# ── [06-B] 파일 I/O (히스토리 & 피드백 & 골든) ----------------------------------
def _app_dir() -> Path:
    p = Path.home() / ".maic"
    try: p.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return p

def _history_path() -> Path: return _app_dir() / "qa_history.jsonl"
def _feedback_path() -> Path: return _app_dir() / "feedback.jsonl"
def _golden_path() -> Path: return _app_dir() / "golden_explanations.jsonl"

def _append_jsonl(path: Path, obj: Dict[str, Any]):
    try:
        import json as _json
        with path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass

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

def _render_top3_badges():
    if not st.session_state.get("SHOW_TOP3_STICKY"): return
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

# ── [06-D] 캐시 + 저장 ----------------------------------------------------------
def _cache_put(q: str, answer: str, refs: List[Dict[str,str]], mode_label: str, source: str):
    _ensure_state()
    norm = _normalize_question(q)
    st.session_state["answer_cache"][norm] = {
        "answer": (answer or "").strip(),
        "refs": refs or [],
        "mode": mode_label,
        "source": source,
        "ts": int(time.time()),
    }

def _cache_get(norm: str) -> Dict[str, Any] | None:
    _ensure_state()
    return st.session_state["answer_cache"].get(norm)

def _render_cached_block(norm: str):
    data = _cache_get(norm)
    if not data:
        st.info("이 질문의 저장된 답변이 없어요. 아래 ‘다시 검색’으로 최신 답변을 받아보세요.")
        return
    # 골든 배지
    if data.get("source") == "golden":
        st.markdown("**⭐ 친구들이 이해 잘한 설명**")
    st.write(data.get("answer","—"))
    refs = data.get("refs") or []
    if refs:
        with st.expander("근거 자료(상위 2개)"):
            for i, r0 in enumerate(refs[:2], start=1):
                name = r0.get("doc_id") or r0.get("source") or f"ref{i}"
                url = r0.get("url") or r0.get("source_url") or ""
                st.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

# ── [06-D’] 피드백 저장/조회 -----------------------------------------------------
def _get_last_rating(q_norm: str, user: str, mode_key: str) -> int | None:
    import json as _json
    p = _feedback_path()
    if not p.exists(): return None
    last = None
    try:
        with p.open("r", encoding="utf-8") as f:
            for ln in f:
                try:
                    o = _json.loads(ln)
                    if o.get("q_norm")==q_norm and o.get("user")==user and o.get("mode")==mode_key:
                        r = int(o.get("rating",0))
                        if 1 <= r <= 5: last = r
                except Exception:
                    continue
    except Exception:
        pass
    return last

def _save_feedback(q: str, answer: str, rating: int, mode_key: str, source: str, user: str):
    q_norm = _normalize_question(q)
    ts = int(time.time())
    _append_jsonl(_feedback_path(), {
        "ts": ts, "user": user, "mode": mode_key, "q_norm": q_norm,
        "rating": int(rating), "source": source
    })
    if int(rating) >= 4:
        _append_jsonl(_golden_path(), {
            "ts": ts, "user": user, "mode": mode_key, "q_norm": q_norm,
            "question": q, "answer": answer, "source": source
        })

# ── [06-D’’] 일반 지식 Fallback(문구용) -----------------------------------------
def _fallback_general_answer(q: str, mode_key: str) -> str | None:
    return ("일반 지식 모드가 비활성화되어 있어요. "
            "관리자에서 일반 지식 LLM 연결을 켜면 교재에 없더라도 기본 설명을 제공할 수 있어요.")

# ── [06-D’’’] 한국어→영어 용어 확장 --------------------------------------------
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
        "조건문": "conditional|if-clause",
        "비교급": "comparative",
        "최상급": "superlative",
        "to부정사": "to-infinitive|infinitive",
        "부정사": "infinitive",
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

# ── [06-D⁴] 규칙기반 합성기(간략) -----------------------------------------------
def _extract_hit_text(h) -> str:
    try:
        if isinstance(h, dict):
            for k in ("text", "content", "page_content", "snippet", "chunk", "excerpt"):
                v = h.get(k)
                if v: return str(v)
        for attr in ("text", "content", "page_content", "snippet"):
            v = getattr(h, attr, None)
            if v: return str(v)
        n = getattr(h, "node", None)
        if n:
            for cand in ("get_content", "get_text"):
                fn = getattr(n, cand, None)
                if callable(fn):
                    v = fn()
                    if v: return str(v)
            for attr in ("text", "content", "page_content"):
                v = getattr(n, attr, None)
                if v: return str(v)
        s = str(h)
        if s and s != repr(h): return s
    except Exception:
        pass
    return ""

def _gather_context(hits: Any, max_chars: int = 1500) -> str:
    parts: List[str] = []
    if hits:
        for h in list(hits)[:4]:
            t = _extract_hit_text(h)
            if not t: continue
            t = t.replace("\n", " ").strip()
            if t:
                parts.append(t)
            if sum(len(x) for x in parts) > max_chars:
                break
    return " ".join(parts)[:max_chars].strip()

def _detect_topic(q: str, ctx: str) -> str:
    ql = (q or "").lower()
    cl = (ctx or "").lower()
    topics = {
        "relative_pronoun": ["관계대명사","relative pronoun","relative clause"," who "," which "," that "],
        "present_perfect": ["현재완료","present perfect"],
        "past_perfect": ["과거완료","대과거","past perfect"],
        "passive": ["수동태","passive"],
        "gerund": ["동명사","gerund"],
        "infinitive": ["to부정사","부정사","infinitive"],
        # (다른 항목 추가 예정)
    }
    for name, kws in topics.items():
        if any(k in ql for k in kws) or any(k in cl for k in kws):
            return name
    return "generic"

def _compose_answer_rule_based(topic: str) -> str:
    if topic == "relative_pronoun":
        return (
            "① **관계대명사(Relative Pronoun)** 는 앞에 있는 명사를 이어 받아 **형용사절(관계절)** 을 이끌며 "
            "사람·사물에 대해 **추가 정보를 덧붙이는** 역할을 합니다. 주로 **who/which/that** 을 쓰고, "
            "관계대명사가 절에서 **주어/목적어** 자리에 올 수 있어요.\n\n"
            "② **형식**: 선행사 + 관계대명사 + (주어) + 동사 …\n"
            "③ **예문**\n"
            "- The book **that** I bought is interesting. → 내가 산 그 책은 흥미롭다.\n"
            "- She is the girl **who** won the prize. → 상을 받은 그 소녀가 그녀야.\n"
            "④ **요령**: 선행사와 관계대명사의 **수 일치**와, **목적격**일 땐 구어에서 종종 생략된다는 점을 기억!"
        )
    if topic == "present_perfect":
        return (
            "① **현재완료(Present Perfect)** 는 과거에 한 일이 **현재와 연결된 결과/경험/계속** 을 나타낼 때 씁니다. "
            "**have/has + p.p.** 형태예요.\n\n"
            "② **주요 쓰임**\n"
            "- 경험(ever/never), 완료·결과(now), 계속(since/for)\n"
            "③ **예문**\n"
            "- I **have visited** Jeju **twice**.\n"
            "- She **has lived** here **for** three years.\n"
            "④ **요령**: **어제/ago** 같은 과거시점 표현과는 함께 쓰지 않아요."
        )
    if topic == "past_perfect":
        return (
            "① **과거완료(Past Perfect)** 는 과거의 한 시점보다 **더 이전**에 끝난 일을 말할 때 씁니다. "
            "**had + p.p.** 형태.\n\n"
            "② **예문**\n"
            "- By the time I arrived, the movie **had started**.\n"
            "- He **had finished** homework before dinner.\n"
            "③ **요령**: 과거 두 사건의 **선후관계**를 분명히!"
        )
    if topic == "passive":
        return (
            "① **수동태(Passive Voice)** : **be동사 + p.p.** 로 대상(피동)을 강조.\n"
            "② **예문**\n- The window **was broken** yesterday.\n- English **is spoken** worldwide.\n"
            "③ **요령**: 필요할 때만 **by + 행위자**."
        )
    if topic == "gerund":
        return (
            "① **동명사(Gerund)** : 동사에 **-ing** 를 붙여 **명사처럼** 사용.\n"
            "② **예문**\n- **Swimming** is fun.\n- I enjoy **reading**.\n"
            "③ **요령**: 전치사 뒤에는 동명사."
        )
    if topic == "infinitive":
        return (
            "① **부정사(Infinitive)** : **to + 동사원형** — 명/형/부 역할.\n"
            "② **예문**\n- I want **to learn** Spanish.\n- This book is easy **to read**.\n"
            "③ **요령**: 목적·의도 표현에 자주 사용."
        )
    return (
        "이 단원은 질문과 관련된 문법 항목을 설명합니다. 핵심 개념을 정리하면 다음과 같아요.\n"
        "① 정의/형식 ② 쓰임 ③ 예문 2개 ④ 한 줄 요령"
    )

def _ensure_nonempty_answer_rule_based(q: str, mode_key: str, hits: Any, raw: str) -> Tuple[str, str]:
    ctx = _gather_context(hits)
    topic = _detect_topic(q, ctx)
    ans = (_compose_answer_rule_based(topic) or "").strip()
    if ans:
        return ans, ("kb_rule" if hits else "rule_based")
    if st.session_state.get("allow_fallback", True):
        fb = (_fallback_general_answer(q, mode_key) or "").strip()
        if fb:
            return fb, "fallback_info"
    return "설명을 불러오는 중 문제가 있었어요. 질문을 조금 더 구체적으로 써 주세요.", "error"

# ── [06-D⁵] 골든 해설 우선 검색 -------------------------------------------------
_GOLDEN_MIN_SCORE = 0.52  # 필요시 0.45~0.6 사이로 조정

def _read_golden_rows(max_lines: int = 20000) -> List[Dict[str, Any]]:
    import json as _json
    p = _golden_path()
    if not p.exists(): return []
    rows: List[Dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for ln in f.readlines()[-max_lines:]:
                try:
                    o = _json.loads(ln)
                    # 기대 필드: ts, user, mode, q_norm, question, answer, source
                    if o.get("answer"):
                        rows.append(o)
                except Exception:
                    continue
    except Exception:
        return []
    rows.reverse()
    return rows

def _tokenize_for_sim(s: str) -> set[str]:
    import re as _re
    s = (s or "").lower()
    s = _re.sub(r"[^\w\sㄱ-ㅎ가-힣]", " ", s)
    toks = [t for t in s.split() if len(t) >= 2]
    # 간단 불용어
    stop = {"the","a","an","to","of","and","or","in","on","for","is","are","was","were","be","been","being"}
    return set(t for t in toks if t not in stop)

def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b: return 0.0
    inter = a & b
    union = a | b
    return float(len(inter)) / float(len(union))

def _search_golden_best(q: str, mode_key: str) -> Tuple[str, float] | None:
    q_norm = _normalize_question(q)
    rows = _read_golden_rows()
    # 1) 동일 정규질문 우선
    same = [r for r in rows if r.get("q_norm") == q_norm and r.get("mode") == mode_key and r.get("answer")]
    if same:
        # 최신 ts 우선
        same.sort(key=lambda r: int(r.get("ts") or 0), reverse=True)
        return (same[0]["answer"], 1.0)

    # 2) 유사도 기반(간단 자카드)
    q_expanded = _expand_query_for_rag(q, mode_key)
    qset = _tokenize_for_sim(q_expanded)
    best_ans, best_score = None, 0.0
    for r in rows:
        if r.get("mode") != mode_key: 
            continue
        cand_q = (r.get("question") or r.get("q_norm") or "")
        cset = _tokenize_for_sim(str(cand_q))
        s = _jaccard(qset, cset)
        if s > best_score:
            best_score = s
            best_ans = r.get("answer")
    if best_ans and best_score >= _GOLDEN_MIN_SCORE:
        return (best_ans, best_score)
    return None

# ✅ 항상 보이는 결과 패널 (컨테이너에 그릴 수도 있음)
def _render_active_result_panel(container=None):
    target = container or st
    ar = st.session_state.get("active_result")
    if not ar: 
        return
    norm = ar.get("q_norm"); mode_key = ar.get("mode_key"); user = ar.get("user") or "guest"
    data = _cache_get(norm)
    if not data:
        return

    # 골든 배지
    if (ar.get("origin") == "golden") or (data.get("source") == "golden"):
        target.markdown("**⭐ 친구들이 이해 잘한 설명**")

    target.write(data.get("answer","—"))
    refs = data.get("refs") or []
    if refs:
        with target.expander("근거 자료(상위 2개)"):
            for i, r0 in enumerate(refs[:2], start=1):
                name = r0.get("doc_id") or r0.get("source") or f"ref{i}"
                url = r0.get("url") or r0.get("source_url") or ""
                target.markdown(f"- {name}  " + (f"(<{url}>)" if url else ""))

    # 라디오(유지형) + 저장
    guard_key = f"{norm}|{mode_key}"
    saved = _get_last_rating(norm, user, mode_key)
    default_rating = saved if saved in (1,2,3,4,5) else 3
    rv_key = f"rating_value_{guard_key}"
    if rv_key not in st.session_state:
        st.session_state[rv_key] = default_rating

    emoji = {1:"😕 1", 2:"🙁 2", 3:"😐 3", 4:"🙂 4", 5:"😄 5"}
    sel = target.radio(
        "해설 만족도",
        options=[1,2,3,4,5],
        index=st.session_state[rv_key]-1,
        format_func=lambda n: emoji.get(n, str(n)),
        horizontal=True,
        key=f"rating_radio_{guard_key}"
    )
    st.session_state[rv_key] = sel

    c1, c2 = target.columns([1,4])
    with c1:
        if target.button("💾 저장", key=f"save_{guard_key}"):
            try:
                _save_feedback(ar["q"], data.get("answer",""), int(st.session_state[rv_key]), mode_key, data.get("source",""), user)
                try: st.toast("✅ 저장 완료!", icon="✅")
                except Exception: target.success("저장 완료!")
            except Exception as _e:
                target.warning(f"저장에 실패했어요: {_e}")
    with c2:
        target.caption(f"현재 저장된 값: {saved if saved else '—'} (라디오 선택 후 ‘저장’ 클릭)")

# ── [06-E] 메인 렌더 -----------------------------------------------------------
def render_simple_qa():
    _ensure_state()
    is_admin = st.session_state.get("is_admin", False)

    _render_top3_badges()
    st.markdown("### 💬 질문은 모든 천재들이 가장 많이 사용하는 공부 방법이다!")

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

    if submitted and not enabled.get(mode_key, False):
        st.warning("이 질문 유형은 지금 관리자에서 꺼져 있어요. 다른 유형을 선택해 주세요.")
        return

    # ▶ 제출 시: ① 골든 우선 → ② RAG → ③ 룰기반/폴백
    if submitted and (st.session_state.get("qa_q","").strip()):
        q = st.session_state["qa_q"].strip()
        guard_key = f"{_normalize_question(q)}|{mode_key}"
        now = time.time()
        if not (st.session_state.get("last_submit_key") == guard_key and (now - st.session_state.get("last_submit_ts",0) < 1.5)):
            st.session_state["last_submit_key"] = guard_key
            st.session_state["last_submit_ts"] = now

            user = _sanitize_user(st.session_state.get("student_name") if not is_admin else "admin")
            _append_history_file_only(q, user)

            area = st.container()
            with area:
                thinking = st.empty()
                thinking.info("🧠 답변 생각중… 베스트 해설과 교재를 차례로 확인하고 있어요.")

            final, origin = "", "unknown"
            refs: List[Dict[str, str]] = []

            # ① 골든 우선
            golden = _search_golden_best(q, mode_key)
            if golden:
                final, _score = golden
                origin = "golden"

            # ② RAG (골든이 없거나 불충분할 때만)
            if not final:
                index_ready = _is_ready_unified()
                if index_ready:
                    try:
                        q_expanded = _expand_query_for_rag(q, mode_key)
                        qe = st.session_state["rag_index"].as_query_engine(top_k=k)
                        r = qe.query(q_expanded)
                        raw = getattr(r, "response", "") or ""
                        hits = getattr(r, "source_nodes", None) or getattr(r, "hits", None)

                        def _is_nohit(raw_txt, hits_obj) -> bool:
                            txt = (raw_txt or "").strip().lower()
                            bad_phrases = ["관련 결과를 찾지 못", "no relevant", "no result", "not find"]
                            cond_txt = (not txt) or any(p in txt for p in bad_phrases)
                            cond_hits = (not hits_obj) or (hasattr(hits_obj, "__len__") and len(hits_obj) == 0)
                            return cond_txt or cond_hits

                        if _is_nohit(raw, hits):
                            qe_wide = st.session_state["rag_index"].as_query_engine(top_k=max(10, int(k) if isinstance(k,int) else 5))
                            r2 = qe_wide.query(q_expanded)
                            raw2 = getattr(r2, "response", "") or ""
                            hits2 = getattr(r2, "source_nodes", None) or getattr(r2, "hits", None)
                            if not _is_nohit(raw2, hits2):
                                raw, hits = raw2, hits2

                        final, origin = _ensure_nonempty_answer_rule_based(q, mode_key, hits, raw)

                        try:
                            if hits:
                                for h in hits[:2]:
                                    meta = None
                                    if hasattr(h, "metadata") and isinstance(getattr(h, "metadata"), dict):
                                        meta = h.metadata
                                    elif hasattr(h, "node") and hasattr(h.node, "metadata") and isinstance(h.node.metadata, dict):
                                        meta = h.node.metadata
                                    meta = meta or {}
                                    refs.append({
                                        "doc_id": meta.get("doc_id") or meta.get("file_name") or meta.get("filename", ""),
                                        "url": meta.get("source") or meta.get("url", ""),
                                    })
                        except Exception:
                            refs = []

                    except Exception as e:
                        with area:
                            thinking.empty()
                            st.error(f"검색 실패: {type(e).__name__}: {e}")
                            final, origin = "설명을 불러오는 중 문제가 있었어요. 다시 시도해 주세요.", "error"
                else:
                    # ③ 룰기반/폴백(두뇌 미준비)
                    final, origin = _ensure_nonempty_answer_rule_based(q, mode_key, hits=None, raw="")

            # 캐시 + 활성 결과 저장
            _cache_put(q, final, refs, {"Grammar":"문법설명(Grammar)","Sentence":"문장분석(Sentence)","Passage":"지문분석(Passage)"}[mode_key], origin or "unknown")
            st.session_state["active_result"] = {
                "q": q, "q_norm": _normalize_question(q),
                "mode_key": mode_key, "user": user, "origin": origin or "unknown"
            }

            # 제출 직후, 같은 컨테이너에 즉시 결과 패널 렌더
            with area:
                thinking.empty()
                _render_active_result_panel(container=area)

    # 제출 여부와 무관하게, 항상 마지막 결과 패널을 렌더(라디오 클릭 재실행 대비)
    _render_active_result_panel()

    # 📒 나의 질문 히스토리 — 인라인 펼치기
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
        render_simple_qa()
    except Exception as e:
        st.error(f"질문 패널 렌더 중 오류: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
# ===== [07] END ===============================================================
