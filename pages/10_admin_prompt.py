# [H5] START: FILE pages/10_admin_prompt.py — wrapper to real admin prompt
from __future__ import annotations
import streamlit as st

# 기본 “Pages” 네비 숨김 (버전별 testid 변형 모두 차단)

st.markdown(
    """
    <style>
      [data-testid="stSidebarNav"],
      section[data-testid="stSidebarNav"],
      nav[data-testid="stSidebarNav"],
      div[data-testid="stSidebarNav"] { display:none !important; height:0 !important; overflow:hidden !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

from src.ui.admin_prompt import main as _render
_render()
# [H5] END