# =========================== [01] imports & notes — START =========================
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import importlib
import json
import os
import time
# =========================== [01] imports & notes — END ===========================


# ====================== [02] persist resolver (SSOT) — START =====================
def _persist_dir() -> Path:
    """
    Persist 경로의 단일 소스.
    core.persist.effective_persist_dir()만 신뢰하고, 실패 시 홈 폴백.
    """
    try:
        from src.core.persist import effective_persist_dir
        p = effective_persist_dir()
        return p if isinstance(p, Path) else Path(str(p)).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"
# ====================== [02] persist resolver (SSOT) — END =======================


# ==================== [03] ready/chunks helpers — START ==========================
def _chunks_path(p: Path) -> Path:
    return p / "chunks.jsonl"


def _ready_path(p: Path) -> Path:
    return p / ".ready"


def _local_ready(p: Optional[Path] = None) -> bool:
    """READY 기준: .ready 존재 && chunks.jsonl 존재 && size>0."""
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        return _ready_path(base).exists() and cj.exists() and cj.stat().st_size > 0
    except Exception:
        return False


def _ensure_ready_signal(p: Optional[Path] = None) -> None:
    """chunks.jsonl이 있고 .ready가 없으면 .ready 생성(멱등)."""
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        r = _ready_path(base)
        if cj.exists() and cj.stat().st_size > 0 and not r.exists():
            r.write_text("ok", encoding="utf-8")
    except Exception:
        pass
# ===================== [03] ready/chunks helpers — END ===========================


# ==================== [04] Streamlit status bridge — START ======================
def _set_brain_status(code: str, msg: str, src: str = "", attached: bool = False) -> None:
    """app.py와 동일 키로 상태 반영(존재 시). 세션 없으면 무해."""
    try:
        import streamlit as st  # noqa: WPS433 (optional dep)
    except Exception:
        return
    try:
        ss = st.session_state
        ss["brain_status_code"] = code
        ss["brain_status_msg"] = msg
        ss["brain_source"] = src
        ss["brain_attached"] = bool(attached)
        ss["restore_recommend"] = code in ("MISSING", "ERROR")
        ss.setdefault("index_decision_needed", False)
        ss.setdefault("index_change_stats", {})
    except Exception:
        pass
# ==================== [04] Streamlit status bridge — END ========================


# ==================== [05] public: index_status — START =========================
def index_status(p: Optional[Path] = None) -> Dict[str, Any]:
    """현 로컬 인덱스 상태 요약(SSOT 기준)."""
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        return {
            "persist_dir": str(base),
            "chunks_exists": cj.exists(),
            "chunks_size": (cj.stat().st_size if cj.exists() else 0),
            "ready_flag": _ready_path(base).exists(),
            "local_ok": _local_ready(base),
            "code": "READY" if _local_ready(base) else "MISSING",
        }
    except Exception:
        return {
            "persist_dir": str(base),
            "chunks_exists": False,
            "chunks_size": 0,
            "ready_flag": False,
            "local_ok": False,
            "code": "MISSING",
        }
# ==================== [05] public: index_status — END ===========================


# ==================== [06] public: reindex — START ==============================
def reindex(dest_dir: Optional[str | Path] = None) -> bool:
    """
    HQ 인덱싱(SSOT 경로 사용).
    - dest_dir 지정 시 해당 경로로 빌드(테스트/임시용).
    - 성공 기준: chunks.jsonl > 0B && .ready 존재.
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    try:
        mod = importlib.import_module("src.rag.index_build")
        fn = getattr(mod, "rebuild_index", None)
        if not callable(fn):
            return False
        # 인덱서에 출력 경로를 명시 전달(SSOT 보장)
        fn(output_dir=base)
    except Exception:
        return False

    _ensure_ready_signal(base)
    return _local_ready(base)
# ==================== [06] public: reindex — END ================================


# ================= [07] public: restore_or_attach — START =======================
def restore_or_attach(dest_dir: Optional[str | Path] = None) -> bool:
    """
    사용할 수 있는 인덱스를 보장:
      1) 로컬(.ready+chunks) 있으면 연결
      2) 없으면 GitHub Release에서 복원 시도
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    if _local_ready(base):
        _set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
        return True

    # 최신 릴리스 복원 시도(있을 때만)
    try:
        rel = importlib.import_module("src.backup.github_release")
        restore_latest = getattr(rel, "restore_latest", None)
    except Exception:
        restore_latest = None

    if callable(restore_latest):
        ok = False
        try:
            ok = bool(restore_latest(base))
        except Exception:
            ok = False
        if ok:
            _ensure_ready_signal(base)

    if _local_ready(base):
        _set_brain_status("READY", "릴리스 복구/연결 완료", "github", attached=True)
        return True

    _set_brain_status("MISSING", "복구/연결 실패(인덱스 없음)", "", attached=False)
    return False
# ================= [07] public: restore_or_attach — END =========================


# ===================== [08] public: attach_local — START =======================
def attach_local(dest_dir: str | Path) -> bool:
    """
    이미 인덱스가 있는 로컬 디렉터리를 세션에 '첨부'만 한다.
    (학생 모드에서도 안전하게 no-op 가능)
    """
    base = Path(dest_dir).expanduser()
    if not _local_ready(base):
        _set_brain_status("MISSING", "지정 경로에 사용 가능한 인덱스 없음", "local", False)
        return False

    # 세션 스탬프 공유(SSOT: core.persist가 우선 읽음)
    try:
        from src.core.persist import share_persist_dir_to_session
        share_persist_dir_to_session(base)
    except Exception:
        pass

    _set_brain_status("READY", "로컬 인덱스 연결됨", "local", True)
    return True
# ===================== [08] public: attach_local — END ==========================
