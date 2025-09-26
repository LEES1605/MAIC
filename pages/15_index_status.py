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
    from src.ui.index_status import main as _render
    _render()
except Exception:
    st.header("관리자: 인덱스 상태")
    st.info("index_status 모듈을 찾지 못했습니다.")
# [F5] END
