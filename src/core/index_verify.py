# ===== [01] FILE: src/core/index_verify.py — START =====
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional


def verify_persist_ready(persist: Path) -> Tuple[bool, str, Optional[int]]:
    """
    CLI와 동일 규칙:
      - chunks.jsonl 존재 & size > 0
      - .ready 내용 in {'ready', 'ok'}
    """
    try:
        persist = persist.expanduser().resolve()
        # 1) chunks.jsonl 찾기
        root = persist / "chunks.jsonl"
        chunks = None
        if root.exists() and root.stat().st_size > 0:
            chunks = root
        else:
            for p in persist.rglob("chunks.jsonl"):
                if p.is_file() and p.stat().st_size > 0:
                    chunks = p
                    break
        if chunks is None:
            return False, "missing chunks.jsonl", None
        size = chunks.stat().st_size

        # 2) .ready 검사
        ready = persist / ".ready"
        if not ready.exists():
            return False, "missing .ready", size
        raw = ""
        try:
            raw = ready.read_text(encoding="utf-8", errors="ignore").strip().lower()
        except Exception:
            raw = ""

        if raw in {"ready", "ok"}:
            return True, f"OK (.ready='{raw}', size={size})", size
        return False, f"mismatch .ready='{raw or '(empty)'}'", size
    except Exception as e:
        return False, f"error {e}", None
# ===== [01] FILE: src/core/index_verify.py — END =====
