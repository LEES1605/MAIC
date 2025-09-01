# ============================ ui_admin.py — START ============================
from __future__ import annotations
import time
from typing import Optional
import streamlit as st
from src.common.utils import get_secret  # ✅ 통일 유틸 사용

def ensure_admin_session_keys() -> None:
    ss = st.session_state
    ss.setdefault("is_admin", False)
    ss.setdefault("_show_admin_login", False)
    ss.setdefault("admin_login_ts", "")

def render_admin_controls_inline() -> None:
    ensure_admin_session_keys()
    ss = st.session_state
    with st.container():
        cols = st.columns([1, 1, 6])
        with cols[0]:
            if st.button("관리자 로그인" if not ss.get("is_admin") else "🚪 로그아웃", use_container_width=True):
                if ss.get("is_admin"):
                    ss["is_admin"] = False
                    st.success("로그아웃")
                    st.rerun()
                else:
                    ss["_show_admin_login"] = not ss.get("_show_admin_login", False)

    if not ss.get("is_admin") and ss.get("_show_admin_login"):
        with st.container(border=True):
            st.write("### 관리자 로그인")
            pwd_set = get_secret("APP_ADMIN_PASSWORD", "0000") or "0000"  # ✅ 교체
            with st.form("admin_login_form", clear_on_submit=True):
                pwd_in = st.text_input("비밀번호", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
            if submitted:
                if pwd_in and pwd_in == pwd_set:
                    ss["is_admin"] = True
                    ss["admin_login_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    ss["_show_admin_login"] = False
                    st.success("로그인 성공")
                    st.rerun()
                else:
                    st.error("비밀번호가 틀렸습니다.")

def render_role_caption() -> None:
    if st.session_state.get("is_admin"):
        st.info(f"관리자 모드 (since {st.session_state.get('admin_login_ts','')})")
    else:
        st.caption("학생 모드")

def render_mode_radio_admin() -> None:
    ensure_admin_session_keys()
    ss = st.session_state
    with st.container(border=True):
        st.caption("설명 모드 선택")
        ss["qa_mode_radio"] = st.radio(
            "설명 모드",
            ["문법설명", "문장구조분석", "지문분석"],
            index=["문법설명", "문장구조분석", "지문분석"].index(ss.get("qa_mode_radio", "문법설명")),
            horizontal=True,
        )
# ============================= ui_admin.py — END =============================
