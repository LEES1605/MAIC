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
            deps["get_latest_release"] = mod_rel.get_latest_release  # type: ignore[attr-defined]
        except Exception:
            deps["get_latest_release"] = None
        try:
            deps["fetch_manifest_from_release"] = mod_rel.fetch_manifest_from_release  # type: ignore[attr-defined]
        except Exception:
            deps["fetch_manifest_from_release"] = None
        try:
            deps["restore_latest"] = mod_rel.restore_latest  # type: ignore[attr-defined]
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
    관리자 진단 도구 패널(네트워크 호출 지연 + 버튼 클릭 시 실행)
    - Drive/GitHub/Index 연동은 index_build/backup 모듈의 실제 시그니처에 맞춤
    - 버튼 실행 중에는 spinner를 표시하고, 에러는 하단 로그에 누적
    """
    import time

    import streamlit as st

    # 패널 타이틀(직관형)
    st.markdown("## 🛠 진단 도구")

    # 1) 의존성
    deps = _lazy_imports()
    PERSIST_DIR = deps.get("PERSIST_DIR")
    p = PERSIST_DIR if isinstance(PERSIST_DIR, Path) else Path(str(PERSIST_DIR))

    get_latest_release = deps.get("get_latest_release")
    restore_latest = deps.get("restore_latest")
    _drive_client = deps.get("_drive_client")
    _find_folder_id = deps.get("_find_folder_id")
    diff_with_manifest = deps.get("diff_with_manifest")
    build_index_with_checkpoint = deps.get("build_index_with_checkpoint")

    ss = st.session_state
    ss.setdefault("_orch_diag", {})
    ss.setdefault("_orchestrator_errors", [])

    # 2) 상태 요약
    with st.container(border=True):
        st.markdown("### 📋 상태 요약")
        c1, c2, c3 = st.columns([0.38, 0.34, 0.28])
        with c1:
            run_diag = st.button("🔎 빠른 점검", type="primary", use_container_width=True)
        with c2:
            clear_diag = st.button("♻️ 결과 초기화", use_container_width=True)
        with c3:
            st.caption("버튼 클릭 시에만 네트워크 점검")

        if clear_diag:
            ss["_orch_diag"] = {}
            ss["_orchestrator_errors"] = []
            st.success("진단 결과와 오류 로그를 초기화했습니다.")

        if run_diag:
            t0 = time.perf_counter()
            with st.spinner("빠른 점검 실행 중…"):
                # Drive
                drive_ok = False
                drive_email: Optional[str] = None
                if callable(_drive_client):
                    try:
                        svc = _drive_client()
                        about = svc.about().get(fields="user").execute()
                        drive_email = (about or {}).get("user", {}).get("emailAddress")
                        drive_ok = True
                    except Exception as e:
                        _add_error(e)

                # GitHub
                gh_ok = False
                gh_tag: Optional[str] = None
                if callable(get_latest_release):
                    try:
                        gh_latest = get_latest_release()
                        gh_ok = bool(gh_latest)
                        gh_tag = gh_latest.get("tag_name") if gh_latest else None
                    except Exception as e:
                        _add_error(e)

                ss["_orch_diag"] = {
                    "drive_ok": drive_ok,
                    "drive_email": drive_email,
                    "gh_ok": gh_ok,
                    "gh_tag": gh_tag,
                }
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            st.success(f"빠른 점검 완료 ({elapsed_ms:.0f} ms)")

        # 결과 표시
        d = ss.get("_orch_diag") or {}

        def _badge(ok: Optional[bool], label: str) -> str:
            if ok is True:
                return f"✅ {label}"
            if ok is False:
                return f"❌ {label}"
            return f"— {label}"

        local_ok = (p / "chunks.jsonl").exists() and (p / ".ready").exists()

        drive_label = "연결"
        if d.get("drive_email"):
            drive_label = f"연결(`{d.get('drive_email')}`)"
        st.write("- Drive:", _badge(d.get("drive_ok"), drive_label))

        gh_label = f"최신 릴리스: {d.get('gh_tag') or '없음'}"
        st.write("- GitHub:", _badge(d.get("gh_ok"), gh_label))

        st.write("- 로컬:", _badge(local_ok, "인덱스/ready 파일 상태"))

    # 3) 변경사항
    with st.container(border=True):
        st.markdown("### 🔔 변경사항")
        added = 0
        changed = 0
        removed = 0
        details = {"added": [], "changed": [], "removed": []}
        if callable(diff_with_manifest):
            try:
                dct = diff_with_manifest(folder_id=None) or {}
                stats = dct.get("stats") or {}
                added = int(stats.get("added", 0))
                changed = int(stats.get("changed", 0))
                removed = int(stats.get("removed", 0))
                details["added"] = dct.get("added") or []
                details["changed"] = dct.get("changed") or []
                details["removed"] = dct.get("removed") or []
            except Exception as e:
                _add_error(e)
        st.write(f"새 항목: **{added}** · 변경: **{changed}** · 삭제: **{removed}**")
        for label, arr in (("신규", details["added"]), ("변경", details["changed"]), ("삭제", details["removed"])):
            if arr:
                with st.expander(f"{label} {len(arr)}개 보기"):
                    for x in arr:
                        st.write("•", x)

        has_new = (added + changed + removed) > 0
        if has_new:
            st.info("📢 변경사항이 감지되었습니다. 선택하여 진행하세요.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 재인덱싱 실행", use_container_width=True, type="primary"):
                    if callable(build_index_with_checkpoint):
                        try:
                            with st.spinner("재인덱싱 중…"):
                                res = build_index_with_checkpoint(
                                    force=False,
                                    prefer_release_restore=False,
                                    folder_id=_find_folder_id(None) if callable(_find_folder_id) else None,
                                )
                            if isinstance(res, dict) and res.get("ok"):
                                _ready_mark(p)
                                st.success("✅ 업데이트 완료(재인덱싱)")
                            else:
                                st.error("업데이트가 완료되지 않았습니다.")
                        except Exception as e:
                            _add_error(e)
                            st.error("업데이트 중 오류가 발생했습니다.")
                    else:
                        st.error("build_index_with_checkpoint 사용 불가(임포트 실패)")
            with c2:
                if st.button("📦 백업에서 복원", use_container_width=True):
                    if callable(restore_latest):
                        try:
                            with st.spinner("백업에서 복원 중…"):
                                ok = bool(restore_latest(dest_dir=p))
                            if ok:
                                _ready_mark(p)
                                st.success("✅ 백업 복원 완료")
                            else:
                                st.error("복원에 실패했습니다.")
                        except Exception as e:
                            _add_error(e)
                            st.error("복원 중 오류가 발생했습니다.")
                    else:
                        st.error("restore_latest 사용 불가(임포트 실패)")
        else:
            st.success("변경 사항이 없습니다. (최신 상태)")

    # 4) 강제 재인덱싱
    with st.container(border=True):
        st.markdown("### ⛏ 강제 재인덱싱")
        if st.button("⛏ 강제 재인덱싱", use_container_width=True):
            if callable(build_index_with_checkpoint):
                try:
                    with st.spinner("로컬 인덱싱 중…"):
                        res = build_index_with_checkpoint(
                            force=True,
                            prefer_release_restore=False,
                            folder_id=_find_folder_id(None) if callable(_find_folder_id) else None,
                        )
                    if isinstance(res, dict) and res.get("ok"):
                        _ready_mark(p)
                        st.success("✅ 인덱싱 완료")
                    else:
                        st.error("인덱싱이 완료되지 않았습니다.")
                except Exception as e:
                    _add_error(e)
                    st.error("인덱싱 중 오류가 발생했습니다.")
            else:
                st.error("build_index_with_checkpoint 사용 불가(임포트 실패)")

    # 5) 오류 로그
    with st.container(border=True):
        st.markdown("### 🧯 오류 로그")
        txt = _errors_text()
        st.text_area("최근 오류", value=txt, height=160)
        st.download_button(
            "오류 로그 다운로드", data=txt.encode("utf-8"), file_name="orchestrator_errors.txt"
        )


# =================== [03] render_index_orchestrator_panel — END ===================
