# [C-1] START: FILE src/ui/chat.py — no-op by default; optional skeleton
from __future__ import annotations
import os
import streamlit as st

# 진짜 사이드바(SSOT)
try:
    from src.ui.utils.sider import render_sidebar
except Exception:
    from .utils.sider import render_sidebar  # fallback for relative import

def main() -> None:
    # 사이드바만 일관 렌더
    render_sidebar()

    # ✅ 기본값: 아무 것도 렌더하지 않음(중복 방지).
    #    아래 플래그를 켠 경우에만 임시 스켈레톤 UI를 표시한다.
    use_skeleton = (
        os.environ.get("MAIC_CHAT_SKELETON") == "1"
        or bool(st.session_state.get("_USE_CHAT_SKELETON"))
    )
    if not use_skeleton:
        return

    # --- (옵션) 임시 스켈레톤 UI: 디버그/데모 용도 ------------------------------
    st.header("LEES AI Teacher")
    st.subheader("질문")
    c1, c2 = st.columns([9, 1])
    with c1:
        q = st.text_input(
            "질문을 입력하세요...",
            key="chat_input__skeleton",             # 충돌 방지용 네임스페이스
            label_visibility="collapsed",
        )
    with c2:
        send = st.button("➤", key="chat_send__skeleton", use_container_width=True)
    if send and q.strip():
        st.write(f"**질문:** {q.strip()}")
        st.write("**답변:** 준비 중입니다… (스켈레톤)")

if __name__ == "__main__":
    main()
# [C-1] END: FILE src/ui/chat.py
