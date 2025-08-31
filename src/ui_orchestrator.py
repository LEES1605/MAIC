# ======================== [00] orchestrator helpers — START ========================
import importlib, traceback
from pathlib import Path

def _add_error(e) -> None:
    try:
        import streamlit as st
        lst = st.session_state.setdefault("_orchestrator_errors", [])
        lst.append("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        if len(lst) > 50:
            del lst[:-50]
    except Exception:
        pass

def _errors_text() -> str:
    try:
        import streamlit as st
        lst = st.session_state.get("_orchestrator_errors") or []
        return "\n\n".join(lst) if lst else "—"
    except Exception:
        return "—"

def _ready_mark(persist_dir: Path) -> None:
    try:
        persist_dir.mkdir(parents=True, exist_ok=True)
        (persist_dir / ".ready").write_text("ready", encoding="utf-8")
    except Exception as e:
        _add_error(e)

def _lazy_imports() -> dict:
    def _imp(name):
        try: return importlib.import_module(name)
        except Exception: return None

    deps = {}

    # config → PERSIST_DIR
    for m in ("src.config", "config"):
        mod = _imp(m)
        if mod and hasattr(mod, "PERSIST_DIR"):
            deps["PERSIST_DIR"] = getattr(mod, "PERSIST_DIR")
            break

    # GitHub release / manifest
    for m in ("src.release", "release", "src.tools.release", "src.utils.release"):
        mod = _imp(m)
        if not mod: continue
        deps.setdefault("get_latest_release", getattr(mod, "get_latest_release", None))
        deps.setdefault("fetch_manifest_from_release", getattr(mod, "fetch_manifest_from_release", None))
        deps.setdefault("restore_latest", getattr(mod, "restore_latest", None))
        if all(deps.get(k) for k in ("get_latest_release","fetch_manifest_from_release","restore_latest")):
            break

    # Google Drive
    for m in ("src.drive", "drive", "src.gdrive", "gdrive", "src.google_drive", "google_drive"):
        mod = _imp(m)
        if not mod: continue
        deps.setdefault("_drive_client",
            getattr(mod, "_drive_client", None) or getattr(mod, "drive_client", None) or getattr(mod, "client", None))
        deps.setdefault("_find_folder_id",
            getattr(mod, "_find_folder_id", None) or getattr(mod, "find_folder_id", None))
        deps.setdefault("scan_drive_listing",
            getattr(mod, "scan_drive_listing", None) or getattr(mod, "scan_listing", None))
        if all(deps.get(k) for k in ("_drive_client","_find_folder_id","scan_drive_listing")):
            break

    # Indexer
    for m in ("src.index_build", "index_build", "src.rag.index_build", "src.rag.indexer", "src.rag.build"):
        mod = _imp(m)
        if not mod: continue
        deps.setdefault("build_index_with_checkpoint",
            getattr(mod, "build_index_with_checkpoint", None) or getattr(mod, "build_index", None))
        if deps.get("build_index_with_checkpoint"):
            break

    # diff util
    for m in ("src.manifest", "manifest", "src.release", "release", "src.utils.manifest", "src.utils"):
        mod = _imp(m)
        if not mod: continue
        for cand in ("diff_with_manifest", "diff_listing_with_manifest", "diff_manifest"):
            fn = getattr(mod, cand, None)
            if callable(fn):
                deps["diff_with_manifest"] = fn
                break
        if deps.get("diff_with_manifest"):
            break

    return deps
# ========================= [00] orchestrator helpers — END =========================
# =========== render_index_orchestrator_panel — START ===========
def render_index_orchestrator_panel() -> None:
    """
    관리자 진단 도구 패널(네트워크 호출 지연 + 버튼 클릭 시 실행)
    - 패널을 열어도 즉시 네트워크에 접근하지 않습니다.
    - "진단 실행" 버튼 클릭 시에만 Drive/GitHub 상태를 점검합니다.
    - 버튼 실행 중에는 spinner를 표시합니다.
    """
    import time
    import streamlit as st
    from pathlib import Path

    st.markdown("## 🧠 인덱스 진단 도구")  # ← 헤더만 교체 (기존: 인덱스 오케스트레이터)

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
    ss.setdefault("_orch_diag", {})
    ss.setdefault("_orchestrator_errors", [])

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

        # 결과 표시
        d = ss.get("_orch_diag") or {}
        def _badge(ok: bool|None, label: str) -> str:
            if ok is True:  return f"✅ {label}"
            if ok is False: return f"❌ {label}"
            return f"— {label}"
        if PERSIST_DIR:
            from pathlib import Path
            chunks = Path(PERSIST_DIR) / "chunks.jsonl"
            ready  = Path(PERSIST_DIR) / ".ready"
            local_ok = chunks.exists() and ready.exists()
        else:
            local_ok = None
        st.write("- Drive:", _badge(d.get('drive_ok'), f"연결" + (f"(`{d.get('drive_email')}`)" if d.get('drive_email') else "")))
        st.write("- GitHub:", _badge(d.get('gh_ok'), f"최신 릴리스: {d.get('gh_tag') or '없음'}"))
        st.write("- 로컬:", _badge(local_ok, "인덱스/ready 파일 상태"))

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
# ============ render_index_orchestrator_panel — END ============
