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
    관리자 진단/지식관리 패널 — LOCAL-FIRST 정책
      - 기본 원칙: 로컬 인덱스를 진실의 원천으로 사용
      - 부팅 시 자동 릴리스 복구 없음
      - 필요 시 운영자가 수동으로 (1) 재인덱싱 or (2) 릴리스 복구 실행
    """
    import time
    from pathlib import Path
    import importlib
    from typing import Any, Dict, List, Optional
    import shutil
    import os

    import streamlit as st  # 런타임 임포트

    # ---------- helpers ----------
    def _try_import(modname: str, names: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
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
            # 일부 환경에선 rerun이 실패할 수 있음(무시)
            pass

    def _apply_pending_step_before_widgets(steps: List[str]) -> None:
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

        def _snapshot_index_fallback(p: Optional[Path] = None) -> Dict[str, Any]:
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

        def _sync_badge_from_fs_fallback() -> Dict[str, Any]:
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

    steps = ["프리검사", "로컬 인덱싱", "완료"]
    st.session_state.setdefault("_orchestrator_step", steps[0])
    _apply_pending_step_before_widgets(steps)

    # 현 스냅샷
    snap = snapshot_index(PERSIST)
    ready = bool(snap.get("local_ok"))

    # --- header ---
    st.subheader("🛠 진단 도구 (LOCAL-FIRST)")

    # === prepared(선택적) 검사: 실패해도 동작엔 영향 없음 ===
    chk = _try_import("src.drive.prepared", ["check_prepared_updates", "mark_prepared_consumed"])
    check_fn = chk.get("check_prepared_updates")
    mark_fn = chk.get("mark_prepared_consumed")
    updates: Dict[str, Any] = {"status": "CHECK_FAILED"}
    if callable(check_fn):
        try:
            r = check_fn(PERSIST)
            if isinstance(r, dict):
                updates = r
        except Exception as e:
            updates = {"status": "CHECK_FAILED", "error": str(e)}

    # --- 상태 요약 ---
    with st.container():
        st.markdown("#### 상태 요약")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.write("로컬: " + ("**READY**" if ready else "**MISSING**"))
            st.code(str(PERSIST), language="text")
        with c2:
            st.write(f"prepared: **{updates.get('status','CHECK_FAILED')}**")
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

    # --- 단계 도움말 ---
    with st.expander("ℹ️ 단계 도움말 보기"):
        st.markdown(
            "- **프리검사**: 준비된(prepared) 신규 파일 유무만 확인합니다. 실패해도 동작엔 영향이 없습니다.\n"
            "- **로컬 인덱싱**: 로컬 기준으로 인덱스를 빌드합니다. 성공 시 `.ready` 및 `manifest.json`이 갱신됩니다.\n"
            "- **완료**: 최신 인덱스가 활성화된 상태입니다."
        )

    # === 작업 버튼(LOCAL-FIRST) ===
    log_key = "_orchestrator_log"
    st.session_state.setdefault(log_key, [])

    def _log(msg: str) -> None:
        st.session_state[log_key].append(f"{time.strftime('%H:%M:%S')}  {msg}")

    st.markdown("#### 작업")
    cA, cB, cC = st.columns([1, 1, 1])
    with cA:
        do_reindex = st.button(
            "재인덱싱(로컬 기준 → READY)",
            key="btn_reindex_local",
            help="로컬 기준으로 인덱스를 새로 빌드합니다. (릴리스 복구 없음)",
        )
    with cB:
        do_force = st.button(
            "강제 인덱싱(+백업 → READY)",
            key="btn_force_with_backup",
            help="로컬 기준 재인덱싱 후 GitHub 릴리스에 백업을 발행합니다.",
        )
    with cC:
        do_force_hq = st.button(
            "강제 인덱싱(HQ, 느림) + 백업",
            key="btn_force_hq",
            help="고품질(HQ) 모드로 인덱싱합니다. 토큰/정제 비용과 시간이 더 들 수 있습니다.",
        )

    with st.expander("고급(수동 복구/초기화)"):
        c1, c2 = st.columns([1, 1])
        with c1:
            do_restore = st.button(
                "수동 복구(릴리스 → READY)",
                key="btn_restore_manual",
                help="원격 릴리스에서 수동 복구합니다. LOCAL-FIRST 정책에서도 예외적으로 사용할 수 있습니다.",
            )
        with c2:
            do_clean = st.button(
                "강제 초기화(로컬)",
                key="btn_clean",
                help="로컬 persist(.ready, chunks*, chunks/ 디렉터리)만 삭제합니다. 릴리스는 삭제하지 않습니다.",
            )

    # --- 동작 구현 ---
    def _run_reindex_and_maybe_backup(force_backup: bool) -> tuple[bool, bool]:
        svc = _try_import("src.services.index", ["reindex"])
        reindex_fn = svc.get("reindex")
        ok1 = False
        with st.spinner("재인덱싱(로컬) 중…"):
            try:
                ok1 = bool(reindex_fn(PERSIST)) if callable(reindex_fn) else False
            except TypeError:
                ok1 = bool(reindex_fn()) if callable(reindex_fn) else False
            except Exception as e:
                _log(f"reindex 예외: {e}")
                ok1 = False
        ok2 = False
        if force_backup and ok1:
            gh = _try_import("src.backup.github_release", ["publish_backup"])
            pub = gh.get("publish_backup")
            if callable(pub):
                with st.spinner("GitHub 릴리스(백업) 발행 중…"):
                    try:
                        ok2 = bool(pub(PERSIST))
                    except Exception as e:
                        _log(f"publish_backup 예외: {e}")
                        ok2 = False
        return ok1, ok2

    if do_reindex:
        ok, _ = _run_reindex_and_maybe_backup(force_backup=False)
        snap2 = sync_badge_from_fs()
        if ok and snap2["local_ok"]:
            st.success("재인덱싱 완료(READY).")
            if callable(mark_fn) and isinstance(updates, dict):
                try:
                    files_raw: Any = updates.get("files", [])
                    files_list: List[Dict[str, Any]] = files_raw if isinstance(files_raw, list) else []
                    mark_fn(PERSIST, files_list)
                except Exception:
                    pass
            _request_step("완료")
        else:
            st.warning("재인덱싱 후 READY 미충족. 로그를 확인하세요.")

    if do_force:
        ok1, ok2 = _run_reindex_and_maybe_backup(force_backup=True)
        snap3 = sync_badge_from_fs()
        if ok1 and snap3["local_ok"]:
            msg = "강제 인덱싱(+백업) 완료(READY)." if ok2 else "강제 인덱싱 완료(READY). 백업은 실패/생략."
            st.success(msg)
            _request_step("완료")
        else:
            st.warning("강제 인덱싱 후 READY 미충족. 로그를 확인하세요.")

    if do_force_hq:
        # HQ 모드: 환경변수로 모드 전달 → manifest.mode=HQ
        prev_mode = os.getenv("MAIC_INDEX_MODE", "")
        os.environ["MAIC_INDEX_MODE"] = "HQ"
        try:
            ok1, ok2 = _run_reindex_and_maybe_backup(force_backup=True)
        finally:
            # 이전 모드 복원
            if prev_mode:
                os.environ["MAIC_INDEX_MODE"] = prev_mode
            else:
                try:
                    del os.environ["MAIC_INDEX_MODE"]
                except Exception:
                    pass
        snap4 = sync_badge_from_fs()
        if ok1 and snap4["local_ok"]:
            msg = "강제 인덱싱(HQ, +백업) 완료(READY)." if ok2 else "강제 인덱싱(HQ) 완료. 백업은 실패/생략."
            st.success(msg)
            _request_step("완료")
        else:
            st.warning("강제 인덱싱(HQ) 후 READY 미충족. 로그를 확인하세요.")

    if do_restore:
        gh2 = _try_import("src.backup.github_release", ["restore_latest"])
        restore_latest = gh2.get("restore_latest")
        if callable(restore_latest):
            with st.spinner("릴리스에서 수동 복구 중…"):
                try:
                    ok = bool(restore_latest(PERSIST))
                except Exception as e:
                    _log(f"restore_latest 예외: {e}")
                    ok = False
            snap = sync_badge_from_fs()
            if ok and snap["local_ok"]:
                st.success("수동 복구 완료(READY).")
                _request_step("완료")
            else:
                st.warning("수동 복구 실패 또는 READY 미충족. 로그를 확인하세요.")

    if do_clean:
        try:
            removed: List[str] = []
            for name in (".ready", "chunks.jsonl", "chunks.jsonl.gz"):
                p = PERSIST / name
                if p.exists():
                    p.unlink()
                    removed.append(name)
            d = PERSIST / "chunks"
            if d.exists() and d.is_dir():
                shutil.rmtree(d)
                removed.append("chunks/ (dir)")
            st.success("강제 초기화(로컬) 완료.")
            _log(f"강제 초기화: 제거 = {removed or '없음'}")
        except Exception as e:
            _log(f"강제 초기화 실패: {e}")
            st.error("강제 초기화 실패. 권한/경로를 확인해 주세요.")

    # --- 로그 뷰 ---
    st.markdown("#### 오류 로그")
    st.text_area("최근 로그", value="\n".join(st.session_state[log_key][-200:]), height=220)
# =================== [03] render_index_orchestrator_panel — END ===================
