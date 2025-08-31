# ===== 교체 대상: src/ui_orchestrator.py L66–L267 =====
# ===================== render_index_orchestrator_panel — START =====================
def render_index_orchestrator_panel() -> None:
    """
    관리자 오케스트레이터 패널(네트워크 호출 지연 + 버튼 클릭 시 실행)
    - 패널을 열어도 즉시 네트워크에 접근하지 않습니다.
    - "진단 실행" 버튼 클릭 시에만 Drive/GitHub 상태를 점검합니다.
    - 버튼 실행 중에는 spinner를 표시합니다.
    """
    import time
    import streamlit as st
    from pathlib import Path

    st.markdown("## 🧠 인덱스 오케스트레이터")

    # 1) 의존성 지연 임포트
    deps = _lazy_imports()
    get_latest_release = deps.get("get_latest_release")
    fetch_manifest_from_release = deps.get("fetch_manifest_from_release")
    restore_latest = deps.get("restore_latest")
    _drive_client = deps.get("_drive_client")
    _find_folder_id = deps.get("_find_folder_id")
    build_index_with_checkpoint = deps.get("build_index_with_checkpoint")
    scan_drive_listing = deps.get("scan_drive_listing")
    diff_with_manifest = deps.get("diff_with_manifest")
    PERSIST_DIR = deps.get("PERSIST_DIR")

    # 내부 유틸
    def _lines(items, label):
        if not items:
            st.write(f"- {label}: 없음"); return
        with st.expander(f"{label} {len(items)}개 보기"):
            for x in items:
                st.write("•", x)

    # 결과 캐시
    ss = st.session_state
    ss.setdefault("_orch_diag", {})   # {"drive_ok":bool,"drive_email":str,"gh_ok":bool,"gh_tag":str, ...}
    ss.setdefault("_orchestrator_errors", [])   # 기존 에러 누적 키와 동일하게 사용

    # 1) 상태 점검(지연 실행)
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
            st.success("진단 결과를 초기화했습니다.")

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
                        gh_ok = gh_latest is not None
                        gh_tag = gh_latest.get("tag_name") if gh_latest else None
                    except Exception as e:
                        _add_error(e)
                ss["_orch_diag"] = {
                    "drive_ok": drive_ok, "drive_email": drive_email,
                    "gh_ok": gh_ok, "gh_tag": gh_tag,
                }
            st.success(f"진단 완료 ({(time.perf_counter()-t0)*1000:.0f} ms)")

        # 결과 표시(있으면)
        d = ss.get("_orch_diag") or {}
        def _badge(ok: bool|None, label: str) -> str:
            if ok is True:  return f"✅ {label}"
            if ok is False: return f"❌ {label}"
            return f"— {label}"
        st.write("- Drive:", _badge(d.get('drive_ok'), f"연결" + (f"(`{d.get('drive_email')}`)" if d.get('drive_email') else "")))
        st.write("- GitHub:", _badge(d.get('gh_ok'), f"최신 릴리스: {d.get('gh_tag') or '없음'}"))
        if PERSIST_DIR:
            chunks = Path(PERSIST_DIR) / "chunks.jsonl"
            ready  = Path(PERSIST_DIR) / ".ready"
            local_ok = chunks.exists() and ready.exists()
            st.write("- 로컬:", _badge(local_ok, f"인덱스 파일: {'있음' if chunks.exists() else '없음'} / .ready: {'있음' if ready.exists() else '없음'}"))
            st.caption(f"persist: `{Path(PERSIST_DIR).as_posix()}`")

    # 2) 신규 자료 감지(Drive/Release 비교)
    with st.container(border=True):
        st.markdown("### 신규 자료 감지")
        prepared_id = None
        if callable(_find_folder_id):
            try:
                prepared_id = _find_folder_id("prepared")
            except Exception as e:
                _add_error(e)

        added = changed = removed = 0
        diff = {}
        if callable(scan_drive_listing) and callable(diff_with_manifest) and callable(fetch_manifest_from_release):
            try:
                listing = scan_drive_listing(prepared_id or "prepared")
                manifest = fetch_manifest_from_release() or {}
                diff = diff_with_manifest(listing, manifest)
                added = len(diff.get("added", []))
                changed = len(diff.get("changed", []))
                removed = len(diff.get("removed", []))
            except Exception as e:
                _add_error(e)

        st.write(f"새 항목: **{added}** · 변경: **{changed}** · 삭제: **{removed}**")
        _lines(diff.get("added", []), "신규")
        _lines(diff.get("changed", []), "변경")
        _lines(diff.get("removed", []), "삭제")

        has_new = (added + changed + removed) > 0
        if has_new:
            st.info("📢 신규/변경 자료가 감지되었습니다. 어떻게 할까요?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes — 업데이트 진행 (인덱싱→릴리스→로컬백업)", use_container_width=True, type="primary"):
                    if callable(build_index_with_checkpoint) and PERSIST_DIR:
                        try:
                            with st.spinner("업데이트 중…(인덱싱/릴리스/로컬백업)"):
                                res = build_index_with_checkpoint(
                                    update_pct=lambda v, m=None: None,
                                    update_msg=lambda s: st.write(s),
                                    gdrive_folder_id=prepared_id or "prepared",
                                    gcp_creds={}, persist_dir=str(PERSIST_DIR),
                                    remote_manifest={}, should_stop=None
                                )
                            if isinstance(res, dict) and res.get("ok"):
                                _ready_mark(Path(PERSIST_DIR))
                                st.success("✅ 업데이트 완료(릴리스 업로드 및 로컬 백업 포함)")
                            else:
                                st.error("업데이트가 완료되지 않았습니다.")
                        except Exception as e:
                            _add_error(e); st.error("업데이트 중 오류가 발생했습니다.")
                    else:
                        st.error("build_index_with_checkpoint 사용 불가(임포트 실패)")
            with c2:
                if st.button("No — 최신 릴리스에서 복원", use_container_width=True):
                    if callable(restore_latest) and PERSIST_DIR:
                        try:
                            with st.spinner("최신 릴리스에서 복원 중…"):
                                ok = restore_latest(dest_dir=str(PERSIST_DIR))
                            if ok:
                                _ready_mark(Path(PERSIST_DIR))
                                st.success("✅ 최신 릴리스에서 복원 완료")
                            else:
                                st.error("복원에 실패했습니다.")
                        except Exception as e:
                            _add_error(e); st.error("복원 중 오류가 발생했습니다.")
                    else:
                        st.error("restore_latest 사용 불가(임포트 실패)")

        else:
            st.success("변경 사항이 없습니다. (최신 상태)")

    # 3) 수동 인덱싱
    with st.container(border=True):
        st.markdown("### 수동 인덱싱")
        if st.button("로컬에서 강제 인덱싱", use_container_width=True):
            if callable(build_index_with_checkpoint) and PERSIST_DIR:
                try:
                    with st.spinner("로컬 인덱싱 중…"):
                        res = build_index_with_checkpoint(
                            update_pct=lambda v, m=None: None,
                            update_msg=lambda s: st.write(s),
                            gdrive_folder_id=None, gcp_creds={},
                            persist_dir=str(PERSIST_DIR), remote_manifest={},
                            should_stop=None
                        )
                    if isinstance(res, dict) and res.get("ok"):
                        _ready_mark(Path(PERSIST_DIR))
                        st.success("✅ 인덱싱 완료")
                    else:
                        st.error("인덱싱이 완료되지 않았습니다.")
                except Exception as e:
                    _add_error(e); st.error("인덱싱 중 오류가 발생했습니다.")
            else:
                st.error("build_index_with_checkpoint 사용 불가(임포트 실패)")

    # 4) 에러/로그 카드
    with st.container(border=True):
        st.markdown("### 에러/로그")
        txt = _errors_text()
        st.text_area("최근 오류", value=txt, height=160)
        st.download_button("오류 로그 다운로드", data=txt.encode("utf-8"), file_name="orchestrator_errors.txt")
# ====================== render_index_orchestrator_panel — END ======================
