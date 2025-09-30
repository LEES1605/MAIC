# [F5] START: FILE pages/15_index_status.py — wrapper to real index status
from __future__ import annotations
import streamlit as st
st.markdown(
    """
    <style>
      [data-testid="stSidebarNav"],
      section[data-testid="stSidebarNav"],
      nav[data-testid="stSidebarNav"],
      div[data-testid="stSidebarNav"] { display:none !important; height:0 !important; overflow:hidden !important; }
    </style>
    """, unsafe_allow_html=True
)

try:
    from src.ui.widgets.index_status import render_index_status_panel
    from src.core.persist import effective_persist_dir
    
    st.header("관리자: 인덱스 상태")
    persist_dir = effective_persist_dir()
    render_index_status_panel(dest_dir=persist_dir)
except Exception as e:
    st.header("관리자: 인덱스 상태")
    st.error(f"index_status 모듈 로드 실패: {e}")
    import traceback
    st.code(traceback.format_exc())
# [F5] END
