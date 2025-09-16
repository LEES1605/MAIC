# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
from pathlib import Path

ASCII_READY = "ready"
# ============================= [01] imports & cfg — END =============================


# ============================ [02] logic — START ====================================
def restore_and_verify(dest: Path, repo: str | None) -> int:
    """
    GitHub Release에서 최신 인덱스를 복원하고, READY 여부를 점검한다.
    """
    from src.backup.github_release import restore_latest  # (ignore 제거)

    dest.mkdir(parents=True, exist_ok=True)
    ok = restore_latest(dest, repo=repo)
    if not ok:
        print("[restore] restore_latest returned False")
        return 1

    chunks = dest / "chunks.jsonl"
    ready = dest / ".ready"
    if not chunks.exists() or chunks.stat().st_size <= 0:
        print("[verify] chunks.jsonl missing or empty")
        return 2
    try:
        txt = ready.read_text(encoding="utf-8").strip().lower()
    except Exception:
        txt = ""
    if txt != ASCII_READY:
        print(f"[verify] .ready != '{ASCII_READY}' (got: '{txt or 'EMPTY'}')")
        return 3

    print(f"[ok] restored to {dest} and READY")
    return 0
# ============================= [02] logic — END =====================================

# ============================ [03] main — START =====================================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Restore latest release and verify READY.")
    ap.add_argument("--repo", help="owner/repo (default: $GITHUB_REPO).")
    ap.add_argument("--dest", default="tmp_ready", help="destination directory.")
    args = ap.parse_args(argv)

    repo = args.repo or None
    code = restore_and_verify(Path(args.dest).expanduser().resolve(), repo)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
# ============================= [03] main — END ======================================
