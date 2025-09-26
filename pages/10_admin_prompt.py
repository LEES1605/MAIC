# [F4] START: FILE pages/10_admin_prompt.py — wrapper to real admin prompt
from __future__ import annotations
import streamlit as st

# 기본 Pages 네비 숨김(보조)
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

from src.ui.admin_prompt import main as _render  # 실제 구현 호출
_render()
# [F4] END
