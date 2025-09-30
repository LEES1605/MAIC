# =============================== [01] future import — START ===========================
from __future__ import annotations
# ================================ [01] future import — END ============================

# =============================== [02] module imports — START ==========================
from typing import Any, Dict, List, Optional
import time
import json
import sys
try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore[assignment]

from src.services.index_state import render_index_steps
from src.services.index_actions import (
    persist_dir_safe as _persist_dir_safe,
    make_index_backup_zip,
    upload_index_backup,
    run_admin_index_job,
)

# 내부 동적 로더(앱 도우미 접근)
def _resolve_app_attr(name: str):
    try:
        app_mod = sys.modules.get("__main__")
        return getattr(app_mod, name, None)
    except Exception:
        return None

# prepared용 동적 API 로더
def _load_prepared_lister():
    try:
        from src.services.index_actions import _load_prepared_lister as _lp  # type: ignore[attr-defined]
        return _lp()
    except Exception:
        return None, []

def _load_prepared_api():
    try:
        from src.services.index_actions import _load_prepared_api as _la  # type: ignore[attr-defined]
        return _la()
    except Exception:
        return None, None, []
# ================================ [02] module imports — END ===========================

# =============================== [03] orchestrator header — START =====================
def render_orchestrator_header() -> None:
    if st is None:
        return

    # 공용 판정기(역호환 허용)
    try:
        from src.core.readiness import is_ready_text
    except Exception:
        def _norm(x: str | bytes | None) -> str:
            if x is None:
                return ""
            if isinstance(x, bytes):
                x = x.decode("utf-8", "ignore")
            return x.replace("\ufeff", "").strip().lower()
        def is_ready_text(x):  # type: ignore
            return _norm(x) in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}

    st.markdown("### 🧪 인덱스 오케스트레이터")
    persist = _persist_dir_safe()
    with st.container():
        st.caption("Persist Dir")
        st.code(str(persist), language="text")

    # 로컬 준비 상태 재계산(세션 키 보정)
    cj = persist / "chunks.jsonl"
    rf = persist / ".ready"
    try:
        ready_txt = rf.read_text(encoding="utf-8") if rf.exists() else ""
    except Exception:
        ready_txt = ""
    local_ready = cj.exists() and cj.stat().st_size > 0 and is_ready_text(ready_txt)
    st.session_state["_INDEX_LOCAL_READY"] = bool(local_ready)

    # 최신 여부(헤더 칩 결정용) — 앱 세션 플래그 사용
    is_latest = bool(st.session_state.get("_INDEX_IS_LATEST", False))
    latest_tag = st.session_state.get("_LATEST_RELEASE_TAG")

    # 칩 계산
    if is_latest:
        badge = "🟩 준비완료"
        badge_code = "READY"
        badge_desc = f"최신 릴리스 적용됨 (tag={latest_tag})" if latest_tag else "최신 릴리스 적용됨"
    elif local_ready:
        badge = "🟨 준비중(로컬 인덱스 감지)"
        badge_code = "MISSING"
        badge_desc = "로컬 인덱스는 있으나 최신 릴리스와 불일치 또는 미확인"
    else:
        badge = "🟧 없음"
        badge_code = "MISSING"
        badge_desc = "인덱스 없음"

    st.markdown(f"**상태**\n\n{badge}")

    # 상단 글로벌 배지 동기화 (앱 함수가 있으면 사용)
    try:
        _set = _resolve_app_attr("_set_brain_status")
        if callable(_set):
            _set(badge_code, badge_desc, "index", attached=(badge_code == "READY"))
    except Exception:
        pass

    if bool(st.session_state.get("admin_mode", False)):
        cols = st.columns([1, 1, 2])
        if cols[0].button("⬇️ Release에서 최신 인덱스 복원", use_container_width=True):
            try:
                fn = _resolve_app_attr("_boot_auto_restore_index")
                if callable(fn):
                    fn()
                st.success("Release 복원을 시도했습니다. 상태를 확인하세요.")
            except Exception as e:
                st.error(f"복원 실행 실패: {e}")

        if cols[1].button("✅ 로컬 구조 검증", use_container_width=True):
            try:
                ok = local_ready
                rec = {
                    "result": "성공" if ok else "실패",
                    "chunk": str(cj),
                    "ready": ready_txt.strip() or "(없음)",
                    "persist": str(persist),
                    "latest_tag": latest_tag,
                    "is_latest": is_latest,
                    "ts": int(time.time()),
                }
                st.session_state["_LAST_RESTORE_CHECK"] = rec

                if ok:
                    st.success("검증 성공: chunks.jsonl 존재 & .ready 유효")
                else:
                    st.error("검증 실패: 산출물/ready 상태가 불일치")
            except Exception as e:
                st.error(f"검증 실행 실패: {e}")

        with st.expander("최근 검증/복원 기록", expanded=False):
            rec = st.session_state.get("_LAST_RESTORE_CHECK")
            st.json(rec or {"hint": "위의 복원/검증 버튼을 사용해 기록을 남길 수 있습니다."})

        with st.expander("ℹ️ 최신 릴리스/메타 정보", expanded=False):
            st.write({
                "latest_release_tag": latest_tag,
                "latest_release_id": st.session_state.get("_LATEST_RELEASE_ID"),
                "last_restore_meta": st.session_state.get("_LAST_RESTORE_META"),
                "is_latest": is_latest,
                "local_ready": local_ready,
            })

        try:
            _dbg = _resolve_app_attr("_render_release_candidates_debug")
            if callable(_dbg):
                _dbg()
        except Exception:
            pass

    st.info(
        "강제 인덱싱(HQ, 느림)·백업과 인덱싱 파일 미리보기는 **관리자 인덱싱 패널**에서 합니다. "
        "관리자 모드 진입 후 아래 섹션으로 이동하세요.",
        icon="ℹ️",
    )
    st.markdown("<span id='idx-admin-panel'></span>", unsafe_allow_html=True)
# ================================ [03] orchestrator header — END ======================

# =============================== [04] prepared scan — START ===========================
def render_prepared_scan_panel() -> None:
    if st is None or not bool(st.session_state.get("admin_mode", False)):
        return

    st.markdown("<h4>🔍 새 파일 스캔(인덱싱 없이)</h4>", unsafe_allow_html=True)

    c1, c2, _c3 = st.columns([1, 1, 2])
    act_scan = c1.button("🔍 스캔 실행", use_container_width=True)
    act_clear = c2.button("🧹 화면 지우기", use_container_width=True)

    if act_clear:
        st.session_state.pop("_PR_SCAN_RESULT", None)
        try:
            _sr = _resolve_app_attr("_safe_rerun")
            if callable(_sr):
                _sr("pr_scan_clear", ttl=1)
        except Exception:
            pass

    prev = st.session_state.get("_PR_SCAN_RESULT")
    if isinstance(prev, dict) and not act_scan:
        st.caption("이전에 실행한 스캔 결과:")
        st.json(prev)

    if not act_scan:
        return

    idx_persist = _persist_dir_safe()
    lister, dbg1 = _load_prepared_lister()
    files_list: List[Dict[str, Any]] = []
    if lister:
        try:
            files_list = lister() or []
        except Exception as e:
            st.error(f"prepared 목록 조회 실패: {e}")
    else:
        with st.expander("디버그(파일 나열 함수 로드 경로)"):
            st.write("\n".join(dbg1) or "(정보 없음)")

    chk, _mark, dbg2 = _load_prepared_api()
    info: Dict[str, Any] = {}
    new_files: List[str] = []
    if callable(chk):
        try:
            info = chk(idx_persist, files_list) or {}
        except TypeError:
            info = chk(idx_persist) or {}
        except Exception as e:
            st.error(f"스캔 실행 실패: {e}")
            info = {}
        try:
            new_files = list(info.get("files") or info.get("new") or [])
        except Exception:
            new_files = []
    else:
        with st.expander("디버그(소비 API 로드 경로)"):
            st.write("\n".join(dbg2) or "(정보 없음)")

    total_prepared = len(files_list)
    total_new = len(new_files)
    st.success(f"스캔 완료 · prepared 총 {total_prepared}건 · 새 파일 {total_new}건")

    if total_new:
        with st.expander("새 파일 미리보기(최대 50개)"):
            rows = []
            for rec in (new_files[:50] if isinstance(new_files, list) else []):
                if isinstance(rec, str):
                    rows.append({"name": rec})
                elif isinstance(rec, dict):
                    nm = str(rec.get("name") or rec.get("path") or rec.get("file") or "")
                    fid = str(rec.get("id") or rec.get("fileId") or "")
                    rows.append({"name": nm, "id": fid})
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.write("(표시할 항목이 없습니다.)")
    else:
        st.info("새 파일이 없습니다. 재인덱싱을 수행할 필요가 없습니다.")

    st.session_state["_PR_SCAN_RESULT"] = {
        "persist": str(idx_persist),
        "prepared_total": total_prepared,
        "new_total": total_new,
        "timestamp": int(time.time()),
        "sample_new": new_files[:10] if isinstance(new_files, list) else [],
    }
# ================================ [04] prepared scan — END ============================

# =============================== [05] indexing panel — START ==========================
def _consume_admin_index_request() -> None:
    """세션의 _IDX_REQ를 소비하여 인덱싱 잡을 실행한다."""
    if st is None:
        return
    try:
        req = st.session_state.pop("_IDX_REQ", None)
    except Exception:
        req = None
    if req:
        try:
            run_admin_index_job(req)
        except Exception as e:
            from src.services.index_state import log as _log
            _log(f"인덱싱 소비 실패: {e}", "err")


def render_index_panel() -> None:
    """관리자 인덱싱 패널 본문."""
    if st is None:
        return

    # 1) 렌더 초입: 요청 소비
    _consume_admin_index_request()

    st.markdown("### 🔧 관리자 인덱싱 패널 (prepared 전용)")

    # 2) 진행/상태 패널을 '먼저' 강제 생성
    try:
        render_index_steps()
    except Exception:
        pass

    # 3) 옵션/버튼 영역
    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        auto_zip = st.toggle("인덱싱 후 ZIP/Release 업로드", value=False, key="idx_auto_zip",
                             help="GH_TOKEN/GITHUB_REPO 필요")
    with colB:
        show_debug = st.toggle("디버그 로그 표시", value=True, key="idx_show_debug")
    with colC:
        if st.button("📤 인덱싱 산출물 업로드(Release)", use_container_width=True, key="idx_manual_upload"):
            try:
                used_persist = _persist_dir_safe()
                z = make_index_backup_zip(used_persist)
                msg = upload_index_backup(z, tag=f"index-{int(time.time())}")
                st.success(f"업로드 완료: {msg}")
            except Exception as e:
                st.error(f"업로드 실패: {e}")

    # 4) 강제 인덱싱 실행 버튼
    if st.button("🚀 강제 재인덱싱(HQ, prepared)", type="primary",
                 use_container_width=True, key="idx_run_btn"):
        try:
            st.session_state["_IDX_REQ"] = {"auto_up": bool(auto_zip), "debug": bool(show_debug)}
        except Exception:
            st.session_state["_IDX_REQ"] = {"auto_up": False}
        try:
            _sr = _resolve_app_attr("_safe_rerun")
            if callable(_sr):
                _sr("idx_run", ttl=0.3)
        except Exception:
            pass

    # 5) 마지막으로 한 번 더 진행/상태 렌더(있으면 갱신)
    try:
        render_index_steps()
    except Exception:
        pass
# ================================ [05] indexing panel — END ===========================

# =============================== [06] indexed sources — START =========================
def render_indexed_sources_panel() -> None:
    if st is None or not bool(st.session_state.get("admin_mode", False)):
        return

    chunks_path = _persist_dir_safe() / "chunks.jsonl"
    with st.container(border=True):
        st.subheader("📄 인덱싱된 파일 목록 (읽기 전용)")
        st.caption(f"경로: `{str(chunks_path)}`")

        if not chunks_path.exists():
            st.info("아직 인덱스가 없습니다. 먼저 인덱싱을 수행해 주세요.")
            return

        docs: Dict[str, Dict[str, Any]] = {}
        total_lines = 0
        parse_errors = 0
        try:
            with chunks_path.open("r", encoding="utf-8") as rf:
                for line in rf:
                    s = line.strip()
                    if not s:
                        continue
                    total_lines += 1
                    try:
                        obj = json.loads(s)
                    except Exception:
                        parse_errors += 1
                        continue
                    doc_id = str(obj.get("doc_id") or obj.get("source") or "")
                    title = str(obj.get("title") or "")
                    source = str(obj.get("source") or "")
                    if not doc_id:
                        continue
                    row = docs.setdefault(
                        doc_id, {"doc_id": doc_id, "title": title, "source": source, "chunks": 0}
                    )
                    row["chunks"] += 1
        except Exception as e:
            try:
                _err = _resolve_app_attr("_errlog")
                if callable(_err):
                    _err(f"read chunks.jsonl failed: {e}", where="[indexed-sources.read]", exc=e)
            except Exception:
                pass
            st.error("인덱스 파일을 읽는 중 오류가 발생했어요.")
            return

        rows2 = [
            {"title": r["title"], "path": r["source"], "doc_id": r["doc_id"], "chunks": r["chunks"]}
            for r in docs.values()
        ]
        st.caption(
            f"총 청크 수: {total_lines} · 문서 수: {len(rows2)} (파싱오류 {parse_errors}건)"
        )
        st.dataframe(rows2, hide_index=True, use_container_width=True)
# ================================ [06] indexed sources — END ==========================
