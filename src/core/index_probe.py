# =========================== [01] imports & types — START ===========================
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# =========================== [01] imports & types — END =============================

# ===================== [02] persist resolution helpers — START =====================
def _default_persist_dir() -> Path:
    """Resolve the *effective* persist directory.

    Lookup order (SSOT):
    1) src.rag.index_build.PERSIST_DIR
    2) src.config.PERSIST_DIR
    3) ~/.maic/persist

    Returns:
        Path: Expanded absolute path to the persist directory.
    """
    # 1) index_build.PERSIST_DIR (preferred)
    try:
        # Late import to avoid optional dependency at import-time
        from src.rag.index_build import PERSIST_DIR as IDX
        return Path(str(IDX)).expanduser()
    except Exception:
        pass

    # 2) config.PERSIST_DIR
    try:
        from src.config import PERSIST_DIR as CFG
        return Path(str(CFG)).expanduser()
    except Exception:
        pass

    # 3) fallback
    return Path.home() / ".maic" / "persist"


def _ensure_dir(p: Path) -> Path:
    """Make sure directory exists (best-effort) and return it."""
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Swallow: write operations will fail later and be handled
        pass
    return p
# ===================== [02] persist resolution helpers — END =======================

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
    """Lightweight health probe for a built index directory.

    This function is **pure** (no Streamlit dependency), so it can be used in
    services/tests as well as UI layers.

    Args:
        persist: The directory where `.ready` and `chunks.jsonl` live.
        sample_lines: How many lines to sample from `chunks.jsonl` to validate JSON.

    Returns:
        IndexHealth with basic metrics (exists flags, sizes, malformed count).
    """
    p = _ensure_dir(persist or _default_persist_dir())

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
                for i, line in enumerate(f):
                    if i >= sample_lines:
                        break
                    sampled += 1
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        import json  # local import to avoid global cost
                        json.loads(line)
                    except Exception:
                        malformed += 1
        except Exception:
            # If the file can't be read, treat all as malformed sample
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
    """Create the `.ready` sentinel file (best-effort).

    Safe to call multiple times. Directory will be created if missing.
    """
    p = _ensure_dir(persist or _default_persist_dir())
    try:
        (p / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        # Best-effort; callers can check `is_brain_ready` afterward
        pass


def is_brain_ready(persist: Optional[Path] = None) -> bool:
    """Return True iff both `.ready` exists *and* `chunks.jsonl` has size > 0."""
    p = _ensure_dir(persist or _default_persist_dir())
    try:
        if not p.exists():
            return False
        ready_ok = (p / ".ready").exists()
        chunks = p / "chunks.jsonl"
        chunks_ok = chunks.exists() and chunks.stat().st_size > 0
        return bool(ready_ok and chunks_ok)
    except Exception:
        return False


def get_brain_status(persist: Optional[Path] = None) -> Dict[str, str]:
    """Return a concise status code/message derived from the probe.

    Codes:
        - READY:    both `.ready` present and `chunks.jsonl` > 0B
        - MISSING:  otherwise (not ready yet / not built)

    Notes:
        UI layers (e.g., Streamlit) may override the displayed status via
        session-state. Keep this pure for reuse & tests.
    """
    try:
        if is_brain_ready(persist):
            return {"code": "READY", "msg": "로컬 인덱스 연결됨(SSOT)"}
        return {"code": "MISSING", "msg": "인덱스 없음(관리자에서 '업데이트 점검' 필요)"}
    except Exception:
        return {"code": "MISSING", "msg": "상태 계산 실패"}
# ========================= [03] probe & status core — END ==========================
