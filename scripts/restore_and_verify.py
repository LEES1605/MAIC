# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
from pathlib import Path

ASCII_READY = "ready"
# ============================= [01] imports & cfg — END =============================


# ================================ [02] logic — START =================================
from __future__ import annotations
from pathlib import Path

try:
    from src.core.readiness import is_persist_ready, normalize_ready_file
except Exception:
    def is_persist_ready(p: Path) -> bool:  # type: ignore
        cj = p / "chunks.jsonl"
        rf = p / ".ready"
        if not (cj.exists() and cj.stat().st_size > 0 and rf.exists()):
            return False
        txt = rf.read_text(encoding="utf-8")
        txt = txt.replace("\ufeff", "").strip().lower()
        return txt in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}

    def normalize_ready_file(_: Path) -> bool:  # type: ignore
        try:
            (_ / ".ready").write_text("ready", encoding="utf-8")
            return True
        except Exception:
            return False


def restore_and_verify(persist_dir: Path) -> bool:
    """
    Restore was performed prior to this call. Here we only verify and normalize.
    """
    ok = is_persist_ready(persist_dir)
    if ok:
        # 표준화 보장
        normalize_ready_file(persist_dir)
    return ok
# ================================= [02] logic — END ==================================

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
