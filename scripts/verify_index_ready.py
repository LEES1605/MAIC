# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

ASCII_READY = "ready"
# ============================= [01] imports & cfg — END =============================

# ============================ [02] helpers — START ==================================
def _check_ready(persist: Path) -> tuple[bool, str]:
    """
    준비 상태 판단:
      - chunks.jsonl 존재 & 크기 > 0
      - .ready 파일의 내용이 ASCII "ready"
    """
    try:
        cj = persist / "chunks.jsonl"
        r = persist / ".ready"

        has_chunks = cj.exists() and cj.stat().st_size > 0
        ready_text = ""
        if r.exists():
            try:
                ready_text = r.read_text(encoding="utf-8").strip().lower()
            except Exception:
                ready_text = ""

        ok = has_chunks and (ready_text == ASCII_READY)
        if ok:
            return True, f"READY · chunks={cj.stat().st_size} bytes"
        reasons = []
        if not cj.exists():
            reasons.append("no chunks.jsonl")
        elif cj.stat().st_size <= 0:
            reasons.append("chunks.jsonl empty")
        if ready_text != ASCII_READY:
            reasons.append(f".ready='{ready_text or ''}'")
        return False, " / ".join(reasons) if reasons else "unknown"
    except Exception as e:
        return False, f"error: {e}"
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
