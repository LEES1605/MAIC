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
# ================== [03] render_index_orchestrator_panel — START ==================
def render_index_orchestrator_panel() -> None:
    """
    관리자 진단/지식관리 패널.
    요구 플로우 구현 + 보강:
      - 앱 실행 시 prepared 신규 검사 → status: UPDATED / NO_UPDATES / CHECK_FAILED
      - UPDATED: (A) 재인덱싱→릴리스 백업→READY, (B) 기존 릴리스 복구→READY 중 선택
      - NO_UPDATES: READY 아니면 자동 복구(1회)
      - CHECK_FAILED: 자동복구 건너뛰고 안내/수동 버튼만 제공
      - 강제 인덱싱(+백업) 버튼 제공
      - 성공 시 스텝 이동은 “예약+rerun” 방식(위젯 set 예외 방지)
    """
    import time
    from pathlib import Path
    import importlib
    from typing import Any, Dict, List
    import shutil
    import os

    import streamlit as st  # 런타임 임포트

    # ---------- helpers ----------
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

    def _request_step(step: str) -> None:
        st.session_state["_orchestrator_next_step"] = step
        try:
            st.rerun()
        except Exception:
            try:
                st.experimental_rerun()
            except Exception:
                pass

    def _apply_pending_step_before_widgets(steps: list[str]) -> None:
        k = "_orchestrator_next_step"
        if k in st.session_state:
            val = st.session_state.pop(k, None)
            if val in steps:
                st.session_state["_orchestrator_step"] = val

    # --- 세션/스냅샷 API 동적 로드 ---
    def _load_session_api():
        ensure_keys_fn = None
        persist_dir_fn = None
        snapshot_index_fn = None
        sync_badge_from_fs_fn = None
        try:
            mod = importlib.import_module("src.state.session")
            ensure_keys_fn = getattr(mod, "ensure_keys", None)
            persist_dir_fn = getattr(mod, "persist_dir", None)
            snapshot_index_fn = getattr(mod, "snapshot_index", None)
            sync_badge_from_fs_fn = getattr(mod, "sync_badge_from_fs", None)
        except Exception:
            pass

        def _persist_dir_fallback() -> Path:
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

        def _snapshot_index_fallback(p: Path | None = None) -> dict[str, Any]:
            base = p or _persist_dir_fallback()
            cj = base / "chunks.jsonl"
            try:
                size = cj.stat().st_size if cj.exists() else 0
            except Exception:
                size = 0
            return {
                "persist_dir": str(base),
                "ready_flag": (base / ".ready").exists(),
                "chunks_exists": cj.exists(),
                "chunks_size": size,
                "local_ok": (base / ".ready").exists() and cj.exists() and size > 0,
            }

        def _sync_badge_from_fs_fallback() -> dict[str, Any]:
            return _snapshot_index_fallback()

        return (
            ensure_keys_fn or (lambda: None),
            persist_dir_fn or _persist_dir_fallback,
            snapshot_index_fn or _snapshot_index_fallback,
            sync_badge_from_fs_fn or _sync_badge_from_fs_fallback,
        )

    ensure_keys, _persist_dir, snapshot_index, sync_badge_from_fs = _load_session_api()
    ensure_keys()
    PERSIST = _persist_dir()

    steps = ["프리검사", "백업훑", "변경검지", "다운로드", "복구/해체", "연결성", "완료"]
    st.session_state.setdefault("_orchestrator_step", steps[0])
    _apply_pending_step_before_widgets(steps)

    # 현 스냅샷
    snap = snapshot_index(PERSIST)
    ready = bool(snap.get("local_ok"))

    # --- header ---
    st.subheader("🛠 진단 도구")

    # === 신규 파일 검사(앱 진입 시) ===
    chk = _try_import("src.drive.prepared", ["check_prepared_updates", "mark_prepared_consumed"])
    check_fn = chk.get("check_prepared_updates")
    mark_fn = chk.get("mark_prepared_consumed")
    updates: Any = None
    if callable(check_fn):
        try:
            updates = check_fn(PERSIST)
        except Exception:
            updates = {"status": "CHECK_FAILED", "error": "exception in check_prepared_updates"}

    status = (updates or {}).get("status", "CHECK_FAILED")

    # --- 상태 요약 ---
    with st.container(border=True):
        st.markdown("#### 상태 요약")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.write("로컬: " + ("**READY**" if ready else "**MISSING**"))
            st.code(str(PERSIST), language="text")
        with c2:
            st.write(f"prepared: **{status}**")
        with c3:
            gh = _try_import("src.backup.github_release", ["get_latest_release"])
            latest_tag = "—"
            get_latest = gh.get("get_latest_release")
            try:
                if callable(get_latest):
                    rel = get_latest(None)
                    if isinstance(rel, dict):
                        latest_tag = str(rel.get("tag_name") or rel.get("name") or "없음")
            except Exception:
                latest_tag = "표시 실패"
            st.write(f"GitHub 최신 릴리스: **{latest_tag}**")

    # === 분기 처리 ===
    log_key = "_orchestrator_log"
    st.session_state.setdefault(log_key, [])

    def _log(msg: str) -> None:
        st.session_state[log_key].append(f"{time.strftime('%H:%M:%S')}  {msg}")

    # UPDATED → 사용자 선택
    if status == "UPDATED":
        u: Dict[str, Any] = updates if isinstance(updates, dict) else {}
        with st.container(border=True):
            st.markdown("### ⚡ prepared 폴더에 **신규 파일**이 감지되었습니다.")
            cnt = int(u.get("count", 0))
            cache_path = str(u.get("cache_path", ""))
            st.caption(f"파일 수: {cnt}  |  캐시: {cache_path}")
            colA, colB = st.columns([1, 1])
            with colA:
                do_apply_new = st.button("신규 반영(재인덱싱 + 백업 → READY)", key="btn_apply_new")
            with colB:
                do_restore_old = st.button("기존 릴리스로 복구(→ READY)", key="btn_restore_old")

            if do_apply_new:
                svc = _try_import("src.services.index", ["reindex"])
                reindex_fn = svc.get("reindex")
                ok1 = False
                with st.spinner("재인덱싱 중…"):
                    try:
                        ok1 = bool(reindex_fn(PERSIST)) if callable(reindex_fn) else False
                    except TypeError:
                        ok1 = bool(reindex_fn()) if callable(reindex_fn) else False
                    except Exception as e:
                        _log(f"reindex 예외: {e}")
                        ok1 = False
                ok2 = False
                if ok1:
                    gh = _try_import("src.backup.github_release", ["publish_backup"])
                    pub = gh.get("publish_backup")
                    if callable(pub):
                        with st.spinner("GitHub 릴리스(백업) 발행 중…"):
                            ok2 = bool(pub(PERSIST))
                        if not ok2:
                            st.info("백업 발행 실패 또는 생략됨(로컬 READY는 유지됩니다).")
                snap = sync_badge_from_fs()
                if callable(mark_fn):
                    try:
                        files: List[Dict[str, Any]] = u.get("files", [])
                        mark_fn(PERSIST, files)
                    except Exception:
                        pass
                if snap["local_ok"]:
                    st.success("신규 반영 완료(READY).")
                    _request_step("완료")
                else:
                    st.warning("신규 반영 후 READY 조건이 미충족입니다. 로그를 확인하세요.")

            if do_restore_old:
                gh2 = _try_import("src.backup.github_release", ["restore_latest"])
                restore_latest = gh2.get("restore_latest")
                ok = False
                if callable(restore_latest):
                    with st.spinner("기존 릴리스로 복구 중…"):
                        try:
                            ok = bool(restore_latest(PERSIST))
                        except Exception as e:
                            _log(f"restore_latest 예외: {e}")
                            ok = False
                snap = sync_badge_from_fs()
                if callable(mark_fn):
                    try:
                        files: List[Dict[str, Any]] = u.get("files", [])
                        mark_fn(PERSIST, files)
                    except Exception:
                        pass
                if ok and snap["local_ok"]:
                    st.success("복구 완료(READY).")
                    _request_step("완료")
                else:
                    st.warning("복구 실패 또는 READY 미충족. 로그를 확인하세요.")

    # NO_UPDATES → READY 아니면 자동 복구 1회
    auto_key = "_auto_restore_done"
    if status == "NO_UPDATES" and (not ready):
        if not st.session_state.get(auto_key, False):
            gh3 = _try_import("src.backup.github_release", ["restore_latest"])
            restore_latest = gh3.get("restore_latest")
            if callable(restore_latest):
                with st.spinner("신규 없음 → 최신 릴리스 자동 복구 중…"):
                    try:
                        restore_latest(PERSIST)
                    except Exception as e:
                        _log(f"auto restore 예외: {e}")
                st.session_state[auto_key] = True
                snap = sync_badge_from_fs()
                if snap["local_ok"]:
                    _request_step("완료")

    # CHECK_FAILED → 자동 복구는 하지 않고 안내
    if status == "CHECK_FAILED":
        with st.container(border=True):
            st.warning("prepared 점검에 실패했습니다. 네트워크/권한을 확인해 주세요.")
            st.caption(str((updates or {}).get("error", "")))

    # --- 수동 작업들 ---
    st.markdown("#### 작업")
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        do_force = st.button("강제 인덱싱(+백업 → READY)", key="btn_force_all",
                             help="인덱싱 후 자동으로 릴리스 백업을 발행하고 READY로 만듭니다.")
    with b2:
        do_restore = st.button("수동 복구(릴리스 → READY)", key="btn_restore_manual",
                               help="최신 릴리스에서 수동 복구합니다.")
    with b3:
        do_clean = st.button("강제 초기화(로컬)", key="btn_clean",
                             help="로컬 persist(.ready / chunks* / chunks/ 디렉터리)만 삭제합니다. "
                                  "GitHub 릴리스(원격 백업)는 삭제하지 않습니다.")

    if do_force:
        svc = _try_import("src.services.index", ["reindex"])
        reindex_fn = svc.get("reindex")
        with st.spinner("재인덱싱 중…"):
            ok1 = False
            try:
                ok1 = bool(reindex_fn(PERSIST)) if callable(reindex_fn) else False
            except TypeError:
                ok1 = bool(reindex_fn()) if callable(reindex_fn) else False
            except Exception as e:
                _log(f"reindex 예외: {e}")
                ok1 = False
        ok2 = False
        if ok1:
            gh = _try_import("src.backup.github_release", ["publish_backup"])
            pub = gh.get("publish_backup")
            if callable(pub):
                with st.spinner("GitHub 릴리스(백업) 발행 중…"):
                    ok2 = bool(pub(PERSIST))
            if not ok2:
                _log("publish_backup 실패/생략 — 로컬 READY는 유지됩니다.")
        snap = sync_badge_from_fs()
        if ok1 and snap["local_ok"]:
            st.success("강제 인덱싱(+백업) 완료(READY).")
            _request_step("완료")
        else:
            st.warning("강제 인덱싱(+백업) 후 READY 조건이 미충족입니다. 로그를 확인하세요.")

    if do_restore:
        gh2 = _try_import("src.backup.github_release", ["restore_latest"])
        restore_latest = gh2.get("restore_latest")
        if callable(restore_latest):
            with st.spinner("릴리스에서 복구 중…"):
                try:
                    ok = bool(restore_latest(PERSIST))
                except Exception as e:
                    _log(f"restore_latest 예외: {e}")
                    ok = False
            snap = sync_badge_from_fs()
            if ok and snap["local_ok"]:
                st.success("복구 완료(READY).")
                _request_step("완료")
            else:
                st.warning("복구 실패 또는 READY 미충족. 로그를 확인하세요.")

    if do_clean:
        try:
            removed = []
            for name in (".ready", "chunks.jsonl", "chunks.jsonl.gz"):
                p = PERSIST / name
                if p.exists():
                    p.unlink()
                    removed.append(name)
            d = PERSIST / "chunks"
            if d.exists() and d.is_dir():
                shutil.rmtree(d)
                removed.append("chunks/ (dir)")
            _log(f"강제 초기화: 제거 = {removed or '없음'}")
            st.success("강제 초기화 완료.")
        except Exception as e:
            _log(f"강제 초기화 실패: {e}")
            st.error("강제 초기화 실패. 권한/경로를 확인해 주세요.")

    # --- 로그 뷰 ---
    st.markdown("#### 오류 로그")
    st.text_area("최근 로그", value="\n".join(st.session_state[log_key][-200:]), height=220)
# =================== [03] render_index_orchestrator_panel — END ===================
