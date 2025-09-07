# =================================== [01] future import ===================================
from __future__ import annotations

# =================================== [02] module imports ==================================
from typing import Dict, Optional, TYPE_CHECKING
import os

try:
    import streamlit as st
except Exception:
    st = None  # Streamlit이 없는 환경(CI 등) 대비

if TYPE_CHECKING:
    # 런타임 의존은 함수 내부에서 lazy import 하므로, 타입만 체크 시 사용
    from src.core.index_probe import IndexHealth  # noqa: F401


# =================================== [03] SSOT helpers ====================================
def _ready_level() -> str:
    """인덱스 상태를 HIGH/MID/LOW로 환산 (SSOT 기반)."""
    try:
        # SSOT: 코어의 probe 호출(경로 결정을 코어에 위임)
        from src.core.index_probe import probe_index_health

        info: "IndexHealth" = probe_index_health()  # persist 미지정: 코어가 해석
        size_ok = int(getattr(info, "chunks_size", 0) or 0) > 0
        json_ok = bool(
            (int(getattr(info, "json_sample", 0) or 0) > 0)
            and int(getattr(info, "json_malformed", 0) or 0) == 0
        )
        ok = bool(
            getattr(info, "ready_exists", False)
            and getattr(info, "chunks_exists", False)
            and size_ok
            and json_ok
        )
        return "HIGH" if ok else ("MID" if (size_ok and json_ok) else "LOW")
    except Exception:
        # 코어 호출 실패 시 보수적으로 LOW
        return "LOW"


def _from_secrets(name: str, default: Optional[str] = None) -> Optional[str]:
    """Streamlit secrets 안전 접근."""
    try:
        if st is None or not hasattr(st, "secrets"):
            return os.getenv(name, default)
        val = st.secrets.get(name, None)
        if val is None:
            return os.getenv(name, default)
        return str(val)
    except Exception:
        return os.getenv(name, default)


# =================================== [04] UI: header render ================================
def render() -> None:
    """상단 헤더(학생: 상태칩+펄스점, 관리자: + 로그인/아웃)."""
    if st is None:
        return

    ss = st.session_state
    ss.setdefault("admin_mode", False)
    ss.setdefault("_show_admin_login", False)

    level = _ready_level()
    label_map = {"HIGH": "준비완료", "MID": "준비중", "LOW": "문제발생"}
    dot_map = {"HIGH": "rd-high", "MID": "rd-mid", "LOW": "rd-low"}
    label = label_map.get(level, "문제발생")
    dot_cls = dot_map.get(level, "rd-low")

    # CSS (E501 회피 위해 속성 단위 줄바꿈)
    st.markdown(
        """
        <style>
          .brand-wrap{ display:flex; align-items:center; gap:10px; }
          .brand-title{ font-weight:900; letter-spacing:.2px; font-size:250%; line-height:1.1; }
          .ready-chip{
            display:inline-flex; align-items:center; gap:6px;
            padding:2px 10px; border-radius:12px;
            background:#f4f6fb; border:1px solid #e5e7eb;
            font-weight:800; color:#111827; font-size:18px;
          }
          .rd{ width:8px; height:8px; border-radius:50%; display:inline-block; animation:pulseDot 1.8s infinite; }
          .rd-high{ background:#16a34a; box-shadow:0 0 0 0 rgba(22,163,74,.55); }
          .rd-mid{ background:#f59e0b; box-shadow:0 0 0 0 rgba(245,158,11,.55); }
          .rd-low{ background:#ef4444; box-shadow:0 0 0 0 rgba(239,68,68,.55); }
          @keyframes pulseDot{
            0%{ box-shadow:0 0 0 0 rgba(0,0,0,0.18); }
            70%{ box-shadow:0 0 0 16px rgba(0,0,0,0); }
            100%{ box-shadow:0 0 0 0 rgba(0,0,0,0); }
          }
          .admin-login-narrow [data-testid="stTextInput"] input{ height:42px; border-radius:10px; }
          .admin-login-narrow .stButton>button{ width:100%; height:42px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # (빈칸) | [라벨+점 + 제목] | [관리자 버튼]
    _, c2, c3 = st.columns([1, 6, 2], gap="small")
    with c2:
        chip_html = f'<span class="ready-chip">{label}<span class="rd {dot_cls}"></span></span>'
        title_html = (
            '<div class="brand-wrap">'
            f'{chip_html}<span class="brand-title">LEES AI Teacher</span>'
            "</div>"
        )
        st.markdown(title_html, unsafe_allow_html=True)

    with c3:
        if ss.get("admin_mode"):
            if st.button("🚪 로그아웃", key="logout_now", help="관리자 로그아웃"):
                ss["admin_mode"] = False
                ss["_show_admin_login"] = False
                try:
                    st.toast("로그아웃 완료", icon="👋")
                except Exception:
                    st.success("로그아웃 완료")
                st.rerun()
        else:
            if st.button("🔐 관리자", key="open_admin_login", help="관리자 로그인"):
                ss["_show_admin_login"] = not ss.get("_show_admin_login", False)

    # 관리자 로그인 폼
    need_login = (not ss.get("admin_mode")) and ss.get("_show_admin_login")
    if need_login:
        with st.container(border=True):
            st.write("🔐 관리자 로그인")
            try:
                pwd_set = (
                    _from_secrets("ADMIN_PASSWORD", None)
                    or _from_secrets("APP_ADMIN_PASSWORD", None)
                    or _from_secrets("MAIC_ADMIN_PASSWORD", None)
                    or os.getenv("ADMIN_PASSWORD")
                    or os.getenv("APP_ADMIN_PASSWORD")
                    or os.getenv("MAIC_ADMIN_PASSWORD")
                    or None
                )
            except Exception:
                pwd_set = None

            left, mid, right = st.columns([2, 1, 2])
            with mid:
                with st.form("admin_login_form", clear_on_submit=False):
                    st.markdown('<div class="admin-login-narrow">', unsafe_allow_html=True)
                    pw = st.text_input("비밀번호", type="password", key="admin_pw_input")
                    col_a, col_b = st.columns([1, 1])
                    submit = col_a.form_submit_button("로그인")
                    cancel = col_b.form_submit_button("닫기")
                    st.markdown("</div>", unsafe_allow_html=True)

                if cancel:
                    ss["_show_admin_login"] = False
                    st.rerun()

                if submit:
                    if not pwd_set:
                        st.error("서버에 관리자 비밀번호가 설정되어 있지 않습니다.")
                    elif pw and str(pw) == str(pwd_set):
                        ss["admin_mode"] = True
                        ss["_show_admin_login"] = False
                        try:
                            st.toast("로그인 성공", icon="✅")
                        except Exception:
                            st.success("로그인 성공")
                        st.rerun()
                    else:
                        st.error("비밀번호가 올바르지 않습니다.")
