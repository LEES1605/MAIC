# ===== FILE: src/core/readiness.py ============================================
# [01] imports & constants — START
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Union

# 허용 값(정규화 후)
_READY_VALUES = {"ready", "ok", "true", "1", "on", "yes", "y", "green"}
# [01] imports & constants — END
# -----------------------------------------------------------------------------

# [02] text normalization & checks — START
def _norm_text(raw: str | bytes | None) -> str:
    """
    Normalize text for readiness check:
    - bytes -> utf-8 decode (ignore errors)
    - strip whitespace
    - remove BOM
    - lowercase
    """
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    raw = raw.replace("\ufeff", "")  # BOM 제거
    return raw.strip().lower()


def is_ready_text(raw: str | bytes | None) -> bool:
    """Return True if raw text indicates 'ready' state (including legacy values)."""
    return _norm_text(raw) in _READY_VALUES
# [02] text normalization & checks — END
# -----------------------------------------------------------------------------

# [03] file helpers — START
PathLike = Union[str, Path]


def _ensure_path_to_file(p: Path) -> None:
    """Ensure parent dir exists for a file path."""
    p.parent.mkdir(parents=True, exist_ok=True)


def ready_file_of(path_or_dir: PathLike) -> Path:
    """Map a dir-or-file input to the canonical '.ready' file path."""
    p = Path(path_or_dir)
    return p / ".ready" if p.is_dir() else p


def read_ready_file(path_or_dir: PathLike) -> str:
    """
    Read and normalize the content of '.ready'.
    Returns normalized lowercase string (BOM trimmed), or '' if missing/failed.
    """
    p = ready_file_of(path_or_dir)
    try:
        return _norm_text(p.read_text(encoding="utf-8"))
    except Exception:
        return ""


def normalize_ready_file(path_or_dir: PathLike) -> bool:
    """
    Write canonical 'ready' into '.ready'. Returns True on success.
    """
    p = ready_file_of(path_or_dir)
    try:
        _ensure_path_to_file(p)
        p.write_text("ready", encoding="utf-8")
        return True
    except Exception:
        return False
# [03] file helpers — END
# -----------------------------------------------------------------------------

# [04] persist-level helpers — START
def is_persist_ready(persist_dir: PathLike) -> bool:
    """
    Persist is 'ready' if:
      - chunks.jsonl exists and size > 0
      - .ready contains a value accepted by is_ready_text()
    """
    p = Path(persist_dir)
    cj = p / "chunks.jsonl"
    if not (cj.exists() and cj.stat().st_size > 0):
        return False
    return is_ready_text(read_ready_file(p / ".ready"))


def mark_ready(persist_dir: PathLike) -> None:
    """Mark persist as 'ready' (canonical)."""
    normalize_ready_file(persist_dir)


def mark_ready_if_chunks_exist(persist_dir: PathLike) -> bool:
    """
    If chunks.jsonl exists with size>0, ensure '.ready' is 'ready'.
    Returns True if marked, False if chunks missing or write failed.
    """
    p = Path(persist_dir)
    cj = p / "chunks.jsonl"
    if cj.exists() and cj.stat().st_size > 0:
        return normalize_ready_file(p)
    return False
# [04] persist-level helpers — END
# ============================================================================

