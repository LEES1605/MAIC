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
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    # 공용 헬퍼(신규)
    from src.core.readiness import mark_ready, is_persist_ready
except Exception:
    # 폴백(동일 로직)
    def mark_ready(persist_dir: Path) -> None:  # type: ignore
        (persist_dir / ".ready").write_text("ready", encoding="utf-8")

    def is_persist_ready(persist_dir: Path) -> bool:  # type: ignore
        cj = persist_dir / "chunks.jsonl"
        rf = persist_dir / ".ready"
        try:
            txt = rf.read_text(encoding="utf-8") if rf.exists() else ""
        except Exception:
            txt = ""
        txt = txt.replace("\ufeff", "").strip().lower()
        return (cj.exists() and cj.stat().st_size > 0) and (txt in {"ready", "ok", "true", "1", "on", "yes", "y", "green"})


def mark_ready_if_chunks_exist(persist_dir: Path) -> bool:
    """chunks.jsonl 존재 시, 표준 'ready' 기록."""
    cj = persist_dir / "chunks.jsonl"
    if cj.exists() and cj.stat().st_size > 0:
        mark_ready(persist_dir)
        return True
    return False
# =========================== [03] probe & status core — END ==========================
