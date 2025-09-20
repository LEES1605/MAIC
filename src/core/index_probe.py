# =========================== [01] imports & types — START ===========================
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, Optional

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


# ─ Ready-text normalization & tolerant check ─
def _norm_ready_text(raw: str | bytes | None) -> str:
    """
    Normalize text for readiness check:
    - bytes -> utf-8 decode (ignore errors)
    - strip whitespace
    - remove BOM (\ufeff)
    - lowercase
    """
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    return raw.replace("\ufeff", "").strip().lower()


def _is_ready_text(raw: str | bytes | None) -> bool:
    """Return True if raw text indicates 'ready' (legacy values accepted)."""
    return _norm_ready_text(raw) in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}
# ===================== [02] helpers (no Streamlit deps) — END ======================

# ========================= [03] probe & status core — START ========================
@dataclass(frozen=True)
class IndexHealth:
    """Lightweight snapshot of index condition (for services/tests/UI)."""
    persist: Path
    ready_exists: bool
    chunks_exists: bool
    chunks_size: int
    json_sample: int
    json_malformed: int
    mtime: int

    # Pseudo-enum constants for compatibility (e.g., IndexHealth.MISSING)
    READY: ClassVar[str] = "ready"
    PARTIAL: ClassVar[str] = "partial"
    MISSING: ClassVar[str] = "missing"


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
            import json
            with chunks.open("r", encoding="utf-8") as f:
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
    """Create/normalize the `.ready` sentinel file (best-effort, canonical 'ready')."""
    p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())
    try:
        (p / ".ready").write_text("ready", encoding="utf-8")  # canonical
    except Exception:
        # Best-effort; callers can re-check with is_brain_ready()
        pass


def mark_ready_if_chunks_exist(persist: Optional[Path] = None) -> bool:
    """
    If chunks.jsonl exists and has size>0, ensure '.ready' is 'ready'.
    Returns True if marked or already 'ready', False if chunks missing or write failed.
    """
    p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())
    try:
        cj = p / "chunks.jsonl"
        if cj.exists() and cj.stat().st_size > 0:
            mark_ready(p)
            return True
        return False
    except Exception:
        return False


def is_persist_ready(persist: Optional[Path] = None) -> bool:
    """
    True iff `.ready` contains an acceptable value (ready/ok/…) AND `chunks.jsonl` size > 0.
    """
    try:
        p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())
        if not p.exists():
            return False
        ready_path = p / ".ready"
        chunks = p / "chunks.jsonl"
        chunks_ok = chunks.exists() and chunks.stat().st_size > 0
        ready_txt = ""
        if ready_path.exists():
            try:
                ready_txt = ready_path.read_text(encoding="utf-8")
            except Exception:
                ready_txt = ""
        return bool(chunks_ok and _is_ready_text(ready_txt))
    except Exception:
        return False


def is_brain_ready(persist: Optional[Path] = None) -> bool:
    """Back-compat alias; same semantics as is_persist_ready()."""
    return is_persist_ready(persist)


def get_brain_status(persist: Optional[Path] = None) -> Dict[str, str]:
    """Concise status for UI layers (pure/no-Streamlit)."""
    try:
        # 유지: READY/MISSING만 노출(내부 판정은 강화됨)
        ok = is_persist_ready(persist)
    except Exception:
        return {"code": "MISSING", "msg": "상태 계산 실패"}

    if ok:
        return {"code": "READY", "msg": "로컬 인덱스 연결됨(SSOT)"}
    return {"code": "MISSING", "msg": "인덱스 없음(관리자에서 '업데이트 점검' 필요)"}


__all__ = [
    "IndexHealth",
    "probe_index_health",
    "mark_ready",
    "mark_ready_if_chunks_exist",
    "is_persist_ready",
    "is_brain_ready",
    "get_brain_status",
]
# ========================= [03] probe & status core — END ==========================

