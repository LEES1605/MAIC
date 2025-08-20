# ===== [01] APP BOOT =========================================================
from __future__ import annotations
import streamlit as st
from src.rag_engine import get_or_build_index

st.set_page_config(page_title="AI Teacher (Clean)", layout="wide")

st.title("🧑‍🏫 AI Teacher — Clean Scaffold")
if st.button("Build/Load Index"):
    st.write("Pretending to build…")
    idx = get_or_build_index()
    st.success("Index ready (stub).")
# ===== [02] END ==============================================================
