
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
    else:
        # 🔧 중복 누적 방지: 다시 그리기 전 반드시 비움
        try:
            placeholder.empty()
        except Exception:
            pass

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


# (아래는 기존 helpers에 있던 함수들)
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
    finally:
        # 변경 즉시 학생 진행바/로그를 갱신(관리자 여부에 상관없이 안전 호출)
        try:
            render_stepper_safe(force=True)
            # 로그 패널은 강제 생성까지는 하지 않음(학생 화면은 미니멀)
            render_status(force=False)
        except Exception:
            pass


def log(message: str, level: str = "info") -> None:
    """진행 로그를 세션에 기록한다. level: info|warn|err"""
    if st is None:
        return
    ensure_index_state()
    try:
        logs: List[Dict[str, Any]] = st.session_state["_IDX_LOGS"]  # type: ignore[assignment]
        logs.append({"level": str(level or "info"), "message": str(message or ""), "ts": int(time.time())})
        if len(logs) > 2000:
            del logs[:-2000]
        st.session_state["_IDX_LOGS"] = logs
    finally:
        try:
            # 학생 화면에도 최소 캡션은 유지, 관리자면 전체 로그 영역 생성
            render_stepper_safe(force=True)
            render_status(force=bool(st.session_state.get("admin_mode")))
        except Exception:
            pass


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
    with ph.container():
        st.progress(pct, text=f"{label} ({pct}%)")

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
