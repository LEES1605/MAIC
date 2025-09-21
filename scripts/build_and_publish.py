# ===== [PATCH] FILE: scripts/build_and_publish.py — readiness probe — START =====
from __future__ import annotations
from pathlib import Path
from typing import Tuple
from src.core.readiness import is_ready_text

def _is_ready(persist_dir: Path) -> Tuple[bool, str]:
    """
    Return (ok, why). 'ok' is True if chunks.jsonl exists & non-empty and .ready text is valid.
    'why' explains first failure reason. (Contract restored for callers: ok, why = _is_ready(...))
    """
    chunks = persist_dir / "chunks.jsonl"
    ready  = persist_dir / ".ready"

    if not chunks.exists():
        return False, "chunks.jsonl not found"
    try:
        if chunks.stat().st_size <= 0:
            return False, "chunks.jsonl is empty"
    except Exception as e:
        return False, f"stat(chunks) failed: {e}"

    try:
        txt = ready.read_text(encoding="utf-8") if ready.exists() else ""
    except Exception as e:
        return False, f"read(.ready) failed: {e}"

    if not is_ready_text(txt):
        return False, "invalid .ready content"

    return True, "ok"
# ===== [PATCH] FILE: scripts/build_and_publish.py — readiness probe — END =====
