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
    관리자 진단/지식관리 패널 렌더링.
    - 재인덱싱 버튼을 '항상' 노출(필요 시 안내)
    - READY(.ready + chunks.jsonl>0B) 이전에는 '완료' 스텝 잠금(🔒)
    - 단계별 설명 팝오버/툴팁 제공
    - 실패 시 세부 원인(READY 신호/파일 존재/크기/세션 메시지) 즉시 로그 남김
    - 추가: 릴리스 복구 라벨 명확화, 강제 초기화, 파일 스냅샷 보기
    - NEW: 자동 완료(성공 시 스텝을 '완료'로 이동), 강제 재인덱싱(HQ) 버튼
    """
    import time
    from pathlib import Path
    import importlib
    from typing import Any
    import shutil
    import os  # NEW

    import streamlit as st  # 런타임 임포트

    # ---------- helpers (사용 전에 미리 정의) ----------
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

    def _list_files(p: Path, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            for idx, q in enumerate(sorted(p.glob("*"))):
                if idx >= limit:
                    break
                try:
                    rows.append({
                        "name": q.name,
                        "type": "dir" if q.is_dir() else "file",
                        "size": (q.stat().st_size if q.is_file() else -1),
                    })
                except Exception:
                    rows.append({"name": q.name, "type": "?", "size": -1})
        except Exception:
            pass
        return rows

    # --- NEW: 세션/스냅샷 API 동적 로드(정적 import 제거 → mypy import-not-found 방지) ---
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

        # 폴백 구현체들
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

    # ---------- state ----------
    ensure_keys()
    PERSIST = _persist_dir()
    snap = snapshot_index(PERSIST)
    ready = bool(snap.get("local_ok"))

    # ---------- steps & tips ----------
    steps = ["프리검사", "백업훑", "변경검지", "다운로드", "복구/해체", "연결성", "완료"]
    STEP_TIPS = {
        "프리검사": "로컬 경로 및 신호(.ready/chunks.jsonl) 점검",
        "백업훑": "GitHub/Drive 백업 존재 여부·최신성 조회(네트워크는 버튼 때만)",
        "변경검지": "원천(Drive) 대비 증감·변경 파일 탐지(diff)",
        "다운로드": "릴리스 자산(.zip/.tar.gz/.gz) 다운로드",
        "복구/해체": "압축 해제 후 로컬에 복구/부착(평탄화/병합 포함)",
        "연결성": "인덱스 attach, 모델/키 확인",
        "완료": "학생 질의 가능(READY) 최종 확인",
    }

    # ✅ 위젯 생성 '이전'에 상태 보정(READY 전 '완료' 선택 차단)
    st.session_state.setdefault("_orchestrator_step", steps[0])
    if not ready and st.session_state["_orchestrator_step"] == "완료":
        st.session_state["_orchestrator_step"] = steps[0]

    # ---------- header & stepper ----------
    left, right = st.columns([1, 1])
    with left:
        st.subheader("🛠 진단 도구")
    with right:
        # 단계 설명 팝오버(클릭식). 환경에 따라 popover 미지원 시 expander로 폴백
        try:
            with st.popover("ⓘ 단계 설명", use_container_width=False):
                st.markdown("| 단계 | 설명 |")
                st.markdown("|---|---|")
                for s in steps:
                    st.markdown(f"| {s} | {STEP_TIPS.get(s,'—')} |")
        except Exception:
            with st.expander("ⓘ 단계 설명", expanded=False):
                st.markdown("| 단계 | 설명 |")
                st.markdown("|---|---|")
                for s in steps:
                    st.markdown(f"| {s} | {STEP_TIPS.get(s,'—')} |")

    # segmented_control가 없는 환경에서는 radio로 폴백
    try:
        st.segmented_control(
            "단계",
            steps,
            key="_orchestrator_step",
            help="단계 위 또는 ‘ⓘ 단계 설명’을 눌러 각 단계의 의미를 확인하세요.",
        )
    except Exception:
        st.radio(
            "단계",
            steps,
            key="_orchestrator_step",
            horizontal=True,
            help="‘ⓘ 단계 설명’을 눌러 각 단계의 의미를 확인하세요.",
        )

    # ---------- status summary ----------
    with st.container(border=True):
        st.markdown("#### 상태 요약")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.caption("로컬")
            st.write("🧠 " + ("**READY** (.ready+chunks)" if ready else "**MISSING**"))
            st.code(str(PERSIST), language="text")
        with c2:
            st.caption("GitHub")
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
            st.write(f"릴리스: **{latest_tag}**")
        with c3:
            st.caption("Drive")
            st.write("네트워크 점검은 버튼 클릭 시에만 수행합니다.")

    # ---------- actions ----------
    st.markdown("#### 작업")
    b1, b2, b3, b4, b5, b6 = st.columns([1, 1, 1, 1, 1, 1])
    with b1:
        do_quick = st.button(
            "빠른 점검",
            key="btn_quick",
            help="버튼 클릭 시에만 네트워크를 확인합니다.",
        )
    with b2:
        do_reset = st.button(
            "결과 초기화",
            key="btn_reset",
            help="진단 결과/오류 로그 뷰를 초기화합니다.",
        )
    with b3:
        do_update = st.button(
            "릴리스 복구(업데이트)",
            key="btn_restore",
            help="GitHub 최신 릴리스에서 복구를 시도합니다.",
        )
    with b4:
        do_reindex = st.button(
            "재인덱싱",
            key="btn_reindex",
            help="로컬 인덱스를 새로 구축합니다(항상 표시).",
        )
    with b5:
        do_clean = st.button(
            "강제 초기화",
            key="btn_clean",
            help="persist의 .ready / chunks* / chunks/ 를 삭제하고 깨끗이 시작합니다.",
        )
    with b6:
        do_reindex_hq = st.button(
            "강제 재인덱싱(HQ)",
            key="btn_reindex_hq",
            help="강제초기화 후 HQ 모드(작은 청크, 높은 오버랩, 상한↑)로 깊게 재인덱싱합니다.",
        )

    # ---------- log area ----------
    log_key = "_orchestrator_log"
    if do_reset:
        st.session_state[log_key] = []
    st.session_state.setdefault(log_key, [])

    def _log(msg: str) -> None:
        st.session_state[log_key].append(f"{time.strftime('%H:%M:%S')}  {msg}")

    # ---------- file snapshot ----------
    with st.expander("📁 현재 PERSIST_DIR 파일 스냅샷(상위 50개)", expanded=False):
        rows = _list_files(PERSIST, 50)
        if not rows:
            st.write("표시할 항목이 없습니다.")
        else:
            st.dataframe(rows, use_container_width=True, hide_index=True)

    # ---------- quick check ----------
    if do_quick:
        snap = snapshot_index(PERSIST)
        _log(f"local: {'READY' if snap['local_ok'] else 'MISSING'} — {snap}")
        gh_info = _try_import("src.backup.github_release", ["get_latest_release"])
        get_latest = gh_info.get("get_latest_release")
        try:
            rel = get_latest() if callable(get_latest) else None
            if isinstance(rel, dict):
                tag = rel.get("tag_name") or rel.get("name") or "없음"
                _log(f"github: 최신 릴리스 = {tag}")
                st.success(f"GitHub 최신 릴리스: {tag}")
            else:
                _log("github: 최신 릴리스 없음 또는 조회 실패")
                st.info("GitHub 최신 릴리스: 없음/조회 실패")
        except Exception as e:
            _log(f"github 조회 실패: {e}")
            st.warning("GitHub 조회 실패(토큰/권한/네트워크)")

    # ---------- clean reset ----------
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
            st.success("강제 초기화 완료. 이제 릴리스 복구 또는 재인덱싱을 실행해 주세요.")
        except Exception as e:
            _log(f"강제 초기화 실패: {e}")
            st.error("강제 초기화 실패. 권한/경로를 확인해 주세요.")

    # ---------- update from release ----------
    if do_update:
        gh2 = _try_import("src.backup.github_release", ["restore_latest"])
        restore_latest = gh2.get("restore_latest")
        if callable(restore_latest):
            with st.spinner("GitHub 릴리스에서 복구 중…"):
                ok = False
                try:
                    ok = bool(restore_latest(PERSIST))
                except Exception as e:
                    _log(f"restore_latest 예외: {e}")
                snap = sync_badge_from_fs()  # 배지 동기화
                if ok and snap["local_ok"]:
                    _log(f"restore 결과: READY — {snap}")
                    st.success("복구 완료.")
                    st.session_state["_orchestrator_step"] = "완료"  # NEW: 자동 완료
                elif ok and not snap["local_ok"]:
                    _log(f"restore 결과: MISSING — {snap}")
                    st.warning("복구는 성공했지만 READY 조건(.ready+chunks)이 충족되지 않았습니다.")
                else:
                    _log(f"restore 실패 — {snap}")
                    st.error("복구 실패. 오류 로그를 확인해 주세요.")
        else:
            st.info("restore_latest 함수를 찾지 못했습니다. 모듈 버전을 확인해 주세요.")

    # ---------- reindex (always visible) ----------
    if do_reindex:
        svc = _try_import("src.services.index", ["reindex"])
        fn = svc.get("reindex")
        if not callable(fn):
            idx = _try_import(
                "src.rag.index_build",
                [
                    "rebuild_index",
                    "build_index",
                    "rebuild",
                    "index_all",
                    "build_all",
                    "build_index_with_checkpoint",
                ],
            )
            fn = next(
                (
                    idx[n]
                    for n in (
                        "rebuild_index",
                        "build_index",
                        "rebuild",
                        "index_all",
                        "build_all",
                        "build_index_with_checkpoint",
                    )
                    if callable(idx.get(n))
                ),
                None,
            )

        if callable(fn):
            with st.spinner("재인덱싱(전체) 실행 중…"):
                success = False
                try:
                    try:
                        success = bool(fn(PERSIST))
                    except TypeError:
                        success = bool(fn())
                except Exception as e:
                    _log(f"reindex 예외: {e}")

                snap = sync_badge_from_fs()  # 배지 동기화
                bs_msg = str(st.session_state.get("brain_status_msg", ""))
                if success and snap["local_ok"]:
                    _log(f"reindex 결과: READY — {snap}")
                    if bs_msg:
                        _log(f"status_msg: {bs_msg}")
                    st.success("재인덱싱 완료.")
                    st.session_state["_orchestrator_step"] = "완료"  # NEW: 자동 완료
                elif success and not snap["local_ok"]:
                    _log(f"reindex 결과: MISSING — {snap}")
                    if bs_msg:
                        _log(f"status_msg: {bs_msg}")
                    st.warning("재인덱싱 후 READY 조건(.ready+chunks)이 충족되지 않았습니다.")
                else:
                    _log(f"reindex 실패 — {snap}")
                    if bs_msg:
                        _log(f"status_msg: {bs_msg}")
                    st.error("재인덱싱 실패. 오류 로그를 확인해 주세요.")
        else:
            st.info(
                "현재 버전에서 재인덱싱 함수가 정의되지 않았습니다. "
                "업데이트 점검(릴리스 복구) 또는 수동 인덱싱 스크립트를 사용해 주세요."
            )

    # ---------- reindex (HQ) ----------
    if do_reindex_hq:
        # 1) 강제 초기화
        try:
            for name in (".ready", "chunks.jsonl", "chunks.jsonl.gz"):
                (PERSIST / name).unlink(missing_ok=True)
            d = PERSIST / "chunks"
            if d.exists() and d.is_dir():
                shutil.rmtree(d)
        except Exception as e:
            _log(f"HQ 초기화 실패: {e}")

        # 2) HQ 모드 토글 (index_build가 env로 스위치)
        os.environ["MAIC_INDEX_MODE"] = "HQ"

        # 3) 인덱서 직접 호출(서비스 경유 대신 HQ 확실 적용)
        fn = _try_import("src.rag.index_build", ["rebuild_index"]).get("rebuild_index")
        if callable(fn):
            with st.spinner("강제 재인덱싱(HQ) 실행 중…"):
                try:
                    try:
                        fn(PERSIST)
                    except TypeError:
                        fn()
                except Exception as e:
                    _log(f"rebuild_index(HQ) 예외: {e}")

        # 4) 결과 반영
        snap = sync_badge_from_fs()
        if snap["local_ok"]:
            _log(f"reindex(HQ) 결과: READY — {snap}")
            st.success("강제 재인덱싱(HQ) 완료.")
            st.session_state["_orchestrator_step"] = "완료"  # NEW: 자동 완료
        else:
            _log(f"reindex(HQ) 결과: MISSING — {snap}")
            st.warning("HQ 재인덱싱 후 READY 조건(.ready+chunks)이 충족되지 않았습니다.")

    # ---------- log view ----------
    st.markdown("#### 오류 로그")
    st.text_area(
        "최근 로그",
        value="\n".join(st.session_state[log_key][-200:]),
        height=220,
    )
# =================== [03] render_index_orchestrator_panel — END ===================
