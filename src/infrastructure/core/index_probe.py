# ===== [01] FILE: src/core/index_probe.py — START =====
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from src.infrastructure.core.persist import effective_persist_dir
from src.infrastructure.core.readiness import is_ready_text, normalize_ready_file


# ──────────────────────────────── helpers ─────────────────────────────────────
def _ensure_dir(p: Path) -> Path:
    """Ensure directory exists (best-effort) and return it."""
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


# ──────────────────────────────── model ───────────────────────────────────────
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

    @property
    def ok(self) -> bool:
        """
        True when persist dir has ready marker + valid chunks.
        샘플 검증(json_sample/json_malformed)은 '실행한 경우에만' 판정에 반영.
        """
        if not (self.ready_exists and self.chunks_exists and self.chunks_size > 0):
            return False
        try:
            txt = (self.persist / ".ready").read_text(encoding="utf-8")
        except Exception:
            txt = ""
        if not is_ready_text(txt):
            return False
        if self.json_sample > 0 and self.json_malformed > 0:
            return False
        return True


# ──────────────────────────────── probe ───────────────────────────────────────
def probe_index_health(persist: Optional[Path] = None, sample_lines: int = 200) -> IndexHealth:
    """
    Lightweight health probe for a built index directory (pure/no-Streamlit).
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


# ──────────────────────────────── readiness API ───────────────────────────────
def mark_ready(persist: Optional[Path] = None) -> None:
    """Create/normalize the `.ready` sentinel file (best-effort, canonical 'ready')."""
    p = _ensure_dir(Path(persist) if isinstance(persist, Path) else effective_persist_dir())
    try:
        normalize_ready_file(p)
    except Exception:
        pass


def is_persist_ready(persist: Optional[Path] = None) -> bool:
    """
    True iff `.ready` text is valid and `chunks.jsonl` size > 0.
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
        return bool(chunks_ok and is_ready_text(ready_txt))
    except Exception:
        return False


def is_brain_ready(persist: Optional[Path] = None) -> bool:
    """Back-compat alias; same semantics as is_persist_ready()."""
    return is_persist_ready(persist)


def get_brain_status(persist: Optional[Path] = None) -> Dict[str, str]:
    """Concise status for UI layers (pure/no-Streamlit)."""
    try:
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
    "is_persist_ready",
    "is_brain_ready",
    "get_brain_status",
]
# ===== [01] FILE: src/core/index_probe.py — END =====
