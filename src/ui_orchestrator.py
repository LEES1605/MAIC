# ======================== [00] orchestrator helpers — START ========================
from __future__ import annotations
import traceback
from pathlib import Path

def _add_error(e) -> None:
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
# ========================== [00B] lazy imports — START ============================
def _lazy_imports() -> dict:
    """
    의존 모듈을 '가능한 이름들'로 느슨하게 임포트해 dict로 반환.
    - PERSIST_DIR: (우선) src.rag.index_build.PERSIST_DIR → (또는) src.config.PERSIST_DIR → (폴백) ~/.maic/persist
    - Drive/Index/GitHub 릴리스 유틸은 실제 파일에 맞춰 탐색
    """
    import importlib
    from pathlib import Path as _P

    def _imp(name):
        try:
            return importlib.import_module(name)
        except Exception:
            return None

    deps = {}

    # --- PERSIST_DIR ---
    # 1) index_build 내부 상수
    mod_idx = _imp("src.rag.index_build")
    if mod_idx and hasattr(mod_idx, "PERSIST_DIR"):
        deps["PERSIST_DIR"] = getattr(mod_idx, "PERSIST_DIR")
    # 2) config 상수(있을 경우)
    if "PERSIST_DIR" not in deps:
        mod_cfg = _imp("src.config")
        if mod_cfg and hasattr(mod_cfg, "PERSIST_DIR"):
            deps["PERSIST_DIR"] = _P(getattr(mod_cfg, "PERSIST_DIR"))
    # 3) 최종 폴백
    if "PERSIST_DIR" not in deps or not deps["PERSIST_DIR"]:
        deps["PERSIST_DIR"] = _P.home() / ".maic" / "persist"

    # --- GitHub release / manifest ---
    # 실제 파일: src.backup.github_release
    mod_rel = _imp("src.backup.github_release")
    if mod_rel:
        deps["get_latest_release"] = getattr(mod_rel, "get_latest_release", None)
        deps["fetch_manifest_from_release"] = getattr(mod_rel, "fetch_manifest_from_release", None)
        deps["restore_latest"] = getattr(mod_rel, "restore_latest", None)

    # --- Google Drive / Index 유틸 (index_build 안에 구현되어 있음) ---
    if mod_idx:
        deps.setdefault("_drive_client", getattr(mod_idx, "_drive_client", None))
        deps.setdefault("_find_folder_id", getattr(mod_idx, "_find_folder_id", None))
        deps.setdefault("scan_drive_listing", getattr(mod_idx, "scan_drive_listing", None))
        deps.setdefault("diff_with_manifest", getattr(mod_idx, "diff_with_manifest", None))
        deps.setdefault("build_index_with_checkpoint", getattr(mod_idx, "build_index_with_checkpoint", None))

    return deps
# =========================== [00B] lazy imports — END =============================


# ======================== [01] autoflow_boot_check — START =========================
def _has_local_index(persist_dir: Path) -> bool:
    return (persist_dir / "chunks.jsonl").exists() and (persist_dir / ".ready").exists()

def autoflow_boot_check(*, interactive: bool) -> None:
    """
    앱 부팅 시 1회 실행되는 오토 플로우:
      - 로컬 인덱스 없으면: 최신 릴리스에서 자동 복원 → .ready 생성
      - 변경 감지 있으면:
          - interactive=True(관리자): 재인덱싱 vs 백업 사용 선택
          - interactive=False(학생): 백업 사용으로 자동 진행
      - 변경 없으면: 백업 동기화 후 .ready
    """
    import streamlit as st
    ss = st.session_state
    if ss.get("_boot_checked") is True:
        return

    deps = _lazy_imports()
    PERSIST_DIR = deps.get("PERSIST_DIR")
    restore_latest = deps.get("restore_latest")
    diff_with_manifest = deps.get("diff_with_manifest")
    _find_folder_id = deps.get("_find_folder_id")
    build_index_with_checkpoint = deps.get("build_index_with_checkpoint")

    p = PERSIST_DIR if isinstance(PERSIST_DIR, Path) else Path(str(PERSIST_DIR))

    # 0) 로컬 없으면 → 자동 복원
    if not _has_local_index(p):
        if callable(restore_latest):
            with st.spinner("초기화: 백업에서 로컬 복원 중…"):
                ok = False
                try:
                    ok = bool(restore_latest(dest_dir=p))
                except Exception as e:
                    _add_error(e)
            if ok:
                _ready_mark(p)
                ss["_boot_checked"] = True
                st.toast("✅ 백업에서 로컬 인덱스를 복원했습니다.", icon="✅")
                st.rerun()
        else:
            _add_error(RuntimeError("restore_latest 가 없습니다."))
            ss["_boot_checked"] = True
        return

    # 1) 변경 감지 (index_build의 diff 사용; folder_id=None이면 내부 규칙 사용)
    has_new = False
    try:
        if callable(diff_with_manifest):
            d = diff_with_manifest(folder_id=None) or {}
            stats = d.get("stats") or {}
            has_new = (int(stats.get("added",0)) + int(stats.get("changed",0)) + int(stats.get("removed",0))) > 0
    except Exception as e:
        _add_error(e)

    if has_new:
        if interactive:
            with st.expander("📢 새 자료 감지 — 처리 방식을 선택하세요", expanded=True):
                choice = st.radio("처리", ("재인덱싱 후 백업/복사", "현재 백업 사용"), horizontal=True)
                go = st.button("실행", type="primary")
                if go:
                    if choice.startswith("재인덱싱"):
                        if callable(build_index_with_checkpoint):
                            with st.spinner("재인덱싱 중…"):
                                ok=False
                                try:
                                    res = build_index_with_checkpoint(force=False, prefer_release_restore=False, folder_id=_find_folder_id(None) if callable(_find_folder_id) else None)
                                    ok = bool(res and res.get("ok"))
                                except Exception as e:
                                    _add_error(e)
                            if ok:
                                _ready_mark(p); ss["_boot_checked"] = True
                                st.success("✅ 재인덱싱 완료 및 로컬 준비됨")
                                st.rerun()
                            else:
                                st.error("재인덱싱이 완료되지 않았습니다.")
                        else:
                            st.error("인덱서 함수를 찾을 수 없습니다.")
                    else:
                        if callable(restore_latest):
                            with st.spinner("백업을 로컬에 복원 중…"):
                                ok=False
                                try:
                                    ok = bool(restore_latest(dest_dir=p))
                                except Exception as e:
                                    _add_error(e)
                            if ok:
                                _ready_mark(p); ss["_boot_checked"] = True
                                st.success("✅ 백업 복원 완료")
                                st.rerun()
                        else:
                            st.error("restore_latest 함수를 찾을 수 없습니다.")
            return
        else:
            # 학생 모드: 묻지 않고 백업 사용
            if callable(restore_latest):
                try:
                    restore_latest(dest_dir=p)
                    _ready_mark(p)
                except Exception as e:
                    _add_error(e)
            ss["_boot_checked"] = True
            return
    else:
        # 새 자료 없음 → 백업 동기화 후 ready (보수적 동기화)
        if callable(restore_latest):
            try:
                restore_latest(dest_dir=p)
            except Exception as e:
                _add_error(e)
        _ready_mark(p)
        ss["_boot_checked"] = True
        return
# ========================= [01] autoflow_boot_check — END ==========================

# =========== render_index_orchestrator_panel — START ===========
def render_index_orchestrator_panel() -> None:
    """
    관리자 진단 도구 패널(네트워크 호출 지연 + 버튼 클릭 시 실행)
    - Drive/GitHub/Index 연동은 index_build/backup 모듈의 실제 시그니처에 맞춤
    - 버튼 실행 중에는 spinner를 표시하고, 에러는 하단 로그에 누적
    """
    import time
    import streamlit as st

    st.markdown("## 🧠 인덱스 진단 도구")

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

    # 2) 상태 점검 섹션
    with st.container(border=True):
        st.markdown("### 상태 점검")
        c1, c2, c3 = st.columns([0.38,0.34,0.28])
        with c1:
            run_diag = st.button("진단 실행", type="primary", use_container_width=True)
        with c2:
            clear_diag = st.button("진단 초기화", use_container_width=True)
        with c3:
            st.caption("버튼 클릭 시에만 네트워크 점검")

        if clear_diag:
            ss["_orch_diag"] = {}
            ss["_orchestrator_errors"] = []   # ← 오류도 함께 초기화
            st.success("진단 결과와 오류 로그를 초기화했습니다.")

        if run_diag:
            t0 = time.perf_counter()
            with st.spinner("진단 실행 중…"):
                # Drive
                drive_ok = False; drive_email = None
                if callable(_drive_client):
                    try:
                        svc = _drive_client()
                        about = svc.about().get(fields="user").execute()
                        drive_email = (about or {}).get("user", {}).get("emailAddress")
                        drive_ok = True
                    except Exception as e:
                        _add_error(e)
                # GitHub
                gh_ok = False; gh_tag = None
                if callable(get_latest_release):
                    try:
                        gh_latest = get_latest_release()
                        gh_ok = bool(gh_latest)
                        gh_tag = gh_latest.get("tag_name") if gh_latest else None
                    except Exception as e:
                        _add_error(e)
                ss["_orch_diag"] = {"drive_ok": drive_ok, "drive_email": drive_email,
                                    "gh_ok": gh_ok, "gh_tag": gh_tag}
            st.success(f"진단 완료 ({(time.perf_counter()-t0)*1000:.0f} ms)")

        # 결과 표시
        d = ss.get("_orch_diag") or {}
        def _badge(ok: bool|None, label: str) -> str:
            if ok is True:  return f"✅ {label}"
            if ok is False: return f"❌ {label}"
            return f"— {label}"
        local_ok = (p / "chunks.jsonl").exists() and (p / ".ready").exists()
        st.write("- Drive:", _badge(d.get('drive_ok'), f"연결" + (f"(`{d.get('drive_email')}`)" if d.get('drive_email') else "")))
        st.write("- GitHub:", _badge(d.get('gh_ok'), f"최신 릴리스: {d.get('gh_tag') or '없음'}"))
        st.write("- 로컬:", _badge(local_ok, "인덱스/ready 파일 상태"))

    # 3) 신규 자료 감지(Drive/Manifest diff)
    with st.container(border=True):
        st.markdown("### 신규 자료 감지")
        added = changed = removed = 0
        details = {"added": [], "changed": [], "removed": []}
        if callable(diff_with_manifest):
            try:
                d = diff_with_manifest(folder_id=None) or {}
                stats = d.get("stats") or {}
                added = int(stats.get("added",0)); changed = int(stats.get("changed",0)); removed = int(stats.get("removed",0))
                details["added"]   = d.get("added") or []
                details["changed"] = d.get("changed") or []
                details["removed"] = d.get("removed") or []
            except Exception as e:
                _add_error(e)
        st.write(f"새 항목: **{added}** · 변경: **{changed}** · 삭제: **{removed}**")
        for label, arr in (("신규", details["added"]), ("변경", details["changed"]), ("삭제", details["removed"])):
            if arr:
                with st.expander(f"{label} {len(arr)}개 보기"):
                    for x in arr: st.write("•", x)

        has_new = (added + changed + removed) > 0
        if has_new:
            st.info("📢 신규/변경 자료가 감지되었습니다. 어떻게 할까요?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes — 업데이트 진행 (재인덱싱)", use_container_width=True, type="primary"):
                    if callable(build_index_with_checkpoint):
                        try:
                            with st.spinner("업데이트 중…(재인덱싱)"):
                                res = build_index_with_checkpoint(force=False, prefer_release_restore=False, folder_id=_find_folder_id(None) if callable(_find_folder_id) else None)
                            if isinstance(res, dict) and res.get("ok"):
                                _ready_mark(p)
                                st.success("✅ 업데이트 완료(재인덱싱)")
                            else:
                                st.error("업데이트가 완료되지 않았습니다.")
                        except Exception as e:
                            _add_error(e); st.error("업데이트 중 오류가 발생했습니다.")
                    else:
                        st.error("build_index_with_checkpoint 사용 불가(임포트 실패)")
            with c2:
                if st.button("No — 최신 릴리스에서 복원", use_container_width=True):
                    if callable(restore_latest):
                        try:
                            with st.spinner("최신 릴리스에서 복원 중…"):
                                ok = bool(restore_latest(dest_dir=p))
                            if ok:
                                _ready_mark(p)
                                st.success("✅ 최신 릴리스에서 복원 완료")
                            else:
                                st.error("복원에 실패했습니다.")
                        except Exception as e:
                            _add_error(e); st.error("복원 중 오류가 발생했습니다.")
                    else:
                        st.error("restore_latest 사용 불가(임포트 실패)")
        else:
            st.success("변경 사항이 없습니다. (최신 상태)")

    # 4) 수동 인덱싱
    with st.container(border=True):
        st.markdown("### 수동 인덱싱")
        if st.button("로컬에서 강제 인덱싱", use_container_width=True):
            if callable(build_index_with_checkpoint):
                try:
                    with st.spinner("로컬 인덱싱 중…"):
                        res = build_index_with_checkpoint(force=True, prefer_release_restore=False, folder_id=_find_folder_id(None) if callable(_find_folder_id) else None)
                    if isinstance(res, dict) and res.get("ok"):
                        _ready_mark(p)
                        st.success("✅ 인덱싱 완료")
                    else:
                        st.error("인덱싱이 완료되지 않았습니다.")
                except Exception as e:
                    _add_error(e); st.error("인덱싱 중 오류가 발생했습니다.")
            else:
                st.error("build_index_with_checkpoint 사용 불가(임포트 실패)")

    # 5) 에러/로그 카드
    with st.container(border=True):
        st.markdown("### 에러/로그")
        txt = _errors_text()
        st.text_area("최근 오류", value=txt, height=160)
        st.download_button("오류 로그 다운로드", data=txt.encode("utf-8"), file_name="orchestrator_errors.txt")
# ============ render_index_orchestrator_panel — END ============
