# [01] imports START
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import importlib
# [01] END


# [02] persist resolver START
def _persist_dir() -> Path:
    try:
        from src.core.persist import effective_persist_dir as _ssot
        p = _ssot()
        return p if isinstance(p, Path) else Path(str(p)).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"
# [02] END


# [03] helpers START
def _chunks_path(p: Path) -> Path:
    return p / "chunks.jsonl"


def _ready_path(p: Path) -> Path:
    return p / ".ready"


def _local_ready(p: Optional[Path] = None) -> bool:
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        return _ready_path(base).exists() and cj.exists() and cj.stat().st_size > 0
    except Exception:
        return False


def _ensure_ready_signal(p: Optional[Path] = None) -> None:
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        r = _ready_path(base)
        if cj.exists() and cj.stat().st_size > 0 and not r.exists():
            r.write_text("ok", encoding="utf-8")
    except Exception:
        pass


def _set_brain_status(
    code: str, msg: str = "", source: str = "", attached: bool = False
) -> None:
    try:
        import streamlit as st  # lazy
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
# [03] END


# [04] public: index_status START
def index_status(p: Optional[Path] = None) -> Dict[str, Any]:
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
# [04] END


# [05] public: reindex START
def reindex(dest_dir: Optional[str | Path] = None) -> bool:
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    try:
        mod = importlib.import_module("src.rag.index_build")
        fn = getattr(mod, "rebuild_index", None)
        if not callable(fn):
            return False
        fn(output_dir=base)
    except Exception:
        return False
    _ensure_ready_signal(base)
    try:
        cj = base / "chunks.jsonl"
        size = cj.stat().st_size if cj.exists() else 0
        ok = bool((base / ".ready").exists() and cj.exists() and size > 0)
        return ok
    except Exception:
        return False
# [05] END


# [06] public: restore_or_attach START
def restore_or_attach(dest_dir: Optional[str | Path] = None) -> bool:
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    if _local_ready(base):
        _set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
        return True
    try:
        gh = importlib.import_module("src.backup.github_release")
        restore_latest = getattr(gh, "restore_latest", None)
    except Exception:
        restore_latest = None
    restored_ok = False
    if callable(restore_latest):
        try:
            restored_ok = bool(restore_latest(base))
        except Exception:
            restored_ok = False
    _ensure_ready_signal(base)
    if _local_ready(base) or restored_ok:
        _set_brain_status("READY", "릴리스 복원 완료", "release", attached=True)
        return True
    _set_brain_status("MISSING", "인덱스 없음", "none", attached=False)
    return False
# [06] END
