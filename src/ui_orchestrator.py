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


# ======================== [02] autoflow_boot_check — START =========================
def _has_local_index(persist_dir: Path) -> bool:
    return (persist_dir / "chunks.jsonl").exists() and (persist_dir / ".ready").exists()


def autoflow_boot_check(*, interactive: bool) -> None:  # noqa: ARG001 (인터페이스 유지)
    """
    앱 부팅 시 단 한 번 실행되는 오토 플로우(FAST BOOT):
      - 로컬 인덱스가 있으면 **즉시 READY 로 전환** (네트워크 호출 없음)
      - 로컬 인덱스가 없을 때만 Releases 에서 복원 시도
      - 변경 감지/재인덱싱/동기화는 **관리자 버튼(업데이트 점검)** 으로 수동 실행
    """
    import streamlit as st

    ss = st.session_state
    if ss.get("_boot_checked") is True:
        return

    # 진행 단계 기록(SSOT)
    def PH(code: str, msg: str = "") -> None:
        try:
            ss["_boot_phase"] = code
            if msg:
                ss["_boot_msg"] = msg
        except Exception:
            pass

    deps = _lazy_imports()
    PERSIST_DIR = deps.get("PERSIST_DIR")
    restore_latest = deps.get("restore_latest")

    p = PERSIST_DIR if isinstance(PERSIST_DIR, Path) else Path(str(PERSIST_DIR))

    # 0) FAST PATH — 로컬이 이미 있으면 바로 READY
    PH("LOCAL_CHECK", "로컬 인덱스 확인 중…")
    if _has_local_index(p):
        PH("READY_MARK", "준비 완료 표식 생성…")
        _ready_mark(p)
        ss["_boot_checked"] = True
        PH("READY", "준비완료")
        return

    # 1) 로컬이 없을 때만 Releases 복원 시도
    PH("RESTORE_FROM_RELEASE", "백업에서 로컬 복원 중…")
    if callable(restore_latest):
        with st.spinner("초기화: 백업에서 로컬 복원 중…"):
            ok = False
            try:
                ok = bool(restore_latest(dest_dir=p))
            except Exception as e:
                _add_error(e)
        if ok:
            PH("READY_MARK", "준비 완료 표식 생성…")
            _ready_mark(p)
            ss["_boot_checked"] = True
            PH("READY", "준비완료")
            if hasattr(st, "toast"):
                st.toast("✅ 백업에서 로컬 인덱스를 복원했습니다.", icon="✅")
            else:
                st.success("✅ 백업에서 로컬 인덱스를 복원했습니다.")
            st.rerun()
        else:
            ss["_boot_checked"] = True
            PH("ERROR", "복원 실패")
    else:
        _add_error(RuntimeError("restore_latest 가 없습니다."))
        ss["_boot_checked"] = True
        PH("ERROR", "복원 함수를 찾을 수 없습니다.")

# ========================= [02] autoflow_boot_check — END ==========================
# ===== [03] render_index_orchestrator_panel — START =====
def render_index_orchestrator_panel() -> None:
    """
    관리자 진단/지식관리 패널 렌더링.
    - 재인덱싱 버튼을 '항상' 노출(필요 시 비활성화/안내)
    - READY(.ready + chunks.jsonl) 이전에는 '완료' 스텝을 잠금(🔒)
    - GitHub 최신 릴리스 표기(get_latest_release)와 복구(restore_latest) 연계
    """
    # --- Lazy imports & local helpers (안전 가드 포함) --------------------------
    try:
        import streamlit as st  # type: ignore[import-not-found]
    except Exception:
        return

    from pathlib import Path
    import importlib
    from typing import Any, Optional
    import time

    def _persist_dir() -> Path:
        """PERSIST_DIR 탐색: rag.index_build → config → ~/.maic/persist"""
        try:
            from src.rag.index_build import PERSIST_DIR as IDX  # type: ignore[attr-defined]
            return Path(str(IDX)).expanduser()
        except Exception:
            pass
        try:
            from src.config import PERSIST_DIR as CFG  # type: ignore[attr-defined]
            return Path(str(CFG)).expanduser()
        except Exception:
            pass
        return Path.home() / ".maic" / "persist"

    def _local_ready(p: Path) -> bool:
        """SSOT: .ready & chunks.jsonl(>0B) 동시 존재해야 READY."""
        try:
            cj = p / "chunks.jsonl"
            return (p / ".ready").exists() and cj.exists() and cj.stat().st_size > 0
        except Exception:
            return False

    def _try_import(modname: str, names: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            m = importlib.import_module(modname)
            for n in names:
                out[n] = getattr(m, n, None)
        except Exception:
            for n in names:
                out[n] = None
        return out

    PERSIST = _persist_dir()
    ready = _local_ready(PERSIST)

    # --- Header / Stepper ------------------------------------------------------
    st.subheader("🛠 진단 도구")
    steps = ["프리검사", "백업훑", "변경검지", "다운로드", "복구/해체", "연결성", "완료"]
    # 현재 선택 탭 상태 보존
    st.session_state.setdefault("_orchestrator_step", steps[0])
    sel = st.segmented_control("단계", steps, key="_orchestrator_step")  # Streamlit >=1.36
    # ✅ READY 전에는 '완료' 스텝 잠금
    if not ready and sel == "완료":
        st.warning("아직 인덱스가 준비되지 않았습니다. 먼저 복구/연결을 완료해 주세요. (🔒 잠금)")
        # 강제로 첫 단계로 되돌림(사용자 혼선 방지)
        st.session_state["_orchestrator_step"] = steps[0]
        sel = steps[0]

    # --- 상태 요약 카드 ---------------------------------------------------------
    with st.container(border=True):
        st.markdown("#### 상태 요약")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.caption("로컬")
            st.write("🧠 " + ("**READY** (.ready+chunks)" if ready else "**MISSING**"))
            st.code(str(PERSIST), language="text")
        with col2:
            st.caption("GitHub")
            gh = _try_import("src.backup.github_release", ["get_latest_release", "restore_latest"])
            get_latest = gh.get("get_latest_release")
            latest_tag = "—"
            try:
                if callable(get_latest):
                    rel = get_latest(None)
                    if isinstance(rel, dict):
                        latest_tag = str(rel.get("tag_name") or rel.get("name") or "없음")
            except Exception:
                latest_tag = "표시 실패"
            st.write(f"릴리스: **{latest_tag}**")
        with col3:
            st.caption("Drive")
            st.write("관리자 버튼으로만 네트워크 점검을 수행합니다.")

    # --- 액션 버튼 행 -----------------------------------------------------------
    st.markdown("#### 작업")
    b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
    with b1:
        do_quick = st.button("빠른 점검", help="버튼 클릭 시에만 네트워크를 확인합니다.")
    with b2:
        do_reset = st.button("결과 초기화", help="진단 결과/오류 로그 뷰를 초기화합니다.")
    with b3:
        do_update = st.button("업데이트 점검", help="GitHub 최신 릴리스에서 복구를 시도합니다.")
    with b4:
        # ✅ 재인덱싱 버튼 '항상 표기'
        do_reindex = st.button("재인덱싱", help="로컬 인덱스를 새로 구축합니다(항상 표시).")

    # --- 결과/로그 영역 ---------------------------------------------------------
    log_key = "_orchestrator_log"
    if do_reset:
        st.session_state[log_key] = []
    st.session_state.setdefault(log_key, [])
    def _log(msg: str) -> None:
        st.session_state[log_key].append(f"{time.strftime('%H:%M:%S')}  {msg}")

    # --- 동작: 빠른 점검 --------------------------------------------------------
    if do_quick:
        _log("로컬 상태 확인…")
        st.toast("로컬 상태 확인", icon="🔎")
        _log(f"local: {'READY' if ready else 'MISSING'}")

        gh = _try_import("src.backup.github_release", ["get_latest_release"])
        get_latest = gh.get("get_latest_release")
        try:
            rel = get_latest() if callable(get_latest) else None  # type: ignore[misc]
            if isinstance(rel, dict):
                tag = rel.get("tag_name") or rel.get("name") or "없음"
                _log(f"github: 최신 릴리스 = {tag}")
                st.success(f"GitHub 최신 릴리스: {tag}")
            else:
                _log("github: 최신 릴리스 없음 또는 조회 실패")
                st.info("GitHub 최신 릴리스: 없음/조회 실패")
        except Exception as e:
            _log(f"github: 조회 실패 — {e}")
            st.warning("GitHub 조회 실패(토큰/권한/네트워크)")

    # --- 동작: 업데이트 점검(릴리스 복구) ---------------------------------------
    if do_update:
        gh = _try_import("src.backup.github_release", ["restore_latest"])
        restore_latest = gh.get("restore_latest")
        if callable(restore_latest):
            with st.spinner("GitHub 릴리스에서 복구 중…"):
                ok = False
                try:
                    ok = bool(restore_latest(PERSIST))  # .zip/.tar.gz/.gz 자동 처리(이전 패치)
                except Exception as e:
                    _log(f"restore_latest 예외: {e}")
                if ok:
                    # 복구 후 SSOT에 따라 READY 여부 재평가
                    r2 = _local_ready(PERSIST)
                    _log(f"restore 결과: {'READY' if r2 else 'MISSING'}")
                    if r2:
                        st.success("복구 완료(READY).")
                    else:
                        st.warning("복구는 성공했지만 READY 조건(.ready+chunks)이 충족되지 않았습니다.")
                else:
                    st.error("복구 실패. 오류 로그를 확인해 주세요.")
        else:
            st.info("restore_latest 함수를 찾지 못했습니다. 모듈 버전을 확인해 주세요.")

    # --- 동작: 재인덱싱(항상 노출) ---------------------------------------------
    if do_reindex:
        idx = _try_import("src.rag.index_build", [
            "rebuild_index", "build_index", "rebuild", "index_all", "build_all"
        ])
        fn = next((idx[n] for n in ("rebuild_index","build_index","rebuild","index_all","build_all") if callable(idx.get(n))), None)
        if callable(fn):
            with st.spinner("재인덱싱(전체) 실행 중…"):
                ok = False
                try:
                    # 인자가 없는 구현과 (dest_dir) 1-인자 구현을 모두 수용
                    try:
                        ok = bool(fn(PERSIST))  # type: ignore[misc]
                    except TypeError:
                        ok = bool(fn())        # type: ignore[misc]
                except Exception as e:
                    _log(f"reindex 예외: {e}")
                if ok:
                    # 인덱싱 완료 후 .ready 보정(SSOT 충족 시)
                    r2 = _local_ready(PERSIST)
                    _log(f"reindex 결과: {'READY' if r2 else 'MISSING'}")
                    if r2:
                        st.success("재인덱싱 완료(READY).")
                    else:
                        st.warning("재인덱싱 후 READY 조건(.ready+chunks)이 충족되지 않았습니다.")
                else:
                    st.error("재인덱싱 실패. 오류 로그를 확인해 주세요.")
        else:
            # 구현이 없더라도 버튼은 '항상' 보인다 — 사용자 혼선 방지용 메시지
            st.info("현재 버전에서 재인덱싱 함수가 정의되지 않았습니다. "
                    "업데이트 점검(릴리스 복구) 또는 수동 인덱싱 스크립트를 사용해 주세요.")

    # --- 로그 뷰 ---------------------------------------------------------------
    st.markdown("#### 오류 로그")
    st.text_area("최근 로그", value="\n".join(st.session_state[log_key][-200:]), height=160)
# ===== [03] render_index_orchestrator_panel — END =====
