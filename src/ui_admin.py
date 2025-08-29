# ============================ ui_admin.py — START ============================
from __future__ import annotations
import os, json, time
from typing import Optional
import streamlit as st

def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = st.secrets.get(name)  # type: ignore[attr-defined]
        if val is None: return os.getenv(name, default)
        if isinstance(val, str): return val
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
        if ss.get("is_admin"):
            if st.button("로그아웃", use_container_width=True):
                ss["is_admin"] = False
                ss["admin_login_ts"] = ""
                st.rerun()
        else:
            # 팝오버 대신 고정형 토글 버튼 → 겹침 현상 방지
            if st.button("관리자 로그인", use_container_width=True):
                ss["_show_admin_login"] = not ss.get("_show_admin_login", False)

    if not ss.get("is_admin") and ss.get("_show_admin_login"):
        with st.container(border=True):
            st.write("### 관리자 로그인")
            pwd_set = _secret("APP_ADMIN_PASSWORD", "0000") or "0000"
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
