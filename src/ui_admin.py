# ============================ ui_admin.py — START ============================
from __future__ import annotations

import json
import os
import time
from typing import Optional

import streamlit as st


def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if hasattr(st, "secrets"):
            val = st.secrets.get(name, None)
        else:
            val = None
        if val is None:
            return os.getenv(name, default)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)


def ensure_admin_session_keys() -> None:
    ss = st.session_state
    ss.setdefault("is_admin", False)
    ss.setdefault("admin_login_ts", "")
    ss.setdefault("qa_mode_radio", "문법설명")
    ss.setdefault("_show_admin_login", False)


def render_admin_controls() -> None:
    ensure_admin_session_keys()
    ss = st.session_state

    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.caption("관리자 도구 · Admin tools")
    with col2:
        if not ss.get("is_admin"):
            if st.button("관리자 로그인", key="btn_admin_login"):
                ss["_show_admin_login"] = True
        else:
            if st.button("관리자 로그아웃", key="btn_admin_logout"):
                ss["is_admin"] = False
                st.success("로그아웃 되었습니다.")
                st.rerun()

    if ss.get("_show_admin_login") and not ss.get("is_admin"):
        st.markdown("#### 🔐 관리자 로그인")
        pw = st.text_input("비밀번호", type="password")
        if st.button("로그인", type="primary"):
            correct = _secret("APP_ADMIN_PASSWORD") or _secret("ADMIN_PASSWORD")
            if correct and pw and str(pw) == str(correct):
                ss["is_admin"] = True
                ss["admin_login_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
                st.success("관리자 모드로 전환되었습니다.")
                ss["_show_admin_login"] = False
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
# ============================= ui_admin.py — END =============================
