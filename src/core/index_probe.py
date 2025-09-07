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

# ========================= [03] probe & status core — START ========================
@dataclass(frozen=True)
class IndexHealth:
    persist: Path
    ready_exists: bool
    chunks_exists: bool
    chunks_size: int
    json_sample: int
    json_malformed: int
    mtime: int


def probe_index_health(persist: Optional[Path] = None, sample_lines: int = 200) -> IndexHealth:
    """Lightweight health probe for a built index directory (SSOT-based).

    Pure function (no Streamlit). Safe for services/tests/UI.

    Args:
        persist: Directory where `.ready` and `chunks.jsonl` are stored.
                 If None, resolved by core.persist.effective_persist_dir().
        sample_lines: How many lines to sample from `chunks.jsonl` to validate JSON.

    Returns:
        IndexHealth: flags/sizes/sample stats for quick readiness decision.
    """
    p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())

    chunks = p / "chunks.jsonl"
    ready = p / ".ready"

    chunks_exists = chunks.exists()
    size = chunks.stat().st_size if chunks_exists else 0
    ready_exists = ready.exists()
    mtime = int(chunks.stat().st_mtime) if chunks_exists else 0

    malformed = 0
    sampled = 0
    if chunks_exists and size > 0 and sample_lines > 0:
        try:
            with chunks.open("r", encoding="utf-8") as f:
                import json
                for i, line in enumerate(f):
                    if i >= sample_lines:
                        break
                    s = line.strip()
                    if not s:
                        continue
                    sampled += 1
                    try:
                        json.loads(s)
                    except Exception:
                        malformed += 1
        except Exception:
            # If the file can't be read, treat as no valid sample
            sampled = 0
            malformed = sample_lines

    return IndexHealth(
        persist=p,
        ready_exists=ready_exists,
        chunks_exists=chunks_exists,
        chunks_size=size,
        json_sample=sampled,
        json_malformed=malformed,
        mtime=mtime,
    )


def mark_ready(persist: Optional[Path] = None) -> None:
    """Create the `.ready` sentinel file (best-effort)."""
    p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())
    try:
        (p / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        # Best-effort; callers can re-check with is_brain_ready()
        pass


def is_brain_ready(persist: Optional[Path] = None) -> bool:
    """True iff `.ready` exists AND `chunks.jsonl` size > 0."""
    try:
        p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())
        if not p.exists():
            return False
        ready_ok = (p / ".ready").exists()
        chunks = p / "chunks.jsonl"
        chunks_ok = chunks.exists() and chunks.stat().st_size > 0
        return bool(ready_ok and chunks_ok)
    except Exception:
        return False


def get_brain_status(persist: Optional[Path] = None) -> Dict[str, str]:
    """Concise status for UI layers (pure/no-Streamlit)."""
    try:
        if is_brain_ready(persist):
            return {"code": "READY", "msg": "로컬 인덱스 연결됨(SSOT)"}
        return {"code": "MISSING", "msg": "인덱스 없음(관리자에서 '업데이트 점검' 필요)"}
    except Exception:
        return {"code": "MISSING", "msg": "상태 계산 실패"}
# ========================= [03] probe & status core — END ==========================
