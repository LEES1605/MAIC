# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

ASCII_READY = "ready"
# ============================= [01] imports & cfg — END =============================


# ============================ [02] helpers — START ==================================
def _effective_persist_dir(cli_dir: Optional[str]) -> Path:
    """
    SSOT 우선: src.core.persist.effective_persist_dir()
    실패 시: CLI 인자 → ~/.maic/persist 순으로 폴백.
    """
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    try:
        from src.core.persist import effective_persist_dir  # type: ignore
        p = effective_persist_dir()
        return p if isinstance(p, Path) else Path(str(p)).expanduser().resolve()
    except Exception:
        pass
    return (Path.home() / ".maic" / "persist").resolve()


def _check_ready(persist: Path) -> Tuple[bool, str]:
    """
    READY 판단 기준:
      - chunks.jsonl 존재 + 0바이트 초과
      - .ready 파일 내용이 'ready'
    """
    chunks = persist / "chunks.jsonl"
    ready = persist / ".ready"
    if not chunks.exists() or chunks.stat().st_size <= 0:
        return False, "chunks.jsonl missing or empty"
    try:
        txt = ready.read_text(encoding="utf-8").strip().lower()
    except Exception:
        txt = ""
    if txt != ASCII_READY:
        return False, f".ready != '{ASCII_READY}' (got: '{txt or 'EMPTY'}')"
    return True, "READY"
# ============================= [02] helpers — END ===================================


# ============================ [03] main — START =====================================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify index readiness in persist dir.")
    ap.add_argument("--persist", help="Persist dir (optional).")
    args = ap.parse_args(argv)

    persist = _effective_persist_dir(args.persist)
    ok, why = _check_ready(persist)

    print(f"[verify] persist = {persist}")
    print(f"[verify] status  = {why}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
# ============================= [03] main — END ======================================
