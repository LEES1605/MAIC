# ===== [UA-01] ADMIN CONTROLS MODULE — START ================================
from __future__ import annotations
import os
import streamlit as st

# ── [UA-01A] PIN 소스 --------------------------------------------------------
def get_admin_pin() -> str:
    """
    우선순위: st.secrets['ADMIN_PIN'] → 환경변수 ADMIN_PIN → 기본 '0000'
    """
    try:
        pin = st.secrets.get("ADMIN_PIN", None)  # type: ignore[attr-defined]
    except Exception:
        pin = None
    return str(pin or os.environ.get("ADMIN_PIN") or "0000")

# ── [UA-01B] 세션 키 보증 -----------------------------------------------------
def ensure_admin_session_keys() -> None:
    """
    app.py 어디서든 호출해도 안전. 필요한 세션 키가 없으면 기본값 생성.
    """
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False
    if "_admin_auth_open" not in st.session_state:
        st.session_state["_admin_auth_open"] = False

# ── [UA-01C] 관리자 버튼/인증 패널 — START ------------------------------------
def render_admin_controls() -> None:
    """
    상단 우측 '관리자' 버튼과 PIN 인증 폼을 렌더링.
    + '🔎 진단'은 JS 없이 앵커 링크 버튼으로 구현(#diag로 이동, rerun 방지).
    """
    import streamlit as st

    with st.container():
        _, right = st.columns([0.7, 0.3])
        with right:
            c_admin, c_diag = st.columns([0.55, 0.45])

            # --- 관리자 진입/종료 버튼 ---
            if st.session_state.get("is_admin", False):
                with c_admin:
                    if st.button("🔓 관리자 종료", key="btn_close_admin", use_container_width=True):
                        st.session_state["is_admin"] = False
                        st.session_state["_admin_auth_open"] = False
                        try: st.toast("관리자 모드 해제됨")
                        except Exception: pass
                        st.rerun()
            else:
                with c_admin:
                    if st.button("🔒 관리자", key="btn_open_admin", use_container_width=True):
                        st.session_state["_admin_auth_open"] = True
                        st.rerun()

            # --- 진단으로 이동: 앵커 링크 버튼( rerun 발생 X ) ---
            with c_diag:
                if hasattr(st, "link_button"):
                    st.link_button("🔎 진단", url="#diag", use_container_width=True, help="페이지 하단 진단 섹션(#diag)으로 이동")
                else:
                    # 구버전 스트림릿 호환: 단순 앵커 링크 (버튼 스타일은 간단)
                    st.markdown(
                        '<a href="#diag" target="_self" style="display:block;text-align:center;padding:0.5rem 0;'
                        'border:1px solid rgba(255,255,255,0.2);border-radius:0.5rem;text-decoration:none;">🔎 진단</a>',
                        unsafe_allow_html=True
                    )

            # --- 인증 패널 ---
            if st.session_state.get("_admin_auth_open", False) and not st.session_state.get("is_admin", False):
                with st.container(border=True):
                    st.markdown("**관리자 PIN 입력**")
                    with st.form("admin_login_form", clear_on_submit=True, border=False):
                        pin_try = st.text_input("PIN", type="password")
                        c1, c2 = st.columns(2)
                        with c1:
                            ok = st.form_submit_button("입장")
                        with c2:
                            cancel = st.form_submit_button("취소")

                if cancel:
                    st.session_state["_admin_auth_open"] = False
                    st.rerun()
                if ok:
                    if pin_try == get_admin_pin():
                        st.session_state["is_admin"] = True
                        st.session_state["_admin_auth_open"] = False
                        try: st.toast("관리자 모드 진입 ✅")
                        except Exception: pass
                        st.rerun()
                    else:
                        st.error("PIN이 올바르지 않습니다.")
# ── [UA-01C] 관리자 버튼/인증 패널 — END --------------------------------------


# ── [UA-01D] 역할 캡션 --------------------------------------------------------
def render_role_caption() -> None:
    """
    역할 안내 캡션(학생/관리자). 시각적 혼란을 줄이기 위해 한 줄 고정 문구.
    """
    if st.session_state.get("is_admin", False):
        st.caption("역할: **관리자** — 상단 버튼으로 종료 가능")
    else:
        st.caption("역할: **학생** — 질문/답변에 집중할 수 있게 단순화했어요.")
# ===== [UA-01] ADMIN CONTROLS MODULE — END ==================================
