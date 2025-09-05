# ======================== [00] orchestrator helpers — START ========================
from __future__ import annotations

import importlib
import importlib.util
import traceback
from pathlib import Path
from typing import Any, Dict, Optional


def _add_error(e: BaseException) -> None:
    """에러를 세션에 누적(최대 200개)"""
    try:
        import streamlit as st

        lst = st.session_state.setdefault("_orchestrator_errors", [])
        lst.append("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        if len(lst) > 200:
            del lst[:-200]
    except Exception:
        pass


def _errors_text() -> str:
    """누적 에러를 텍스트로 반환(비어 있으면 대시)"""
    try:
        import streamlit as st

        lst = st.session_state.get("_orchestrator_errors") or []
        return "\n\n".join(lst) if lst else "—"
    except Exception:
        return "—"


def _ready_mark(persist_dir: Path) -> None:
    """인덱싱/복원 완료 표시 파일(.ready) 생성"""
    try:
        persist_dir.mkdir(parents=True, exist_ok=True)
        (persist_dir / ".ready").write_text("ready", encoding="utf-8")
    except Exception as e:
        _add_error(e)


# ========================= [00] orchestrator helpers — END =========================

# ========================== [01] lazy imports — START =============================
def _lazy_imports() -> Dict[str, Any]:
    """
    의존 모듈을 '가능한 이름들'로 느슨하게 임포트해 dict로 반환.
    PERSIST_DIR 우선순위:
      (0) Streamlit 세션 _PERSIST_DIR
      (1) src.rag.index_build.PERSIST_DIR
      (2) src.config.PERSIST_DIR
      (3) ~/.maic/persist
    """
    from pathlib import Path as _P

    def _imp(name: str):
        try:
            return importlib.import_module(name)
        except Exception:
            return None

    deps: Dict[str, Any] = {}

    # 0) 세션에 공유된 경로 우선
    try:
        import streamlit as st

        _ss_p = st.session_state.get("_PERSIST_DIR")
        if _ss_p:
            deps["PERSIST_DIR"] = _P(str(_ss_p))
    except Exception:
        pass

    # 1) index_build
    mod_idx = _imp("src.rag.index_build")
    if "PERSIST_DIR" not in deps and mod_idx is not None:
        try:
            if hasattr(mod_idx, "PERSIST_DIR"):
                deps["PERSIST_DIR"] = mod_idx.PERSIST_DIR  # hasattr 체크 후 직접 접근
        except Exception:
            pass

    # 2) config
    if "PERSIST_DIR" not in deps:
        mod_cfg = _imp("src.config")
        if mod_cfg is not None:
            try:
                if hasattr(mod_cfg, "PERSIST_DIR"):
                    deps["PERSIST_DIR"] = _P(mod_cfg.PERSIST_DIR)  # ← B009 해결: getattr → 직접 접근
            except Exception:
                pass

    # 3) 최종 폴백
    if "PERSIST_DIR" not in deps or not deps["PERSIST_DIR"]:
        deps["PERSIST_DIR"] = _P.home() / ".maic" / "persist"

    # --- GitHub release / manifest ---
    mod_rel = _imp("src.backup.github_release")
    if mod_rel is not None:
        try:
            deps["get_latest_release"] = getattr(mod_rel, "get_latest_release", None)
        except Exception:
            deps["get_latest_release"] = None
        try:
            deps["fetch_manifest_from_release"] = getattr(mod_rel, "fetch_manifest_from_release", None)
        except Exception:
            deps["fetch_manifest_from_release"] = None
        try:
            deps["restore_latest"] = getattr(mod_rel, "restore_latest", None)
        except Exception:
            deps["restore_latest"] = None

    # --- Google Drive / Index 유틸 ---
    if mod_idx is not None:
        try:
            deps.setdefault("_drive_client", getattr(mod_idx, "_drive_client", None))
        except Exception:
            pass
        try:
            deps.setdefault("_find_folder_id", getattr(mod_idx, "_find_folder_id", None))
        except Exception:
            pass
        try:
            deps.setdefault("scan_drive_listing", getattr(mod_idx, "scan_drive_listing", None))
        except Exception:
            pass
        try:
            deps.setdefault("diff_with_manifest", getattr(mod_idx, "diff_with_manifest", None))
        except Exception:
            pass
        try:
            deps.setdefault("build_index_with_checkpoint", getattr(mod_idx, "build_index_with_checkpoint", None))
        except Exception:
            pass

    return deps
# =========================== [01] lazy imports — END ==============================
# ======================= [01b] autoflow_boot_check — START ========================
def autoflow_boot_check(*, interactive: bool = False) -> None:
    """
    앱 부팅 시 1회 호출되는 오케스트레이션 진입점.
    - interactive=True  : 관리자 모드(대화형) — 패널 토글을 자동으로 열도록 힌트만 둠
    - interactive=False : 학생/일반 모드  — 아무 것도 강제하지 않음(무해)
    - 예외는 내부에서 `_add_error`로 흡수(앱 크래시 방지)
    """
    try:
        import streamlit as st  # 지역 import: Streamlit 미설치 환경 대응
        ss = st.session_state if hasattr(st, "session_state") else {}
        # 1) persist dir 공유(있다면 app.py가 이미 넣었음)
        if isinstance(ss, dict) and "_PERSIST_DIR" in ss:
            pass  # no-op

        # 2) 관리자 모드 힌트: 패널을 '열도록' 플래그만 설정(UX만; 강제 렌더 X)
        if interactive and isinstance(ss, dict):
            # 최초 1회만 열리도록(사용자가 닫으면 존중)
            ss.setdefault("_admin_diag_open", True)

        # 3) 추가적으로 나중에 확장 가능(예: 자동 상태 점검/가벼운 사전 체크)
        #    현재는 무해한 no-op로 유지해 안전성 확보
    except BaseException as e:  # broad: 여기서 예외로 앱이 죽으면 안 됨
        _add_error(e)
# ======================== [01b] autoflow_boot_check — END =========================


# ====================== [02] Index Orchestrator Panel — START ======================
def render_index_orchestrator_panel() -> None:
    """
    (미니멀 버전)
    - 여기서는 상태/경로/가이드만 노출 + '관리자 인덱싱 패널([15]) 열기' 버튼만 제공.
    - 실제 강제 인덱싱(HQ)+백업/파일 미리보기는 app.py의 [15]/[16]에서 수행.
    """
    # ── 지역 import (필요한 것만; ruff F401 방지) ───────────────────────────
    from pathlib import Path

    try:
        import streamlit as st
    except Exception:
        return

    # 내부 헬퍼
    def _persist_dir() -> Path:
        try:
            from src.rag.index_build import PERSIST_DIR as IDX
            return Path(str(IDX)).expanduser()
        except Exception:
            pass
        try:
            from src.config import PERSIST_DIR as CFG
            return Path(str(CFG)).expanduser()
        except Exception:
            pass
        return Path.home() / ".maic" / "persist"

    def _is_ready(persist: Path) -> bool:
        try:
            ready = (persist / ".ready").exists()
            cj = persist / "chunks.jsonl"
            return ready and cj.exists() and cj.stat().st_size > 0
        except Exception:
            return False

    # 본문
    st.markdown("### 🧭 인덱스 오케스트레이터")
    persist = _persist_dir()
    ok = _is_ready(persist)

    c1, c2, c3 = st.columns([2, 3, 2])
    with c1:
        st.write("**Persist Dir**")
        st.code(str(persist), language="text")
        st.write("**상태**")
        st.success("READY") if ok else st.warning("MISSING")

    with c2:
        st.info(
            "강제 인덱싱(HQ, 느림)+백업과 인덱싱 파일 미리보기는 **관리자 인덱싱 패널([15])**에서 합니다.\n"
            "- 관리자 모드 진입 → 하단의 *인덱싱(관리자)* 섹션으로 이동"
        )

    with c3:
        st.write(" ")
        if st.button("⚡ 인덱싱 패널([15]) 열기", type="primary", help="관리자 인덱싱 패널로 바로 이동"):
            try:
                st.session_state["_admin_diag_open"] = True
                st.session_state["_force_focus_admin_index"] = True  # [15] 패널 쪽에서 감지
                st.rerun()
            except Exception:
                pass

    with st.expander("도움말 / 트러블슈팅", expanded=False):
        st.markdown(
            "- 인덱싱 후에도 *신규파일 감지*가 뜨면, prepared **전체 목록**이 `seen` 처리되지 않은 것입니다.\n"
            "  - app.py의 [15] 패널은 인덱싱 직후 드라이버를 확인하고, 전체 목록을 조회해 `mark_prepared_consumed()`에 전달합니다.\n"
            "- `chunks.jsonl`이 없거나 0B이면 READY가 되지 않습니다."
        )
# ======================= [02] Index Orchestrator Panel — END =======================

# ================== [03] render_index_orchestrator_panel — START ==================
# (삭제됨) — 기능은 [02] Index Orchestrator Panel에 통합되었습니다.
# 기존 중복 정의로 인해 F811이 발생했으므로 본 구획의 함수 정의는 제거합니다.
# =================== [03] render_index_orchestrator_panel — END ===================
