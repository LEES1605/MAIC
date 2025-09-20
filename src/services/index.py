# ============== [01] imports & notes — START ==============
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import importlib
import os

# 이 모듈은 *서비스 계층*입니다.
# - Persist 경로는 *항상* core.persist.effective_persist_dir()에서만 가져옵니다.
# - UI(app.py 등)는 이 모듈의 reindex()/restore_or_attach()/index_status()만 호출합니다.
# ============== [01] imports & notes — END ==============


# ============================ [02] persist helpers — START ===========================
from __future__ import annotations
from pathlib import Path

try:
    from src.core.readiness import mark_ready_if_chunks_exist
except Exception:
    def mark_ready_if_chunks_exist(p: Path) -> bool:  # type: ignore
        cj = p / "chunks.jsonl"
        if cj.exists() and cj.stat().st_size > 0:
            (p / ".ready").write_text("ready", encoding="utf-8")
            return True
        return False


def ensure_index_ready(persist_dir: Path) -> bool:
    """
    보조 유틸: chunks.jsonl이 있으면 '.ready'를 'ready'로 표준화.
    Returns True if successfully marked.
    """
    return mark_ready_if_chunks_exist(persist_dir)
# ============================= [02] persist helpers — END ============================


# ============== [03] index_status — START ==============
def index_status(p: Optional[Path] = None) -> Dict[str, Any]:
    base = p or _persist_dir()
    try:
        cj = _chunks(base)
        return {
            "persist_dir": str(base),
            "chunks_exists": cj.exists(),
            "chunks_size": (cj.stat().st_size if cj.exists() else 0),
            "ready_flag": _ready(base).exists(),
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
# ============== [03] index_status — END ==============


# ============== [04] reindex — START ==============
def reindex(dest_dir: str | Path | None = None) -> bool:
    """
    Build HQ index via src.rag.index_build.rebuild_index().
    Success: chunks.jsonl > 0 and .ready exists in the SSOT path.
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    try:
        mod = importlib.import_module("src.rag.index_build")
        fn = getattr(mod, "rebuild_index", None)
        if not callable(fn):
            return False
        fn(output_dir=base)  # 명시적 출력 경로
    except Exception:
        return False

    _ensure_ready(base)
    try:
        cj = _chunks(base)
        ok = bool(_ready(base).exists() and cj.exists() and cj.stat().st_size > 0)
        return ok
    except Exception:
        return False
# ============== [04] reindex — END ==============


# ============== [05] restore_or_attach — START ==============
def restore_or_attach(dest_dir: Optional[str | Path] = None) -> bool:
    """
    If local index ready → attach.
    Else try GitHub Releases restore (if integration is present).
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    if _local_ready(base):
        _set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
        return True

    # optional restore_latest()
    try:
        rel = importlib.import_module("src.backup.github_release")
        restore_latest = getattr(rel, "restore_latest", None)
    except Exception:
        restore_latest = None

    ok = False
    if callable(restore_latest):
        try:
            ok = bool(restore_latest(base))
        except Exception:
            ok = False

    if ok:
        _ensure_ready(base)
        _set_brain_status("READY", "릴리스 복원 완료", "release", attached=True)
        return True

    _set_brain_status("MISSING", "인덱스가 없습니다", "none", attached=False)
    return False
# ============== [05] restore_or_attach — END ==============


# ============== [06] streamlit session sync (optional) — START ==============
def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False) -> None:
    try:
        import streamlit as st  # optional dependency
    except Exception:
        return
    try:
        ss = st.session_state
        ss["brain_status_code"] = code
        ss["brain_status_msg"] = msg
        ss["brain_source"] = source
        ss["brain_attached"] = bool(attached)
        ss["restore_recommend"] = code in ("MISSING", "ERROR")
        ss.setdefault("index_decision_needed", False)
        ss.setdefault("index_change_stats", {})
    except Exception:
        pass
# ============== [06] streamlit session sync (optional) — END ==============
