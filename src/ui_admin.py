# ================================= ui_admin.py — START ==========================
from __future__ import annotations

from typing import Optional

import streamlit as st


ADMIN_KEY = "is_admin"  # 세션키 단일화


def ensure_admin_session_keys() -> None:
    st.session_state.setdefault(ADMIN_KEY, False)
    st.session_state.setdefault("_admin_since", "")


def _login_form() -> None:
    st.markdown("#### 🔐 관리자 로그인")
    pw = st.text_input("비밀번호", type="password", key="admin_pw_input")
    if st.button("로그인", type="primary"):
        correct = st.secrets.get("APP_ADMIN_PASSWORD") or st.secrets.get("ADMIN_PASSWORD")
        if correct and pw and str(pw) == str(correct):
            st.session_state[ADMIN_KEY] = True
            st.session_state["_admin_since"] = st.session_state.get("_admin_since") or "now"
            st.success("관리자 모드로 전환되었습니다.")
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")


def _logout_box() -> None:
    st.markdown("#### 👤 관리자")
    st.caption(f"since: {st.session_state.get('_admin_since') or '-'}")
    if st.button("로그아웃", key="btn_admin_logout"):
        st.session_state[ADMIN_KEY] = False
        st.success("로그아웃 되었습니다.")
        st.rerun()


def render_admin_panel() -> None:
    """
    헤더의 ⚙️ 버튼 클릭 시 아래에 표시되는 관리자 패널(간단 버전).
    """
    ensure_admin_session_keys()
    if st.session_state.get(ADMIN_KEY):
        _logout_box()
        with st.expander("진단 도구", expanded=False):
            st.write("여기에 '지하철 진행선' 진단 UI가 렌더됩니다.")
            st.info("관리자 기능은 오케스트레이터 패널에서 동작합니다.")
    else:
        _login_form()
# ================================== ui_admin.py — END ===========================
