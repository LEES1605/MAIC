# ============================== [01] session state API — START ==============================
"""
세션 상태(배지/메시지/경로)의 단일 진입점.
- ensure_keys(): 필요한 키를 멱등 초기화
- set_brain_status(): 상태 코드/원천/부착여부/메시지 세팅
- get_brain_status(): 현재 상태 딕셔너리 반환
- persist_dir(): PERSIST_DIR 해석(우선순위: rag.index_build → config → ~/.maic/persist)
- snapshot_index(): 파일 시스템에서 READY 신호 요약
- sync_badge_from_fs(): 스냅샷으로 배지 동기화(멱등)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


# --------- public: persist_dir -------------------------------------------------
def persist_dir() -> Path:
    """PathResolver 클래스를 사용하여 persist 디렉토리 경로 해석"""
    try:
        from src.core.path_resolver import get_path_resolver
        return get_path_resolver().get_persist_dir()
    except Exception:
        return Path.home() / ".maic" / "persist"


# --------- public: ensure_keys -------------------------------------------------
def ensure_keys() -> None:
    import streamlit as st  # 런타임 임포트

    defaults = {
        "brain_status_code": "MISSING",
        "brain_status_origin": "",
        "brain_attached": False,
        "brain_status_msg": "",
        "_orchestrator_step": "프리검사",
        "_orchestrator_log": [],
        "_persist_dir": str(persist_dir()),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# --------- public: set_brain_status / get_brain_status ------------------------
def set_brain_status(
    code: str,
    msg: str = "",
    origin: str = "",
    attached: Optional[bool] = None,
) -> None:
    import streamlit as st  # 런타임 임포트

    ensure_keys()
    st.session_state["brain_status_code"] = str(code or "").upper()
    st.session_state["brain_status_origin"] = origin or ""
    if attached is not None:
        st.session_state["brain_attached"] = bool(attached)
    if msg:
        st.session_state["brain_status_msg"] = msg


def get_brain_status() -> dict[str, Any]:
    import streamlit as st  # 런타임 임포트

    ensure_keys()
    return {
        "code": st.session_state.get("brain_status_code", "MISSING"),
        "origin": st.session_state.get("brain_status_origin", ""),
        "attached": bool(st.session_state.get("brain_attached", False)),
        "msg": st.session_state.get("brain_status_msg", ""),
    }


# --------- fs snapshot & badge sync -------------------------------------------
def _ready_path(p: Path) -> Path:
    return p / ".ready"


def _chunks_path(p: Path) -> Path:
    return p / "chunks.jsonl"


def snapshot_index(p: Optional[Path] = None) -> dict[str, Any]:
    base = p or persist_dir()
    try:
        cj = _chunks_path(base)
        size = cj.stat().st_size if cj.exists() else 0
        ready_flag = _ready_path(base).exists()
        local_ok = bool(ready_flag and cj.exists() and size > 0)
        return {
            "persist_dir": str(base),
            "ready_flag": ready_flag,
            "chunks_exists": cj.exists(),
            "chunks_size": size,
            "local_ok": local_ok,
        }
    except Exception:
        return {
            "persist_dir": str(base),
            "ready_flag": False,
            "chunks_exists": False,
            "chunks_size": 0,
            "local_ok": False,
        }


def sync_badge_from_fs() -> dict[str, Any]:
    """
    파일 시스템 스냅샷을 읽어 배지/메시지를 일관되게 맞춘다(멱등).
    - READY: code=READY, attached=True
    - 그 외:  code=MISSING, attached=False
    반환: 스냅샷 dict
    """
    snap = snapshot_index()
    if snap.get("local_ok"):
        set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
    else:
        set_brain_status("MISSING", "인덱스가 준비되지 않았습니다.", "", attached=False)
    return snap
# =============================== [01] session state API — END ===============================
