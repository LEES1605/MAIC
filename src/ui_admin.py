# ============================ ui_admin.py — START ============================
from __future__ import annotations
import os, json, time
from typing import Any, Dict, Optional
import streamlit as st

# ---- 세션 키 보장 -----------------------------------------------------------
def ensure_admin_session_keys() -> None:
    ss = st.session_state
    ss.setdefault("is_admin", False)
    ss.setdefault("admin_login_ts", "")
    ss.setdefault("qa_mode_radio", "문법설명")

def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = st.secrets.get(name)  # type: ignore[attr-defined]
        if val is None: return os.getenv(name, default)
        if isinstance(val, str): return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)

# ---- 관리자 로그인/로그아웃 UI ---------------------------------------------
def render_admin_controls() -> None:
    ensure_admin_session_keys()
    ss = st.session_state
    cols = st.columns([0.65, 0.35])
    with cols[0]:
        st.caption("관리자 도구 · Admin tools")
    with cols[1]:
        if ss.get("is_admin"):
            if st.button("로그아웃", use_container_width=True):
                ss["is_admin"] = False
                ss["admin_login_ts"] = ""
                st.experimental_rerun()
        else:
            with st.popover("관리자 로그인", use_container_width=True):
                pwd_set = _secret("APP_ADMIN_PASSWORD", "0000") or "0000"
                pwd_in = st.text_input("비밀번호", type="password")
                if st.button("Login", type="primary"):
                    if pwd_in and pwd_in == pwd_set:
                        ss["is_admin"] = True
                        ss["admin_login_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        st.success("로그인 성공")
                        st.experimental_rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")

def render_role_caption() -> None:
    if st.session_state.get("is_admin"):
        st.info(f"관리자 모드 (since {st.session_state.get('admin_login_ts','')})")
    else:
        st.caption("학생 모드")

# ---- 설명 모드 라디오(관리자 전용) -----------------------------------------
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
