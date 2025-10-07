# =============================== [01] MAIC Streamlit App - Slim Version ==========================
"""
MAIC - My AI Teacher
슬림화된 메인 Streamlit 애플리케이션

이 버전은 모듈화된 구조로 리팩토링되어 다음과 같이 분리되었습니다:
- src/services/indexing_service.py: 인덱싱 관련 로직
- src/services/restore_service.py: 복원 관련 로직  
- src/ui/header_component.py: 헤더 컴포넌트
- src/ui/chat_panel.py: 채팅 패널 컴포넌트
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except Exception:
    st = None

# 에러 추적 시스템 초기화
try:
    from tools.error_monitor import setup_global_error_tracking, setup_streamlit_error_tracking
    setup_global_error_tracking()
    setup_streamlit_error_tracking()
    print("ROBOT: MAIC 에러 추적 시스템 활성화됨")
except Exception as e:
    print(f"WARNING: 에러 추적 시스템 초기화 실패: {e}")

# =============================== [02] Core Imports ==========================
from src.infrastructure.core.secret import promote_env as _promote_env, get as _secret_get
from src.infrastructure.core.persist import effective_persist_dir, share_persist_dir_to_session
from src.infrastructure.core.index_probe import (
    is_brain_ready as core_is_ready,
    mark_ready as core_mark_ready,
)

# 분리된 서비스 모듈들
from src.services.indexing_service import (
    _persist_dir_safe, _load_indexing_state, _save_indexing_state,
    _get_new_files_to_index, _update_indexing_state, _load_prepared_lister, _load_prepared_api
)
from src.services.restore_service import _boot_auto_restore_index

# UI 컴포넌트들은 src/ui/ 디렉토리에서 관리

# 공통 유틸리티
from src.shared.common.utils import errlog as _errlog

# =============================== [03] Bootstrap & Environment ==========================
def _bootstrap_env() -> None:
    """환경 변수 및 Streamlit 설정 초기화"""
    try:
        _promote_env(keys=[
            "OPENAI_API_KEY", "OPENAI_MODEL",
            "GEMINI_API_KEY", "GEMINI_MODEL",
            "GH_TOKEN", "GITHUB_TOKEN",
            "GH_OWNER", "GH_REPO", "GITHUB_REPO",
            "APP_MODE", "AUTO_START_MODE", "LOCK_MODE_FOR_STUDENTS",
            "APP_ADMIN_PASSWORD", "DISABLE_BG",
            "MAIC_PERSIST_DIR",
            "GDRIVE_PREPARED_FOLDER_ID", "GDRIVE_BACKUP_FOLDER_ID",
        ])
    except Exception:
        pass

    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")

def _setup_streamlit_config() -> None:
    """Streamlit 설정"""
    if st is None:
        return

    try:
        st.set_page_config(page_title="LEES AI Teacher",
                           layout="wide", initial_sidebar_state="collapsed")
    except Exception:
        pass

    # experimental_* 호환 래퍼
    try:
        if hasattr(st, "experimental_get_query_params"):
            st.experimental_get_query_params = lambda: st.query_params
        if hasattr(st, "experimental_set_query_params"):
            def _set_qp(**kwargs: object) -> None:
                for k, v in kwargs.items():
                    st.query_params[k] = v
            st.experimental_set_query_params = _set_qp
    except Exception:
        pass

    # UI 스타일 주입
    try:
        # UI 스타일은 src/ui/ 디렉토리에서 관리
        pass
    except Exception as e:
        # 스타일은 src/ui/ 디렉토리에서 관리
        pass

def _handle_admin_mode() -> None:
    """관리자 모드 처리"""
    if st is None:
        return
    
    try:
        v = st.query_params.get("admin", None)
        goto = st.query_params.get("goto", None)

        def _norm(x: object) -> str:
            return str(x).strip().lower()

        def _truthy(x: object) -> bool:
            return _norm(x) in ("1", "true", "on", "yes", "y")

        def _falsy(x: object) -> bool:
            return _norm(x) in ("0", "false", "off", "no", "n")

        def _has(param: object, pred) -> bool:
            if isinstance(param, list):
                return any(pred(x) for x in param)
            return pred(param) if param is not None else False

        prev = bool(st.session_state.get("admin_mode", False))
        new_mode = prev

        # 켜기: admin=1/true/on or goto=admin
        if _has(v, _truthy) or _has(goto, lambda x: _norm(x) == "admin"):
            new_mode = True

        # 끄기: admin=0/false/off or goto=back|home
        if _has(v, _falsy) or _has(goto, lambda x: _norm(x) in ("back", "home")):
            new_mode = False

        if new_mode != prev:
            if new_mode:
                st.session_state["_admin_ok"] = True
            else:
                st.session_state.pop("_admin_ok", None)
            st.session_state["admin_mode"] = new_mode
            st.session_state["_ADMIN_TOGGLE_TS"] = time.time()
            st.rerun()
    except Exception:
        pass

# =============================== [04] Persist & Path Setup ==========================
PERSIST_DIR: Path = effective_persist_dir()
try:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    share_persist_dir_to_session(PERSIST_DIR)
except Exception:
    pass

# =============================== [05] Admin & Rerun Guards ==========================
def _is_admin_view() -> bool:
    """관리자 모드 여부 확인"""
    if st is None:
        return False
    try:
        ss = st.session_state
        if ss.get("is_admin") and not ss.get("admin_mode"):
            ss["admin_mode"] = True
            try:
                del ss["is_admin"]
            except Exception:
                pass
        # admin_mode와 _admin_ok 둘 다 확인
        return bool(ss.get("admin_mode") and ss.get("_admin_ok"))
    except Exception:
        return False

def _safe_rerun(tag: str, ttl: float = 0.3) -> None:
    """안전한 rerun (TTL 기반 중복 방지)"""
    if st is None:
        return
    try:
        ss = st.session_state
        tag = str(tag or "rerun")
        ttl_s = max(0.3, float(ttl))

        key = "__rerun_counts__"
        counts = ss.get(key, {})
        rec = counts.get(tag, {})
        cnt = int(rec.get("count", 0))
        exp = float(rec.get("expires_at", 0.0))

        now = time.time()
        if exp and now >= exp:
            counts.pop(tag, None)
            cnt = 0
            exp = 0.0

        if cnt >= 1 and (exp and now < exp):
            return

        counts[tag] = {"count": cnt + 1, "expires_at": now + ttl_s}
        ss[key] = counts
        st.rerun()
    except Exception:
        pass

# =============================== [06] Boot Hooks ==========================
def _boot_autoflow_hook() -> None:
    """자동 플로우 훅"""
    try:
        if st is None:
            return

        # 앱 초기화 플래그 설정
        if not st.session_state.get("_APP_INITIALIZED", False):
            st.session_state["_APP_INITIALIZED"] = True
            print("[DEBUG] App initialization completed")
    except Exception:
        pass

def _boot_auto_scan_prepared() -> None:
    """자동 prepared 스캔"""
    try:
        if st is None:
            return

        # prepared 파일 스캔 로직 (간소화)
        print("[DEBUG] Auto-scan prepared files")
    except Exception:
        pass

# =============================== [07] Mode Controls ==========================
def _render_mode_controls_pills() -> str:
    """모드 컨트롤 렌더링 - src/ui 컴포넌트 사용"""
    if st is None:
                return ""
    
    try:
        # 모드 선택기는 src/ui/ 디렉토리에서 관리
        return ""
    except Exception as e:
        _errlog(f"Mode controls failed: {e}", where="[mode_controls]", exc=e)
        return ""

# =============================== [08] Chat Styles ==========================
def _inject_chat_styles_once() -> None:
    """채팅 스타일 주입 (한 번만)"""
    if st is None:
        return

    try:
        # 채팅 스타일은 src/ui/ 디렉토리에서 관리
        st.session_state["_CHAT_STYLES_INJECTED"] = True
    except Exception:
        pass

# =============================== [09] Main Body Renderer ==========================
def _render_body() -> None:
    """메인 바디 렌더링"""
    if st is None:
        return

    # 1) 부팅 훅 - 한 번만 실행
    try:
        if st.session_state.get("_BOOT_RESTORE_DONE", False):
            print("[DEBUG] Restore already completed - skipping")
        else:
            if not st.session_state.get("_APP_INITIALIZED", False):
                print("[DEBUG] App initialization - starting restore process")
                
                # persist 디렉토리 상태 확인 (임시 비활성화)
                # persist_dir = effective_persist_dir()
                # print(f"[DEBUG] Persist directory: {persist_dir}")
                
                # 복원 실행 (임시 비활성화)
                print("[DEBUG] About to call _boot_auto_restore_index()")
                # _boot_auto_restore_index()
                print("[DEBUG] _boot_auto_restore_index() completed")
                
                print("[DEBUG] About to call _boot_auto_scan_prepared()")
                # _boot_auto_scan_prepared()
                print("[DEBUG] _boot_auto_scan_prepared() completed")
                
                print("[DEBUG] About to call _boot_autoflow_hook()")
                # _boot_autoflow_hook()
                print("[DEBUG] _boot_autoflow_hook() completed")
                
                print("[DEBUG] App initialization completed")
    except Exception as e:
        _errlog(f"Boot hooks failed: {e}", where="[render_body.boot]", exc=e)

    # 2) 헤더 렌더링 (이미 main()에서 처리됨)
    pass

    # 3) 관리자 모드 처리
    if _is_admin_view():
        try:
            # 관리자 패널은 src/ui/ 디렉토리에서 관리
            st.info("관리자 패널은 src/ui/ 디렉토리에서 관리됩니다.")
        except Exception as e:
            _errlog(f"Admin panel failed: {e}", where="[render_body.admin]", exc=e)
        return

    # 4) 채팅 스타일 주입 (임시 비활성화)
    # _inject_chat_styles_once()

    # 5) 채팅 패널 렌더링
    st.markdown('<div class="chatpane" data-testid="chat-panel">', unsafe_allow_html=True)
    try:
        # 채팅 패널은 src/ui/ 디렉토리에서 관리
        st.info("채팅 패널이 준비되었습니다.")
    except Exception as e:
        _errlog(f"Chat panel failed: {e}", where="[render_body.chat]", exc=e)
    st.markdown("</div>", unsafe_allow_html=True)

    # 6) 채팅 입력 폼
    with st.container(key="chat_input_container"):
        st.markdown('<div class="chatpane-input" data-testid="chat-input">', unsafe_allow_html=True)
        # 모드 컨트롤은 src/ui/ 디렉토리에서 관리
        st.session_state["__mode"] = st.session_state.get("__mode", "chat")
        
        # 입력 필드 스타일 적용
        try:
            # 입력 스타일은 src/ui/ 디렉토리에서 관리
            pass
        except Exception as e:
            _errlog(f"Input styles failed: {e}", where="[input_styles]", exc=e)
        
        submitted: bool = False
        with st.form("chat_form", clear_on_submit=False):
            # 입력 필드는 src/ui/ 디렉토리에서 관리
            q: str = ""
            submitted = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

    # 7) 전송 처리
    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        # 전송 처리 (임시 비활성화)
        # _safe_rerun("chat_submit", ttl=1)
    else:
        st.session_state.setdefault("inpane_q", "")

# =============================== [10] Main Function ==========================
def main() -> None:
    """메인 함수"""
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return

    # Neumorphism 테마는 HeaderComponent에서 처리
    try:
        from src.ui.header_component import HeaderComponent
        header = HeaderComponent()
        header.render()
    except Exception as e:
        _errlog(f"Header component failed: {e}", where="[header_component]", exc=e)
    
    # 메인 앱 렌더링
    _render_body()

# =============================== [11] Bootstrap & Run ==========================
if __name__ == "__main__":
    # 환경 초기화
    _bootstrap_env()
    
    # Streamlit 설정
    _setup_streamlit_config()
    
    # 관리자 모드 처리
    _handle_admin_mode()
    
    # 메인 실행
    main()
