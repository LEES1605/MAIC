# ===== [01] APP BOOT & ENV ===================================================
from __future__ import annotations

import os
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_RUN_ON_SAVE"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION"] = "false"

# ===== [02] IMPORTS ==========================================================
from pathlib import Path
from typing import Any, Optional, Callable

import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None  # type: ignore
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

# 인덱스 빌더/사전점검 (PREPARED→청크→리포트→ZIP 업로드)
try:
    from src.rag.index_build import precheck_build_needed, build_index_with_checkpoint
except Exception:
    precheck_build_needed = None  # type: ignore
    build_index_with_checkpoint = None  # type: ignore

# ===== [03] SESSION & HELPERS ================================================
st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태를 세션에 보관 (없으면 None)
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None  # _Index 객체 또는 None

def _index_ready() -> bool:
    return st.session_state.get("rag_index") is not None

def _index_status_badge() -> None:
    """창고 상태 표시: 준비/없음."""
    if _index_ready():
        st.caption("Index status: ✅ ready")
    else:
        st.caption("Index status: ❌ missing (빌드 또는 복구 필요)")

def _attach_from_local() -> bool:
    """로컬(or in-memory) 인덱스 연결 시도 → 성공 시 세션에 저장."""
    if get_or_build_index is None:
        return False
    try:
        idx = get_or_build_index()
        st.session_state["rag_index"] = idx
        return True
    except LocalIndexMissing:
        return False
    except Exception:
        return False

def _auto_attach_or_restore_silently() -> bool:
    """
    조용히 두뇌 연결 시도.
    - 로컬(또는 in-memory) 인덱스가 있으면 연결
    - 없으면 False(이 앱 버전은 자동 복구 대신 명시적 빌드를 권장)
    """
    return _attach_from_local()

# ===== [04] HEADER ===========================================================
st.title("🧑‍🏫 AI Teacher — Clean Scaffold")
_index_status_badge()
st.divider()

# ===== [05] RAG: Build/Restore Panels =======================================
def render_brain_prep_main():
    st.markdown("### 🧠 강의 준비")
    c1, c2 = st.columns([0.4, 0.6])

    # -------------------- 좌측: 두뇌 연결/초기화 -----------------------------
    with c1:
        if st.button("🧠 AI 두뇌 준비(복구/연결)", type="primary", key="btn_attach_restore"):
            ok = _auto_attach_or_restore_silently()
            if ok:
                st.success("두뇌 연결이 완료되었습니다.")
                st.rerun()
            else:
                st.error("두뇌 연결에 실패했습니다. 먼저 ‘사전점검→재최적화’를 실행해 인덱스를 만들어 주세요.")

        if st.button("📥 강의 자료 다시 불러오기 (두뇌 초기화)", key="btn_reset_local"):
            try:
                # 로컬 저장 디렉터리(이 스캐폴드는 기본 ~/.maic/persist)를 비우고 세션 해제
                base = Path.home() / ".maic"
                persist = base / "persist"
                if persist.exists():
                    import shutil
                    shutil.rmtree(persist)
                if "rag_index" in st.session_state:
                    st.session_state["rag_index"] = None
                st.success("두뇌 파일이 초기화되었습니다. ‘AI 두뇌 준비’를 다시 눌러 연결해 주세요.")
            except Exception as e:
                st.error(f"초기화 중 오류가 발생했습니다: {type(e).__name__}")
                st.exception(e)

    # -------------------- 우측: 사전점검 → 재최적화 --------------------------
    with c2:
        st.markdown("#### ⚙️ 인덱스 최적화 — **사전점검 후 실행**")
        st.caption(
            "‘사전점검’은 드라이브의 prepared 폴더 **메타데이터만** 빠르게 비교합니다. "
            "변경이 없으면 즉시 재최적화하지 않고, 원할 때만 2차 버튼으로 강제 실행합니다."
        )

        # 1) 사전점검
        if st.button("🔎 사전점검 (변경 여부 확인)", key="btn_precheck"):
            if precheck_build_needed is None:
                st.error("사전점검 모듈을 찾지 못했습니다. (src.rag.index_build)")
            else:
                try:
                    res = precheck_build_needed("")  # 시크릿의 PREPARED ID 자동 사용
                    st.session_state["_precheck_res"] = res
                    st.success("사전점검이 완료되었습니다.")
                except Exception as e:
                    st.session_state.pop("_precheck_res", None)
                    st.error(f"사전점검 실패: {type(e).__name__}: {e}")

        pre = st.session_state.get("_precheck_res")

        if pre:
            # 요약 배지
            cA, cB, cC, cD = st.columns(4)
            cA.metric("총 파일", pre.get("total_files", 0))
            cB.metric("신규", pre.get("new_docs", 0))
            cC.metric("변경", pre.get("updated_docs", 0))
            cD.metric("변경 없음", pre.get("unchanged_docs", 0))

            # 상세 표(있을 때만)
            if pre.get("new"):
                with st.expander("🆕 신규 문서 목록", expanded=False):
                    st.table(pre["new"])
            if pre.get("updated"):
                with st.expander("✏️ 변경 문서 목록", expanded=False):
                    st.table(pre["updated"])

            # 재최적화 버튼 라벨/설명 결정
            would = bool(pre.get("would_rebuild"))
            if not would:
                st.info("변경 사항이 없습니다. 재최적화가 꼭 필요하지 않다면 이 단계에서 멈춰도 됩니다.")
                run_label = "⚠️ 그래도 재최적화 실행"
                run_help  = "변경이 없어도 강제로 다시 청크/ZIP을 생성합니다."
            else:
                run_label = "🛠 재최적화 실행 (변경 반영)"
                run_help  = "변경/신규 파일만 델타로 반영하여 인덱스를 갱신합니다."

            # 2) 재최적화 실행 버튼
            if st.button(run_label, help=run_help, key="btn_build_confirm"):
                if build_index_with_checkpoint is None:
                    st.error("인덱스 빌더 모듈을 찾지 못했습니다. (src.rag.index_build)")
                else:
                    prog = st.progress(0)
                    log = st.empty()

                    def _pct(v: int, msg: str | None = None):
                        prog.progress(max(0, min(int(v), 100)))
                        if msg:
                            log.info(str(msg))

                    def _msg(s: str):
                        log.write(f"• {s}")

                    try:
                        with st.spinner("인덱스를 최적화(빌드)하는 중…"):
                            # PREPARED/BACKUP ID는 index_build 내부에서 시크릿으로 자동 탐지
                            res = build_index_with_checkpoint(
                                update_pct=_pct,
                                update_msg=_msg,
                                gdrive_folder_id="",     # ← 자동 탐지 사용
                                gcp_creds={},            # 미사용
                                persist_dir="",          # 내부 기본 사용
                                remote_manifest={},      # 미사용
                            )
                        prog.progress(100)
                        st.success("최적화가 완료되었습니다.")
                        st.json(res)

                        # 완료 후 두뇌 재연결
                        if _attach_from_local():
                            st.success("두뇌가 새 인덱스로 재연결되었습니다.")

                        # 새 결과를 반영하도록 사전점검 결과 초기화
                        st.session_state.pop("_precheck_res", None)

                    except Exception as e:
                        st.error(f"최적화 실패: {type(e).__name__}: {e}")

        # 안내
        st.info(
            "- ‘AI 두뇌 준비’는 로컬 저장본이 있으면 연결하고, 없으면 Drive/in-memory에서 로드합니다.\n"
            "- ‘사전점검’은 빠르게 변경 여부만 확인합니다.\n"
            "- ‘재최적화 실행’은 변경이 있을 때만 권장합니다(변경 없음이면 2차 확인 버튼으로 표시)."
        )

# ===== [06] SIMPLE QA DEMO ===================================================
def render_simple_qa():
    st.markdown("### 💬 질문해 보세요 (간단 데모)")
    if not _index_ready():
        st.info("아직 두뇌가 준비되지 않았어요. 상단의 **AI 두뇌 준비** 또는 **사전점검→재최적화**를 먼저 실행해 주세요.")
        return
    q = st.text_input("질문 입력", placeholder="예: 현재완료 시제 설명해 줘", key="qa_q")
    k = st.slider("검색 결과 개수(top_k)", 1, 10, 5, key="qa_k")
    if st.button("검색", key="qa_go") and q.strip():
        try:
            qe = st.session_state["rag_index"].as_query_engine(top_k=k)  # _LocalQueryEngine
            r = qe.query(q)
            st.text(r.response)
            # 필요하면 카드/표 형태로 r.hits 를 그려도 됨
        except Exception as e:
            st.error(f"검색 실패: {type(e).__name__}: {e}")

# ===== [07] MAIN =============================================================
def main():
    render_brain_prep_main()
    st.divider()
    render_simple_qa()

if __name__ == "__main__":
    main()
