# =========================== [01] imports & types — START ===========================
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from src.core.persist import effective_persist_dir
# =========================== [01] imports & types — END =============================

# ===================== [02] helpers (no Streamlit deps) — START ====================
def _ensure_dir(p: Path) -> Path:
    """Ensure directory exists (best-effort) and return it."""
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort only; callers will handle write failures later
        pass
    return p
# ===================== [02] helpers (no Streamlit deps) — END ======================
# ========================== [03] probe & status core — START =========================
from enum import Enum
from pathlib import Path
from typing import Optional

# ── 공용 헬퍼: 있으면 사용, 없으면 동일 동작의 폴백 제공 ────────────────
try:
    from src.core.readiness import (
        is_persist_ready as _is_persist_ready,
        mark_ready as _mark_ready,
        mark_ready_if_chunks_exist as _mark_ready_if_chunks_exist,
        is_ready_text as _is_ready_text,
    )
except Exception:
    def _norm_text(raw: str | bytes | None) -> str:
        if raw is None:
            return ""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "ignore")
        return raw.replace("\ufeff", "").strip().lower()

    def _is_ready_text(raw: str | bytes | None) -> bool:
        return _norm_text(raw) in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}

    def _is_persist_ready(persist_dir: Path) -> bool:
        p = Path(persist_dir)
        cj = p / "chunks.jsonl"
        rf = p / ".ready"
        try:
            txt = rf.read_text(encoding="utf-8") if rf.exists() else ""
        except Exception:
            txt = ""
        return (cj.exists() and cj.stat().st_size > 0) and _is_ready_text(txt)

    def _mark_ready(persist_dir: Path) -> None:
        (Path(persist_dir) / ".ready").write_text("ready", encoding="utf-8")

    def _mark_ready_if_chunks_exist(persist_dir: Path) -> bool:
        p = Path(persist_dir)
        cj = p / "chunks.jsonl"
        if cj.exists() and cj.stat().st_size > 0:
            _mark_ready(p)
            return True
        return False


class IndexHealth(str, Enum):
    """Index health status (string Enum for easy comparisons & JSON)."""
    MISSING = "missing"     # no chunks.jsonl or size==0
    PARTIAL = "partial"     # chunks present but .ready missing/invalid
    READY = "ready"         # chunks present and .ready is acceptable
    # ─ Aliases for broader compatibility ─
    OK = "ready"
    GREEN = "ready"
    INCOMPLETE = "partial"
    YELLOW = "partial"
    RED = "missing"


def is_persist_ready(persist_dir: Path) -> bool:
    """True if persist has non-empty chunks.jsonl and .ready is acceptable."""
    return _is_persist_ready(Path(persist_dir))


def mark_ready(persist_dir: Path) -> None:
    """Write canonical 'ready' into .ready file."""
    _mark_ready(Path(persist_dir))


def mark_ready_if_chunks_exist(persist_dir: Path) -> bool:
    """
    If chunks.jsonl exists and has content, mark '.ready' as 'ready'.
    Returns True if marking occurred.
    """
    return _mark_ready_if_chunks_exist(Path(persist_dir))


def probe_index_health(persist_dir: Path) -> IndexHealth:
    """
    Inspect persist directory and return IndexHealth.
    - MISSING: chunks.jsonl absent or size==0
    - PARTIAL: chunks.jsonl present but .ready missing or invalid (legacy not accepted)
    - READY  : chunks.jsonl present and .ready acceptable (ready/ok)
    """
    p = Path(persist_dir)
    cj = p / "chunks.jsonl"
    rf = p / ".ready"

    chunks_ok = cj.exists() and cj.stat().st_size > 0
    if not chunks_ok:
        return IndexHealth.MISSING

    ready_txt = ""
    try:
        ready_txt = rf.read_text(encoding="utf-8") if rf.exists() else ""
    except Exception:
        ready_txt = ""

    return IndexHealth.READY if _is_ready_text(ready_txt) else IndexHealth.PARTIAL


__all__ = [
    "IndexHealth",
    "is_persist_ready",
    "mark_ready",
    "mark_ready_if_chunks_exist",
    "probe_index_health",
]
# =========================== [03] probe & status core — END ==========================

