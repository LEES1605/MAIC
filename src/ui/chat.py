# [CHAT-OPT] START: FILE src/ui/chat.py — no-op by default; optional skeleton
from __future__ import annotations
import os
import streamlit as st

try:
    from src.ui.utils.sider import render_sidebar
except Exception:
    from .utils.sider import render_sidebar

def main() -> None:
    render_sidebar()
    # 기본: 아무 것도 렌더하지 않음(중복 방지)
    use_skeleton = (
        os.environ.get("MAIC_CHAT_SKELETON") == "1"
        or bool(st.session_state.get("_USE_CHAT_SKELETON"))
    )
    if not use_skeleton:
        return

    # (옵션) 임시 스켈레톤 UI
    st.header("LEES AI Teacher")
    st.subheader("질문")
    c1, c2 = st.columns([9, 1])
    with c1:
        q = st.text_input("질문을 입력하세요...", key="chat_input__skeleton", label_visibility="collapsed")
    with c2:
        send = st.button("➤", key="chat_send__skeleton", use_container_width=True)
    if send and q.strip():
        st.write(f"**질문:** {q.strip()}")
        st.write("**답변:** 준비 중입니다… (스켈레톤)")

if __name__ == "__main__":
    main()
# [CHAT-OPT] END
