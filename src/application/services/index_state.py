
# =============================== [01] future import — START ===========================
from __future__ import annotations
# ================================ [01] future import — END ============================

# =============================== [02] module imports — START ==========================
from typing import Any, Dict, List, Sequence, Optional
import time
import sys
try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit is optional in test env
    st = None  # type: ignore
# ================================ [02] module imports — END ===========================

# ============================= [03] constants — START =================================
# 기본 인덱싱 단계 이름(표준)
INDEX_STEP_NAMES: Sequence[str] = ("persist", "index", "consume", "summary", "upload")
# ============================== [03] constants — END ==================================

# ============================= [04] helpers — START ===================================
def _resolve_app_attr(name: str):
    """Resolve attribute from the running app (__main__) without importing app module."""
    try:
        app_mod = sys.modules.get("__main__")
        return getattr(app_mod, name, None)
    except Exception:
        return None


def ensure_index_state(step_names: Sequence[str] | None = None) -> None:
    """세션에 인덱스 상태 컨테이너 키를 초기화한다."""
    if st is None:
        return
    ss = st.session_state
    if "_IDX_STEPS" not in ss:
        names = list(step_names or INDEX_STEP_NAMES)
        ss["_IDX_STEPS"] = [{"name": n, "status": "wait", "detail": ""} for n in names]
    if "_IDX_LOGS" not in ss:
        ss["_IDX_LOGS"] = []
    ss.setdefault("_IDX_STATUS_PH", None)
    ss.setdefault("_IDX_STEPPER_PH", None)


def step_set(i: int, status: str, detail: str = "") -> None:
    """i(1-base)번째 스텝의 상태를 갱신한다."""
    if st is None:
        return
    ensure_index_state()
    try:
        steps: List[Dict[str, Any]] = st.session_state["_IDX_STEPS"]
        idx = max(1, min(int(i), len(steps))) - 1
        steps[idx] = {"name": steps[idx]["name"], "status": status, "detail": detail}
        st.session_state["_IDX_STEPS"] = steps
        
        # 변경 즉시 학생 진행바만 갱신 (로그는 표시하지 않음)
        try:
            render_stepper_safe(force=True)
            # 로그 패널은 아예 표시하지 않음 (미니멀리즘)
            # render_status(force=False)
        except Exception:
            pass
    except Exception:
        # no-op on failure
        pass


def log(message: str, level: str = "info") -> None:
    """진행 로그를 세션에 기록한다. level: info|warn|err - ErrorHandler 통합"""
    if st is None:
        return
    ensure_index_state()
    try:
        # ErrorHandler를 사용하여 에러 로깅
        from src.core.error_handler import get_error_handler, ErrorLevel
        
        # 레벨 매핑
        level_mapping = {
            "info": ErrorLevel.INFO,
            "warn": ErrorLevel.WARN,
            "err": ErrorLevel.ERROR,
            "error": ErrorLevel.ERROR
        }
        
        error_level = level_mapping.get(level, ErrorLevel.INFO)
        get_error_handler().log(message, error_level, "index_state")
        
        # 기존 세션 상태 로그도 유지 (UI 호환성)
        logs: List[Dict[str, Any]] = st.session_state["_IDX_LOGS"]
        
        # 중복 메시지 방지: 같은 메시지가 5초 이내에 있으면 추가하지 않음
        now = int(time.time())
        message_str = str(message or "")
        level_str = str(level or "info")
        
        # 최근 5초 내 같은 메시지가 있는지 확인
        recent_duplicate = False
        for log_entry in logs[-10:]:  # 최근 10개만 확인
            if (log_entry.get("message") == message_str and 
                log_entry.get("level") == level_str and 
                now - int(log_entry.get("ts", 0)) < 5):
                recent_duplicate = True
                break
        
        if not recent_duplicate:
            logs.append({"level": level_str, "message": message_str, "ts": now})
            
            # 로그 길이 제한(최근 100개만 유지 - 모바일에서 성능 개선)
            if len(logs) > 100:
                del logs[:-100]
            st.session_state["_IDX_LOGS"] = logs
            
        # 관리자 모드에서는 로그 표시하지 않음 (미니멀리즘)
        try:
            render_stepper_safe(force=True)
            # 관리자 모드에서도 로그 표시하지 않음 - 상태 카드로 충분
            render_status(force=False)
        except Exception:
            pass
    except Exception:
        # 폴백: 기존 방식 사용
        try:
            fallback_logs: List[Dict[str, Any]] = st.session_state["_IDX_LOGS"]
            now = int(time.time())
            message_str = str(message or "")
            level_str = str(level or "info")
            fallback_logs.append({"level": level_str, "message": message_str, "ts": now})
            if len(fallback_logs) > 100:
                del fallback_logs[:-100]
            st.session_state["_IDX_LOGS"] = fallback_logs
        except Exception:
            pass
# ============================== [04] helpers — END ====================================

# ======================= [05] render helpers (UI) — START =============================
def render_status(force: bool = False) -> None:
    """상태(로그) 영역을 렌더한다. force=True면 placeholder를 강제로 만든다."""
    if st is None:
        return
    ensure_index_state()
    placeholder = st.session_state.get("_IDX_STATUS_PH")
    if placeholder is None:
        if not force:
            return
        placeholder = st.empty()
        st.session_state["_IDX_STATUS_PH"] = placeholder
    else:
        # 🔧 중복 누적 방지: 다시 그리기 전 반드시 비움
        try:
            placeholder.empty()
        except Exception:
            pass

    logs = st.session_state.get("_IDX_LOGS", [])
    icon_map = {"info": "ℹ️", "warn": "⚠️", "err": "❌"}
    
    # 모바일 친화적 로그 표시 CSS
    st.markdown("""
    <style>
    .mobile-log-container {
        max-height: 80px;
        overflow-y: auto;
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 6px;
        padding: 4px;
        margin: 4px 0;
    }
    .log-entry {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        font-size: 12px;
        border-bottom: 1px solid #eee;
    }
    .log-entry:last-child {
        border-bottom: none;
    }
    .log-icon {
        font-size: 14px;
        min-width: 20px;
    }
    .log-message {
        flex: 1;
        word-break: break-word;
    }
    @media (max-width: 768px) {
        .mobile-log-container {
            max-height: 60px;
            padding: 2px;
        }
        .log-entry {
            font-size: 10px;
            padding: 2px 0;
        }
        .log-icon {
            font-size: 10px;
            min-width: 14px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    with placeholder.container():
        if not logs:
            st.caption("로그가 없습니다.")
            return
        
        # 최근 3개 로그만 표시 (모바일에서 매우 컴팩트하게)
        recent_logs = logs[-3:]
        
        # HTML로 로그 표시 (매우 컴팩트하게)
        log_html = '<div class="mobile-log-container">'
        for entry in recent_logs:
            level = str(entry.get("level") or "info")
            message = str(entry.get("message") or "")
            icon = icon_map.get(level, "•")
            
            # 메시지 길이 제한 (모바일에서 가독성 향상)
            display_message = message
            if len(message) > 40:
                display_message = message[:37] + "..."
            
            log_html += f'''
            <div class="log-entry">
                <span class="log-icon">{icon}</span>
                <span class="log-message">{display_message}</span>
            </div>
            '''
        log_html += '</div>'
        
        st.markdown(log_html, unsafe_allow_html=True)
        
        # 로그 개수 표시 (간단하게)
        if len(logs) > 3:
            st.caption(f"최근 3개 로그 (총 {len(logs)}개)")


def render_stepper_safe(force: bool = False) -> None:
    """_render_stepper(force=...) 가 앱쪽에 있으면 그걸 사용하고, 없으면 간단한 자리표시자."""
    if st is None:
        return
    try:
        fn = _resolve_app_attr("_render_stepper")
        if callable(fn):
            fn(force=force)
            return
    except Exception:
        pass

    # 폴백: 간단한 상자 자리표시자 생성(중복 누적 없이 클린 렌더)
    ph = st.session_state.get("_IDX_STEPPER_PH")
    if ph is None:
        if not force:
            return
        ph = st.empty()
        st.session_state["_IDX_STEPPER_PH"] = ph
    else:
        # 🔧 중복 누적 방지
        try:
            ph.empty()
        except Exception:
            pass

    with ph.container():
        st.caption("인덱싱 단계 표시기(간이 모드)")


def render_index_steps() -> None:
    """스텝 표시 + 로그(상태) 표시를 함께 렌더한다."""
    if st is None:
        return
    render_stepper_safe(force=True)
    render_status(force=True)


def step_reset(step_names: Sequence[str] | None = None) -> None:
    """스텝/로그/플레이스홀더를 초기화하고 즉시 렌더한다."""
    if st is None:
        return
    names = list(step_names or INDEX_STEP_NAMES)
    ensure_index_state(names)
    st.session_state["_IDX_STEPS"] = [
        {"name": name, "status": "wait", "detail": ""} for name in names
    ]
    st.session_state["_IDX_LOGS"] = []
    for key in ("_IDX_STEPPER_PH", "_IDX_STATUS_PH"):
        ph = st.session_state.get(key)
        if ph is not None:
            try:
                ph.empty()
            except Exception:
                pass
            st.session_state[key] = None
    render_index_steps()
# ======================== [05] render helpers (UI) — END ==============================


# 중복 함수 정의 제거됨 - 위의 함수들이 사용됨


# ======================= [06] student compact progress — START =======================
from typing import Tuple

def _calc_progress() -> Tuple[int, str]:
    """
    세션의 _IDX_STEPS를 바탕으로 대략적인 퍼센트를 계산.
    - ok 1단계 = 1.0, run 1단계 = 0.5 로 가중
    """
    if st is None:
        return 0, "준비중"
    steps = st.session_state.get("_IDX_STEPS") or []
    if not isinstance(steps, list) or not steps:
        return 0, "준비중"
    total = max(1, len(steps))
    done = sum(1 for s in steps if str(s.get("status")) == "ok")
    running = any(str(s.get("status")) == "run" for s in steps)
    frac = (done + (0.5 if running else 0.0)) / float(total)
    pct = int(max(1, min(100, round(frac * 100))))
    # 진행중 단계의 메시지(디테일 > 이름)
    current = None
    for s in steps:
        if str(s.get("status")) in ("run", "wait"):
            current = s
            break
    label = (current or {}).get("detail") or (current or {}).get("name") or "준비중"
    return pct, str(label)

def render_progress_compact(force: bool = False) -> None:
    """
    학생 화면용 진행 바(퍼센티지). force=True면 플레이스홀더를 보장 생성.
    모바일 친화적으로 개선.
    """
    if st is None:
        return
    ensure_index_state()
    ph = st.session_state.get("_IDX_PROGRESS_PH")
    if ph is None and force:
        ph = st.empty()
        st.session_state["_IDX_PROGRESS_PH"] = ph
    if ph is None:
        return
    pct, label = _calc_progress()
    
    # 모바일 친화적 진행바 CSS
    st.markdown("""
    <style>
    .mobile-progress-container {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 8px;
        margin: 8px 0;
    }
    .progress-bar {
        width: 100%;
        height: 20px;
        background-color: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        position: relative;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
        border-radius: 10px;
        transition: width 0.3s ease;
        position: relative;
    }
    .progress-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: #495057;
        font-size: 11px;
        font-weight: 600;
        z-index: 1;
    }
    .progress-label {
        text-align: center;
        font-size: 12px;
        color: #6c757d;
        margin-top: 4px;
    }
    @media (max-width: 768px) {
        .mobile-progress-container {
            padding: 6px;
        }
        .progress-bar {
            height: 16px;
        }
        .progress-text {
            font-size: 10px;
        }
        .progress-label {
            font-size: 11px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    with ph.container():
        # HTML로 커스텀 진행바 표시
        progress_html = f'''
        <div class="mobile-progress-container">
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pct}%;"></div>
                <div class="progress-text">{pct}%</div>
            </div>
            <div class="progress-label">{label}</div>
        </div>
        '''
        st.markdown(progress_html, unsafe_allow_html=True)

def progress_tick() -> None:
    """상태 변화 시 부담 없이 호출(존재하면 업데이트)."""
    if st is None:
        return
    if st.session_state.get("_IDX_PROGRESS_PH"):
        render_progress_compact(force=False)
# ======================= [06] student compact progress — END =========================

# ======================== [06] progress wrappers — START ===========================
def render_progress_with_fallback(pct: int, *, text: str = "") -> None:
    """
    Streamlit 버전 호환 진행바:
    - 신형: st.progress(pct, text="...") 지원
    - 구형: st.progress(pct)만 지원 → 캡션으로 텍스트 보완
    - 예외 시에도 UX를 깨지 않도록 안전 폴백
    """
    if st is None:
        return
    try:
        val = int(max(0, min(100, int(pct))))
    except Exception:
        val = 0

    try:
        # 신형 시그니처
        st.progress(val, text=text)
        return
    except TypeError:
        # 구형 시그니처
        st.progress(val)
        if text:
            st.caption(text)
    except Exception:
        # 마지막 폴백(텍스트만)
        try:
            st.caption(f"{text} ({val}%)" if text else f"{val}%")
        except Exception:
            pass
# ========================= [06] progress wrappers — END ============================
