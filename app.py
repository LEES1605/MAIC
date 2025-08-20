# ===== [01] APP BOOT =========================================================
from __future__ import annotations

import streamlit as st

# RAG 엔진이 없어도 앱이 죽지 않게 try/except로 감쌈
try:
    from src.rag_engine import get_or_build_index, LocalIndexMissing
except Exception:
    get_or_build_index = None
    class LocalIndexMissing(Exception):  # 안전 가드
        ...

st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

# 인덱스 상태를 세션에 보관 (없으면 None)
if "rag_index" not in st.session_state:
    st.session_state["rag_index"] = None

def _index_status_badge() -> None:
    """창고 상태 표시: 준비/없음."""
    if st.session_state["rag_index"] is None:
        st.caption("Index status: ❌ missing (빌드 또는 복구 필요)")
    else:
        st.caption("Index status: ✅ ready")

st.title("🧑‍🏫 AI Teacher — Clean Scaffold")
_index_status_badge()

# 버튼을 눌렀을 때만 로드/빌드 시도 (없으면 크래시 대신 안내)
if st.button("Build/Load Index"):
    with st.spinner("Loading / building local index…"):
        if get_or_build_index is None:
            st.warning("RAG 엔진이 아직 준비되지 않았어요.")
        else:
            try:
                idx = get_or_build_index()              # ← 여기서 없으면 예외 발생
                st.session_state["rag_index"] = idx     # 준비 완료 상태로 저장
                st.success("Index ready.")
            except LocalIndexMissing:
                # 창고가 비어 있으면 여기로 떨어짐 — 크래시 대신 안내만.
                st.info("아직 로컬 인덱스가 없습니다. 백업 복구 또는 인덱스 빌드를 먼저 실행해 주세요.")
            except Exception as e:
                st.error(f"Index load/build failed: {type(e).__name__}: {e}")
# ===== [02] END ==============================================================
