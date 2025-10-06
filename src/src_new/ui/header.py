# =============================== [01] module header =============================
"""
상단 헤더(학생: 상태칩+펄스점만, 관리자: + 로그인/아웃)

변경 사항(세션 우선 로직):
- 헤더 배지는 세션 상태를 우선 반영한다.
  * HIGH(초록): `_INDEX_IS_LATEST`가 True 이거나
                (`brain_status_code` == "READY" and `brain_attached` == True)
  * LOW(주황):  세션 코드가 "MISSING" 등 실패/미연결 상태
  * MID(노랑):  위 두 조건을 만족하지 않는 나머지(준비/부착 불완전)
- 세션 키가 전혀 없을 때만 로컬 probe(SSOT)로 폴백한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional
import importlib
import os

try:
    import streamlit as st
except Exception:
    st = None  # Streamlit이 없는 환경(CI 등) 대비

from src.core.secret import get as secret_get

if TYPE_CHECKING:
    from src.core.index_probe import IndexHealth  # noqa: F401


def _render_admin_navbar() -> None:
    """관리자 모드 네비게이션바 렌더링"""
    if st is None:
        return
    
    # 관리자 네비게이션바 CSS
    admin_navbar_css = """
    <style>
    .admin-navbar {
        background: var(--linear-bg-primary) !important;
        border-bottom: 1px solid var(--linear-border) !important;
        padding: 0.5rem 0 !important;
        margin: 0.5rem 0 1rem 0 !important;
        border-radius: var(--linear-radius) !important;
    }
    
    .admin-navbar-container {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 1rem !important;
        flex-wrap: wrap !important;
    }
    
    .admin-nav-item {
        padding: 0.5rem 1rem !important;
        border-radius: var(--linear-radius) !important;
        background: var(--linear-bg-secondary) !important;
        border: 1px solid var(--linear-border) !important;
        color: var(--linear-text-primary) !important;
        font-family: var(--linear-font) !important;
        font-weight: 500 !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    
    .admin-nav-item:hover {
        background: var(--linear-brand) !important;
        color: white !important;
        border-color: var(--linear-brand) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(94, 106, 210, 0.3) !important;
    }
    
    .admin-nav-item.active {
        background: var(--linear-brand) !important;
        color: white !important;
        border-color: var(--linear-brand) !important;
    }
    </style>
    """
    
    st.markdown(admin_navbar_css, unsafe_allow_html=True)
    
    # 네비게이션바 컨테이너
    with st.container():
        st.markdown('<div class="admin-navbar">', unsafe_allow_html=True)
        
        # 네비게이션 아이템들
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1], gap="small")
        
        with col1:
            if st.button("🏠 홈", key="admin_nav_home", help="메인 페이지로 이동"):
                st.session_state["admin_nav_active"] = "home"
                st.rerun()
        
        with col2:
            if st.button("⚙️ 관리", key="admin_nav_manage", help="시스템 관리"):
                st.session_state["admin_nav_active"] = "manage"
                st.rerun()
        
        with col3:
            if st.button("📝 프롬프트", key="admin_nav_prompt", help="프롬프트 관리"):
                st.session_state["admin_nav_active"] = "prompt"
                st.rerun()
        
        with col4:
            if st.button("📊 통계", key="admin_nav_stats", help="사용 통계"):
                st.session_state["admin_nav_active"] = "stats"
                st.rerun()
        
        with col5:
            if st.button("🔧 설정", key="admin_nav_settings", help="시스템 설정"):
                st.session_state["admin_nav_active"] = "settings"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)


# =============================== [02] ready level — START ==================
def _compute_ready_level_from_session(
    ss: Dict[str, object] | None,
    *,
    fallback_local_ok: Optional[bool] = None,
) -> str:
    """
    순수 판정 함수(테스트 용이). 세션 상태로만 등급을 정하고,
    세션 키가 전혀 없을 때에만 fallback_local_ok로 폴백한다.

    규칙:
      - HIGH:   _INDEX_IS_LATEST == True  OR (brain_status_code=="READY" and brain_attached==True)
      - LOW:    brain_status_code == "MISSING" (명시적 결손/미연결)
      - MID:    그 외 (준비/부착 불완전 등)
      - Fallback: 세션키 없음 → fallback_local_ok True면 MID, 아니면 LOW
    """
    ss = ss or {}
    has_any = any(k in ss for k in ("_INDEX_IS_LATEST", "brain_status_code", "brain_attached"))
    if not has_any:
        return "MID" if fallback_local_ok else "LOW"

    is_latest = bool(ss.get("_INDEX_IS_LATEST"))
    brain_code = ss.get("brain_status_code")
    if isinstance(brain_code, str):
        brain_code = brain_code.strip().upper()
    attached = bool(ss.get("brain_attached"))

    if is_latest or (brain_code == "READY" and attached):
        return "HIGH"
    if brain_code == "MISSING":
        return "LOW"
    return "MID"


def _ready_level() -> str:
    """인덱스 상태를 HIGH/MID/LOW로 환산 (세션 우선, 필요 시 SSOT probe 폴백)."""
    # 1) 세션 상태 확인
    if st is not None:
        ss = getattr(st, "session_state", {})
    else:
        ss = {}

    has_any = any(k in ss for k in ("_INDEX_IS_LATEST", "brain_status_code", "brain_attached"))
    if not has_any:
        # 2) 세션키가 전혀 없으면 로컬 probe로 폴백 (비용 최소화를 위해 필요한 순간에만)
        try:
            # lazy import: 타입 힌트는 문자열 리터럴로만 사용
            from src.core.index_probe import probe_index_health
            local_ok = bool(getattr(probe_index_health(sample_lines=0), "ok", False))
        except Exception:
            local_ok = False
        return _compute_ready_level_from_session({}, fallback_local_ok=local_ok)

    # 3) 세션이 있으면 오직 세션 기준으로만 결정
    return _compute_ready_level_from_session(ss, fallback_local_ok=None)
# =============================== [02] ready level — END ====================


# =============================== [03] UI: header render ==========================
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
    
    # 관리자 모드에서는 준비 상태에 따라 표시
    if ss.get("admin_mode", False):
        # 관리자 모드에서도 준비 상태 반영
        if level == "HIGH":
            label = "준비완료"
            dot_cls = "rd-high"
        elif level == "MID":
            label = "준비중"
            dot_cls = "rd-mid"
        else:
            label = "문제발생"
            dot_cls = "rd-low"

    # Linear 테마 CSS 변수 적용 (중복 제거 - base.py에서 처리)
    st.markdown(
        """
        <style>
        
        .brand-wrap{ 
          display:flex; 
          align-items:center; 
          gap:10px; 
        }
        
        .brand-title{ 
          font-family: var(--linear-font);
          font-weight: 590;
          letter-spacing: -.012em;
          font-size: 2.25rem; 
          line-height: 1.1; 
          color: var(--linear-text-primary);
        }
        
        .ready-chip{
          display: inline-flex; 
          align-items: center; 
          gap: 6px;
          padding: 4px 12px; 
          border-radius: var(--linear-radius-lg);
          background: var(--linear-bg-secondary); 
          border: 1px solid var(--linear-border);
          font-family: var(--linear-font);
          font-weight: 510; 
          color: var(--linear-text-secondary); 
          font-size: 0.9375rem;
        }
        
        .rd{ 
          width: 8px; 
          height: 8px; 
          border-radius: 50%;
          display: inline-block; 
          animation: pulseDot 1.8s infinite; 
        }
        
        .rd-high{ 
          background: var(--linear-brand);
          box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.8);
          animation: pulseReady 2s infinite;
        }
        
        .rd-mid{  
          background: #fc7840;
          box-shadow: 0 0 0 0 rgba(252, 120, 64, 0.55); 
        }
        
        .rd-low{  
          background: #eb5757;
          box-shadow: 0 0 0 0 rgba(235, 87, 87, 0.55); 
        }
        
        @keyframes pulseReady{
          0%, 100%{ 
            box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.8);
            transform: scale(1);
          }
          50%{ 
            box-shadow: 0 0 0 8px rgba(255, 255, 255, 0.2);
            transform: scale(1.02);
          }
        }
        
        @keyframes pulseDot{
          0%{ box-shadow: 0 0 0 0 rgba(0,0,0,0.18); }
          70%{ box-shadow: 0 0 0 16px rgba(0,0,0,0); }
          100%{ box-shadow: 0 0 0 0 rgba(0,0,0,0); }
        }
        
        .admin-login-narrow [data-testid="stTextInput"] input{
          height: 42px; 
          border-radius: var(--linear-radius);
          background: var(--linear-bg-secondary);
          border: 1px solid var(--linear-border);
          color: var(--linear-text-primary);
          font-family: var(--linear-font);
        }
        
        .admin-login-narrow .stButton>button{
          width: 100%; 
          height: 42px;
          border-radius: var(--linear-radius);
          background: var(--linear-brand);
          color: white;
          border: none;
          font-family: var(--linear-font);
          font-weight: 510;
        }
        
        /* 관리자 모드 Linear 스타일 */
        .admin-mode .brand-title {
          color: var(--linear-brand) !important;
        }
        
        .admin-mode .ready-chip {
          background: rgba(94, 106, 210, 0.1) !important;
          border-color: var(--linear-brand) !important;
          color: var(--linear-brand) !important;
        }
        
        /* 관리자 모드에서 제목을 위로 올리기 */
        .admin-mode .brand-wrap {
          margin-bottom: 0.5rem !important;
        }
        
        /* 메인 제목 적절한 크기 */
        .brand-title {
          font-size: 1.2em !important;
        }
        
        .ready-chip {
          font-size: 1.0em !important;
        }
        
        /* 관리자 네비게이션바 스타일 */
        .admin-navbar {
          background: var(--linear-bg-primary) !important;
          border: 1px solid var(--linear-border) !important;
          border-radius: var(--linear-radius) !important;
          padding: 0.75rem 1rem !important;
          margin: 0.5rem 0 1rem 0 !important;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        }
        
        .admin-navbar .stButton > button {
          background: var(--linear-bg-secondary) !important;
          border: 1px solid var(--linear-border) !important;
          color: var(--linear-text-primary) !important;
          border-radius: var(--linear-radius) !important;
          padding: 0.5rem 1rem !important;
          font-weight: 500 !important;
          font-size: 1.3em !important;
          transition: all 0.2s ease !important;
        }
        
        .admin-navbar .stButton > button:hover {
          background: var(--linear-brand) !important;
          color: white !important;
          border-color: var(--linear-brand) !important;
          transform: translateY(-1px) !important;
          box-shadow: 0 2px 8px rgba(94, 106, 210, 0.3) !important;
        }
        
        /* 버튼 글씨 기본 크기 */
        .stButton > button {
          font-size: 1.0em !important;
        }
        
        /* 섹션 제목 적절한 크기 */
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
          font-size: 1.1em !important;
        }
        
        /* 본문 텍스트는 기본 크기 유지 */
        .stMarkdown p, .stMarkdown div {
          font-size: 1em !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # (빈칸) | [라벨+점 + 제목] | [관리자 버튼]
    _, c2, c3 = st.columns([1, 6, 2], gap="small")
    with c2:
        chip_html = (
            f'<span class="ready-chip">{label}'
            f'<span class="rd {dot_cls}"></span></span>'
        )
        # 관리자 모드일 때 클래스 추가
        wrapper_class = "brand-wrap admin-mode" if ss.get("admin_mode", False) else "brand-wrap"
        title_html = (
            f'<div class="{wrapper_class}">'
            f'{chip_html}<span class="brand-title">LEES AI Teacher</span>'
            "</div>"
        )
        st.markdown(title_html, unsafe_allow_html=True)
        
        # 관리자 모드일 때 네비게이션바 추가
        if ss.get("admin_mode", False):
            _render_admin_navbar()

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

            # 시크릿 SSOT: st.secrets → env 자동 조회
            try:
                pwd_set = (
                    secret_get("ADMIN_PASSWORD")
                    or secret_get("APP_ADMIN_PASSWORD")
                    or secret_get("MAIC_ADMIN_PASSWORD")
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
                    # 보안 강화: 입력 검증 및 로그인 시도 제한
                    from src.core.security_manager import (
                        get_security_manager, 
                        InputType, 
                        SecurityLevel,
                        check_login_attempts,
                        record_login_attempt
                    )
                    
                    # 클라이언트 식별자 (IP 기반)
                    client_id = getattr(st, 'session_state', {}).get('_client_id', 'unknown')
                    if not client_id or client_id == 'unknown':
                        # 간단한 클라이언트 식별자 생성
                        import hashlib
                        client_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
                        ss['_client_id'] = client_id
                    
                    # 로그인 시도 제한 확인
                    is_allowed, limit_error = check_login_attempts(client_id)
                    if not is_allowed:
                        st.error(limit_error)
                        st.rerun()
                    
                    # 비밀번호 입력 검증
                    is_valid, validation_error = get_security_manager().validate_input(
                        pw, InputType.PASSWORD, "비밀번호", SecurityLevel.HIGH
                    )
                    
                    if not is_valid:
                        record_login_attempt(client_id, False)
                        st.error(validation_error)
                        st.rerun()
                    
                    # 비밀번호 설정 확인
                    if not pwd_set:
                        record_login_attempt(client_id, False)
                        st.error("서버에 관리자 비밀번호가 설정되어 있지 않습니다.")
                        st.rerun()
                    
                    # 비밀번호 검증 (타이밍 공격 방지를 위한 상수 시간 비교)
                    import hmac
                    try:
                        # 안전한 비밀번호 비교
                        is_correct = hmac.compare_digest(str(pw), str(pwd_set))
                        
                        if is_correct:
                            # 로그인 성공
                            record_login_attempt(client_id, True)
                            ss["admin_mode"] = True
                            ss["_show_admin_login"] = False
                            try:
                                st.toast("로그인 성공", icon="✅")
                            except Exception:
                                st.success("로그인 성공")
                            st.rerun()
                        else:
                            # 로그인 실패
                            record_login_attempt(client_id, False)
                            st.error("비밀번호가 올바르지 않습니다.")
                            st.rerun()
                            
                    except Exception as e:
                        # 보안 에러 메시지 정화
                        from src.core.security_manager import sanitize_error_message
                        record_login_attempt(client_id, False)
                        st.error(sanitize_error_message(e))
                        st.rerun()
# ========================================= [EOF] =========================================
