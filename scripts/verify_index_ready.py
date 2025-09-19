# ============================ [01] FILE: scripts/verify_index_ready.py — START =======================
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

ASCII_READY = "ready"


# ============================= [02] helpers — START ==================================
def _effective_persist_dir(cli_dir: Optional[str]) -> Path:
    """
    SSOT 우선: src.core.persist.effective_persist_dir()
    실패 시: CLI 인자 → ~/.maic/persist 순으로 폴백.
    """
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    try:
        # SSOT: 앱이 사용하는 헬퍼와 동일 경로 사용
        from src.core.persist import effective_persist_dir
        p = effective_persist_dir()
        return p if isinstance(p, Path) else Path(str(p)).expanduser().resolve()
    except Exception:
        pass
    return (Path.home() / ".maic" / "persist").resolve()


def _check_ready(persist: Path) -> Tuple[bool, str]:
    """
    검증 규칙(호환성 유지):
      - chunks.jsonl이 존재하고 0바이트 초과일 것(루트 우선, 없으면 하위 탐색).
      - .ready 내용은 { "ready", "ok" } 둘 다 허용.
        · 이유: 앱의 자동 복원 경로는 'ok'로 표기될 수 있고, 릴리스 복원은 'ready'를 씀.
    """
    try:
        # 1) chunks.jsonl 탐색 (루트 우선, 없으면 rglob)
        root_chunks = persist / "chunks.jsonl"
        chunks = None
        if root_chunks.exists() and root_chunks.stat().st_size > 0:
            chunks = root_chunks
        else:
            for p in persist.rglob("chunks.jsonl"):
                if p.is_file() and p.stat().st_size > 0:
                    chunks = p
                    break
        if chunks is None:
            return False, "missing: chunks.jsonl"

        # 2) .ready 검사
        ready_path = persist / ".ready"
        if not ready_path.exists():
            return False, "missing: .ready"

        raw = ""
        try:
            raw = ready_path.read_text(encoding="utf-8", errors="ignore").strip().lower()
        except Exception:
            raw = ""

        ok_values = {ASCII_READY, "ok"}  # 'ready'·'ok' 허용 (앱/릴리스 경로 혼재 대응)
        if raw in ok_values:
            return True, f"OK: chunks.jsonl exists & .ready='{raw}'"
        return False, f"mismatch: .ready='{raw or '(empty)'}' (expected 'ready' or 'ok')"
    except Exception as e:
        return False, f"error: {e}"
# ============================== [02] helpers — END ===================================


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
# ============================= [03] FILE: scripts/verify_index_ready.py — END =======================
