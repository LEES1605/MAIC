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


# ====================== [02] Index Orchestrator Panel — START ======================
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st


def _persist_dir() -> Path:
    """
    app.py와 동일 규칙으로 퍼시스트 디렉터리를 해석한다.
    1) src.rag.index_build.PERSIST_DIR
    2) src.config.PERSIST_DIR
    3) ~/.maic/persist (폴백)
    """
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
        chunks = persist / "chunks.jsonl"
        return ready and chunks.exists() and chunks.stat().st_size > 0
    except Exception:
        return False


def render_index_orchestrator_panel() -> None:
    """
    (중복 제거 버전)
    - 상단 오케스트레이터 패널에서는 레거시 인덱싱 버튼을 모두 제거한다.
    - 실제 인덱싱(강제 인덱싱(HQ, 느림)+백업)은 app.py의 [15] 관리자 인덱싱 패널을 이용.
    - 여기서는 인덱스 상태, 경로, 가이드만 노출한다.
    """
    st.markdown("### 🧭 인덱스 오케스트레이터")
    persist = _persist_dir()
    ok = _is_ready(persist)

    c1, c2 = st.columns([2, 3])
    with c1:
        st.write("**Persist Dir**")
        st.code(str(persist), language="text")
        st.write("**상태**")
        st.success("READY") if ok else st.warning("MISSING")

    with c2:
        st.info(
            "강제 인덱싱(HQ, 느림)+백업은 **관리자 인덱싱 패널([15])**에서 실행하세요.\n"
            "- 관리자 모드 진입 → 하단의 *인덱싱(관리자)* 섹션으로 이동\n"
            "- 인덱싱 완료 후 ‘업데이트 점검(Drive/Local)’을 눌러 신규파일 감지 여부를 확인하세요."
        )

    with st.expander("도움말 / 트러블슈팅", expanded=False):
        st.markdown(
            "- 인덱싱 후에도 *신규파일 감지*가 뜬다면, prepared **전체 목록**이 `seen` 처리되지 않은 것입니다.\n"
            "  - app.py의 [15] 패널은 인덱싱 직후 `check_prepared_updates()`로 드라이버를 확인하고,\n"
            "    드라이버별 **전체 목록**을 재조회해 `mark_prepared_consumed()`에 전달합니다.\n"
            "- `chunks.jsonl`이 없거나 0B이면 READY가 되지 않습니다."
        )

    # (선택) 현재 인덱스 파일 존재만 간단 표시
    try:
        cj = persist / "chunks.jsonl"
        if cj.exists():
            st.caption(f"`chunks.jsonl` 존재: {cj.stat().st_size:,} bytes")
        else:
            st.caption("`chunks.jsonl`이 아직 없습니다.")
    except Exception:
        pass
# ======================= [02] Index Orchestrator Panel — END =======================

# ================== [03] render_index_orchestrator_panel — START ==================
def render_index_orchestrator_panel() -> None:
    """
    관리자 진단/지식관리 패널 — LOCAL-FIRST 정책
      - 기본 원칙: 로컬 인덱스를 진실의 원천으로 사용
      - 부팅 시 자동 릴리스 복구 없음
      - 필요 시 운영자가 수동으로 (1) 재인덱싱 or (2) 릴리스 복구 실행
      - prepared 폴더에 신규 파일이 있으면 즉시 선택 액션(재인덱싱 vs 복구) 제공
    """
    import os
    import time
    from pathlib import Path
    import importlib
    from typing import Any, Dict, List, Optional
    import shutil

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

    # prepared 상태 해석
    files_raw: Any = updates.get("files", [])
    files_list: List[Dict[str, Any]] = files_raw if isinstance(files_raw, list) else []
    has_prepared = bool(files_list) or str(updates.get("status", "")).upper() in {
        "NEW",
        "FOUND",
        "READY",
    }
    prepared_count = len(files_list)

    # --- 상태 요약 ---
    with st.container():
        st.markdown("#### 상태 요약")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.write("로컬: " + ("**READY**" if ready else "**MISSING**"))
            st.code(str(PERSIST), language="text")
        with c2:
            prep_label = updates.get("status", "CHECK_FAILED")
            st.write(f"prepared: **{prep_label}**")
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
            "- **프리검사**: prepared 신규 파일 유무만 확인합니다. 실패해도 동작엔 영향이 없습니다.\n"
            "- **로컬 인덱싱**: 로컬 기준으로 인덱스를 빌드합니다. 성공 시 `.ready` 및 `manifest.json`이 갱신됩니다.\n"
            "- **완료**: 최신 인덱스가 활성화된 상태입니다."
        )

    # === 작업 버튼(LOCAL-FIRST) ===
    log_key = "_orchestrator_log"
    st.session_state.setdefault(log_key, [])

    def _log(msg: str) -> None:
        st.session_state[log_key].append(f"{time.strftime('%H:%M:%S')}  {msg}")

    # --- prepared 신규 파일이 있을 때 즉시 선택 액션 ---
    if has_prepared:
        with st.container(border=True):
            st.markdown("### 📂 Prepared 감지됨")
            st.write(
                "prepared 폴더에 **신규 파일**이 감지되었습니다. "
                "다음 중 하나를 선택해 진행하세요."
            )
            colA, colB = st.columns([1, 1])
            with colA:
                do_prepared_reindex = st.button(
                    "신규 파일로 재인덱싱",
                    key="btn_prepared_reindex",
                    help="prepared 폴더의 신규 파일을 바탕으로 로컬 인덱스를 재생성합니다.",
                )
            with colB:
                do_prepared_restore = st.button(
                    "기존 릴리스에서 복구",
                    key="btn_prepared_restore",
                    help="prepared 파일을 보류하고, 최신 GitHub 릴리스에서 복구합니다.",
                )

            with st.expander(f"파일 미리보기({prepared_count}건)"):
                # 파일 정보가 있다면 간단히 나열
                if files_list:
                    for i, meta in enumerate(files_list[:100], start=1):
                        name = str(meta.get("name") or meta.get("path") or f"file-{i}")
                        size = meta.get("size")
                        size_s = f"{size:,} bytes" if isinstance(size, int) else "-"
                        st.write(f"- {name}  ·  {size_s}")
                else:
                    st.write("파일 목록 정보가 없습니다.")

            # 선택 동작 구현
            if 'do_prepared_reindex' not in locals():
                do_prepared_reindex = False
            if 'do_prepared_restore' not in locals():
                do_prepared_restore = False

            if do_prepared_reindex:
                svc = _try_import("src.services.index", ["reindex"])
                reindex_fn = svc.get("reindex")
                with st.spinner("재인덱싱(신규 파일 기반) 중…"):
                    ok = False
                    try:
                        ok = bool(reindex_fn(PERSIST)) if callable(reindex_fn) else False
                    except TypeError:
                        ok = bool(reindex_fn()) if callable(reindex_fn) else False
                    except Exception as e:
                        _log(f"reindex 예외: {e}")
                        ok = False
                    # -------- 폴백: index_build.rebuild_index --------
                    if not ok:
                        try:
                            from src.rag import index_build as _idx
                            r = _idx.rebuild_index(PERSIST)
                            ok = bool(r and r.get("chunks", 0) > 0)
                        except Exception as e:
                            _log(f"rebuild_index 폴백 예외: {e}")
                            ok = False
                snap2 = sync_badge_from_fs()
                if ok and snap2["local_ok"]:
                    st.success("재인덱싱 완료(READY).")
                    # prepared 소비 처리(성공시에만)
                    if callable(mark_fn) and isinstance(files_list, list):
                        try:
                            mark_fn(PERSIST, files_list)
                        except Exception:
                            pass
                    _request_step("완료")
                else:
                    st.warning("재인덱싱 후 READY 미충족. 로그를 확인하세요.")

            if do_prepared_restore:
                gh2 = _try_import("src.backup.github_release", ["restore_latest"])
                restore_latest = gh2.get("restore_latest")
                if callable(restore_latest):
                    with st.spinner("최신 릴리스에서 복구 중…"):
                        try:
                            ok = bool(restore_latest(PERSIST))
                        except Exception as e:
                            _log(f"restore_latest 예외: {e}")
                            ok = False
                    snap3 = sync_badge_from_fs()
                    if ok and snap3["local_ok"]:
                        st.success("복구 완료(READY).")
                        # prepared 파일은 그대로 유지(소비하지 않음)
                        _request_step("완료")
                    else:
                        st.warning("복구 실패 또는 READY 미충족. 로그를 확인하세요.")

    # --- 일반 작업 영역 ---
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

    # --- 동작 구현 (공통 유틸) ---
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
            # -------- 폴백: index_build.rebuild_index --------
            if not ok1:
                try:
                    from src.rag import index_build as _idx
                    r = _idx.rebuild_index(PERSIST)
                    ok1 = bool(r and r.get("chunks", 0) > 0)
                except Exception as e:
                    _log(f"rebuild_index 폴백 예외: {e}")
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
            # prepared 소비: 일반 재인덱싱은 기본적으로 prepared를 사용하지 않을 수 있어
            # 여기서는 소비하지 않음(선택 액션 구역에서만 소비)
            _request_step("완료")
        else:
            st.warning("재인덱싱 후 READY 미충족. 로그를 확인하세요.")

    if do_force:
        ok1, ok2 = _run_reindex_and_maybe_backup(force_backup=True)
        snap3 = sync_badge_from_fs()
        if ok1 and snap3["local_ok"]:
            msg = (
                "강제 인덱싱(+백업) 완료(READY)."
                if ok2
                else "강제 인덱싱 완료(READY). 백업은 실패/생략."
            )
            st.success(msg)
            _request_step("완료")
        else:
            st.warning("강제 인덱싱 후 READY 미충족. 로그를 확인하세요.")

    if do_force_hq:
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
            msg = (
                "강제 인덱싱(HQ, +백업) 완료(READY)."
                if ok2
                else "강제 인덱싱(HQ) 완료. 백업은 실패/생략."
            )
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
