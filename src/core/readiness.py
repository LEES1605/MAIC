# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

ASCII_READY = "ready"
# ============================= [01] imports & cfg — END =============================


# ============================ [02] SSOT helpers — START =============================
def effective_persist_dir(cli_hint: Optional[str] = None) -> Path:
    """
    SSOT 우선: src.core.persist.effective_persist_dir()
    실패 시: CLI 힌트 → ~/.maic/persist 순으로 폴백.
    """
    if cli_hint:
        return Path(cli_hint).expanduser().resolve()
    try:
        from src.core.persist import effective_persist_dir as _ssot  # type: ignore
        p = _ssot()
        return p if isinstance(p, Path) else Path(str(p)).expanduser().resolve()
    except Exception:
        return (Path.home() / ".maic" / "persist").resolve()
# ============================= [02] SSOT helpers — END ==============================


# ============================ [03] readiness API — START ============================
def check_ready(persist: Optional[Path] = None) -> Tuple[bool, str, Path]:
    """
    READY 판단 기준(통일):
      - chunks.jsonl 존재 + 0바이트 초과
      - .ready 파일 내용이 'ready'
    """
    base = persist or effective_persist_dir()
    chunks = base / "chunks.jsonl"
    ready = base / ".ready"

    if not chunks.exists() or chunks.stat().st_size <= 0:
        return False, "chunks.jsonl missing or empty", base
    try:
        txt = ready.read_text(encoding="utf-8").strip().lower()
    except Exception:
        txt = ""
    if txt != ASCII_READY:
        return False, f".ready != '{ASCII_READY}' (got: '{txt or 'EMPTY'}')", base
    return True, "READY", base
# ============================= [03] readiness API — END =============================
