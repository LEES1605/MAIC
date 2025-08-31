# ===== ui_orchestrator.py — START ===========================================
from __future__ import annotations
import os, json, io, textwrap, traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import streamlit as st

# ── 내부 지연 임포트 헬퍼 ─────────────────────────────────────────────────────
def _lazy_imports():
    """무거운 의존성은 패널 내부에서만 지연 임포트."""
    out: Dict[str, Any] = {}
    try:
        # RAG / Index
        rag = __import__("src.rag.index_build", fromlist=[
            "_drive_client","_find_folder_id",
            "build_index_with_checkpoint","scan_drive_listing",
            "diff_with_manifest","PERSIST_DIR"
        ])
        out.update({
            "_drive_client": getattr(rag, "_drive_client", None),
            "_find_folder_id": getattr(rag, "_find_folder_id", None),
            "build_index_with_checkpoint": getattr(rag, "build_index_with_checkpoint", None),
            "scan_drive_listing": getattr(rag, "scan_drive_listing", None),
            "diff_with_manifest": getattr(rag, "diff_with_manifest", None),
            "PERSIST_DIR": getattr(rag, "PERSIST_DIR", None),
        })
    except Exception as e:
        out["__err_rag__"] = e

    try:
        # GitHub Release
        gh = __import__("src.backup.github_release", fromlist=[
            "get_latest_release","fetch_manifest_from_release","restore_latest"
        ])
        out.update({
            "get_latest_release": getattr(gh, "get_latest_release", None),
            "fetch_manifest_from_release": getattr(gh, "fetch_manifest_from_release", None),
            "restore_latest": getattr(gh, "restore_latest", None),
        })
    except Exception as e:
        out["__err_gh__"] = e

    return out

# ── 공용 유틸 ────────────────────────────────────────────────────────────────
def _badge(ok: Optional[bool], label: str) -> str:
    if ok is True:  return f"✅ {label}"
    if ok is False: return f"❌ {label}"
    return f"— {label}"

def _add_error(e: BaseException) -> None:
    msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    errs: List[str] = st.session_state.get("_orchestrator_errors", [])
    errs.append(msg)
    st.session_state["_orchestrator_errors"] = errs

def _errors_text() -> str:
    errs: List[str] = st.session_state.get("_orchestrator_errors", [])
    return "\n\n".join(errs) if errs else "No errors."

def _ready_mark(persist_dir: Path) -> None:
    try: (persist_dir / ".ready").write_text("ok", encoding="utf-8")
    except Exception: pass

# ── 메인 패널 ────────────────────────────────────────────────────────────────
def render_index_orchestrator_panel() -> None:
    st.markdown("## 🧠 인덱스 오케스트레이터")

    # 1) 의존성 지연 임포트
    deps = _lazy_imports()
    if "__err_rag__" in deps:
        _add_error(deps["__err_rag__"])
    if "__err_gh__" in deps:
        _add_error(deps["__err_gh__"])

    _drive_client               = deps.get("_drive_client")
    _find_folder_id             = deps.get("_find_folder_id")
    build_index_with_checkpoint = deps.get("build_index_with_checkpoint")
    scan_drive_listing          = deps.get("scan_drive_listing")
    diff_with_manifest          = deps.get("diff_with_manifest")
    PERSIST_DIR                 = deps.get("PERSIST_DIR") or (Path.home() / ".maic" / "persist")
    get_latest_release          = deps.get("get_latest_release")
    fetch_manifest_from_release = deps.get("fetch_manifest_from_release")
    restore_latest              = deps.get("restore_latest")

    # 상태 컨테이너
    with st.container(border=True):
        st.markdown("### 상태/진단")
        svc = None
        drive_ok = False
        drive_email = None
        gh_ok = False
        gh_latest = None

        # Drive 연결(가벼운 about 호출)
        if callable(_drive_client):
            try:
                svc = _drive_client()
                about = svc.about().get(fields="user").execute()
                drive_email = (about or {}).get("user", {}).get("emailAddress")
                drive_ok = True
            except Exception as e:
                _add_error(e); drive_ok = False
        else:
            st.caption("⚠️ _drive_client 사용 불가(임포트 실패)")

        st.write("- Drive:", _badge(drive_ok, f"연결" + (f"(`{drive_email}`)" if drive_email else "")))

        # GitHub 최신 릴리스
        try:
            gh_latest = get_latest_release() if callable(get_latest_release) else None
            gh_ok = gh_latest is not None
        except Exception as e:
            _add_error(e); gh_ok = False
        tag = gh_latest.get("tag_name") if gh_latest else None
        st.write("- GitHub:", _badge(gh_ok, f"최신 릴리스: {tag or '없음'}"))

        # 로컬 준비 상태
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
                # 기존 인터페이스 유지: 환경변수/시크릿 → fallback 이름
                prepared_id = _find_folder_id("PREPARED", fallback=os.getenv("GDRIVE_PREPARED_FOLDER_ID", "prepared"))
            except Exception as e:
                _add_error(e)

        colA, colB = st.columns([0.55, 0.45])

        # Drive 스냅샷
        snapshot: List[Dict[str, Any]] = []
        with colA:
            if drive_ok and prepared_id and callable(scan_drive_listing):
                try:
                    snapshot = scan_drive_listing(svc, prepared_id)
                    st.success(f"Drive 스냅샷 완료: {len(snapshot)} 파일")
                except Exception as e:
                    _add_error(e); st.error("Drive 스냅샷 실패")
            else:
                st.info("Drive 연결 불가 또는 폴더 ID/함수 누락")

        # 최신 릴리스 manifest
        latest_manifest: Dict[str, Any] = {}
        with colB:
            if gh_ok and gh_latest and callable(fetch_manifest_from_release):
                try:
                    latest_manifest = fetch_manifest_from_release(gh_latest) or {}
                    docs = latest_manifest.get("docs", []) or []
                    st.success(f"최신 릴리스 manifest 로드: {len(docs)} 문서")
                except Exception as e:
                    _add_error(e); st.error("릴리스 manifest 로드 실패")
            else:
                st.info("최신 릴리스가 없거나 함수 누락")

        # 델타 요약
        diff = {"added": [], "changed": [], "removed": []}
        if callable(diff_with_manifest):
            try:
                diff = diff_with_manifest(snapshot, latest_manifest.get("docs", []) if latest_manifest else [])
            except Exception as e:
                _add_error(e)
        added, changed, removed = map(len, (diff["added"], diff["changed"], diff["removed"]))
        st.write(f"- 변경 요약: 추가 {added}, 변경 {changed}, 삭제 {removed}")

        # 변경 상세(최대 20개)
        with st.expander("변경 상세 보기(최대 20개)", expanded=False):
            def _lines(items: List[Dict[str, Any]], label: str):
                st.caption(f"{label}: {len(items)}")
                for it in items[:20]:
                    st.write(f"• {it.get('name')} ({it.get('id')})")
            _lines(diff["added"],   "추가")
            _lines(diff["changed"], "변경")
            _lines(diff["removed"], "삭제")

        # 의사결정
        has_new = (added + changed + removed) > 0
        if has_new:
            st.info("📢 신규/변경 자료가 감지되었습니다. 어떻게 할까요?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes — 업데이트 진행 (인덱싱→릴리스→로컬백업)", use_container_width=True, type="primary"):
                    if callable(build_index_with_checkpoint):
                        try:
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
                    if callable(restore_latest):
                        try:
                            ok = restore_latest(dest_dir=Path(PERSIST_DIR))
                            if ok:
                                _ready_mark(Path(PERSIST_DIR))
                                st.success("✅ 최신 릴리스에서 복원 완료")
                            else:
                                st.error("복원 실패: 릴리스 또는 자산이 없습니다.")
                        except Exception as e:
                            _add_error(e); st.error("복원 중 오류가 발생했습니다.")
                    else:
                        st.error("restore_latest 사용 불가(임포트 실패)")
        else:
            st.success("🔎 신규/변경 없음 → 최신 릴리스에서 로컬 복원을 권장합니다.")
            if st.button("최신 릴리스에서 복원", use_container_width=True):
                if callable(restore_latest):
                    try:
                        ok = restore_latest(dest_dir=Path(PERSIST_DIR))
                        if ok:
                            _ready_mark(Path(PERSIST_DIR))
                            st.success("✅ 최신 릴리스에서 복원 완료")
                        else:
                            st.error("복원 실패: 릴리스 또는 자산이 없습니다.")
                    except Exception as e:
                        _add_error(e); st.error("복원 중 오류가 발생했습니다.")
                else:
                    st.error("restore_latest 사용 불가(임포트 실패)")

    # 3) Full 인덱싱
    with st.container(border=True):
        st.markdown("### Full 인덱싱")
        st.caption("전체 다시 인덱싱 → GitHub Release 업로드 → 로컬 백업")
        if st.button("🔄 전체 다시 인덱싱", use_container_width=True):
            if callable(build_index_with_checkpoint):
                try:
                    res = build_index_with_checkpoint(
                        update_pct=lambda v, m=None: None,
                        update_msg=lambda s: st.write(s),
                        gdrive_folder_id=( _find_folder_id("PREPARED", fallback=os.getenv("GDRIVE_PREPARED_FOLDER_ID", "prepared")) if callable(_find_folder_id) else "prepared"),
                        gcp_creds={}, persist_dir=str(PERSIST_DIR),
                        remote_manifest={}, should_stop=None
                    )
                    if isinstance(res, dict) and res.get("ok"):
                        _ready_mark(Path(PERSIST_DIR))
                        st.success("✅ Full 인덱싱 완료(릴리스 업로드 및 로컬 백업 포함)")
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
# ===== ui_orchestrator.py — END =============================================
