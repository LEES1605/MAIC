
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
    st = None  # type: ignore[assignment]
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
        steps: List[Dict[str, Any]] = st.session_state["_IDX_STEPS"]  # type: ignore[assignment]
        idx = max(1, min(int(i), len(steps))) - 1
        steps[idx] = {"name": steps[idx]["name"], "status": status, "detail": detail}
        st.session_state["_IDX_STEPS"] = steps
    except Exception:
        # no-op on failure
        pass


def log(message: str, level: str = "info") -> None:
    """진행 로그를 세션에 기록한다. level: info|warn|err"""
    if st is None:
        return
    ensure_index_state()
    try:
        logs: List[Dict[str, Any]] = st.session_state["_IDX_LOGS"]  # type: ignore[assignment]
        logs.append({"level": str(level or "info"), "message": str(message or ""), "ts": int(time.time())})
        # 로그 길이 제한(최근 2000개 유지)
        if len(logs) > 2000:
            del logs[:-2000]
        st.session_state["_IDX_LOGS"] = logs
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
    logs = st.session_state.get("_IDX_LOGS", [])
    icon_map = {"info": "ℹ️", "warn": "⚠️", "err": "❌"}
    with placeholder.container():
        if not logs:
            st.caption("로그가 없습니다.")
            return
        for entry in logs[-50:]:
            level = str(entry.get("level") or "info")
            message = str(entry.get("message") or "")
            icon = icon_map.get(level, "•")
            st.write(f"{icon} {message}")


def render_stepper_safe(force: bool = False) -> None:
    """_render_stepper(force=...) 가 앱쪽에 있으면 그걸 사용하고, 없으면 간단한 자리표시자."""
    if st is None:
        return
    try:
        fn = _resolve_app_attr("_render_stepper")
        if callable(fn):
            fn(force=force)  # type: ignore[misc]
            return
    except Exception:
        pass
    # 폴백: 간단한 상자 자리표시자 생성
    ph = st.session_state.get("_IDX_STEPPER_PH")
    if ph is None and force:
        ph = st.empty()
        st.session_state["_IDX_STEPPER_PH"] = ph
    if ph is not None:
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
