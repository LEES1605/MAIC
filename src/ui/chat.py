# [04] START: FILE src/ui/chat.py — minimal chat skeleton using sider
from __future__ import annotations
import streamlit as st
from src.ui.utils.sider import render_sidebar

def main() -> None:
    render_sidebar()
    st.header("LEES AI Teacher")
    st.subheader("질문")
    c1, c2 = st.columns([9, 1])
    with c1:
        q = st.text_input("질문을 입력하세요...", key="chat_input", label_visibility="collapsed")
    with c2:
        send = st.button("➤", use_container_width=True)
    if send and q.strip():
        st.write(f"**질문:** {q.strip()}")
        st.write("**답변:** 준비 중입니다... (스트리밍 연결 전 임시)")

if __name__ == "__main__":
    main()
# [04] END: FILE src/ui/chat.py
