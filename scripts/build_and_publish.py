# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

ASCII_READY = "ready"
# ============================= [01] imports & cfg — END =============================


# ============================ [02] core logic — START ==============================
def _build_index(mode: str | None) -> int:
    """
    인덱스를 빌드한다.
    - mode: 'HQ' 또는 'STD' (None은 환경변수 유지)
    - 성공 시 생성된 chunks 수를 반환, 실패/0개면 0
    """
    if mode:
        os.environ["MAIC_INDEX_MODE"] = mode
    try:
        from src.rag.index_build import rebuild_index  # uses SSOT persist
    except Exception as e:
        print(f"[build] import failed: {e}")
        return 0

    try:
        result = rebuild_index(output_dir=None)
        cnt = int(result.get("chunks") or 0)
        print(f"[build] chunks: {cnt}")
        return cnt
    except Exception as e:
        print(f"[build] rebuild_index error: {e}")
        return 0


def _publish_release(persist: Path, repo: Optional[str]) -> bool:
    """
    퍼시스트 디렉토리를 zip으로 묶어 GitHub Release로 업로드한다.
    """
    try:
        from src.backup.github_release import publish_backup  # uses urllib
    except Exception as e:
        print(f"[release] import failed: {e}")
        return False

    try:
        ok = publish_backup(persist_dir=persist, repo=repo)
        return bool(ok)
    except Exception as e:
        print(f"[release] publish_backup error: {e}")
        return False


def _effective_persist() -> Path:
    """
    SSOT 우선: src.core.persist.effective_persist_dir() → 전역/폴백
    """
    try:
        from src.core.persist import effective_persist_dir
        p = effective_persist_dir()
        return p if isinstance(p, Path) else Path(str(p)).expanduser().resolve()
    except Exception:
        pass
    return (Path.home() / ".maic" / "persist").resolve()


def _is_ready(persist: Path) -> tuple[bool, str]:
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
# ============================= [02] core logic — END ===============================


# ============================ [03] main — START =====================================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build local RAG index and publish as GitHub Release."
    )
    ap.add_argument("--mode", choices=["STD", "HQ"], help="Indexing mode.")
    ap.add_argument("--repo", help="owner/repo (default: env autodetect).")
    ap.add_argument(
        "--skip-publish",
        action="store_true",
        help="Build only, do not publish a release.",
    )
    args = ap.parse_args(argv)

    persist = _effective_persist()
    cnt = _build_index(args.mode)
    if cnt <= 0:
        print("[build] no chunks produced")
        return 1

    # mark ready if missing
    ok, why = _is_ready(persist)
    if not ok:
        try:
            (persist / ".ready").write_text(ASCII_READY, encoding="utf-8")
            print("[build] wrote .ready=ready")
        except Exception:
            print("[build] failed to write .ready")

    if args.skip_publish:
        print("[ok] build-only finished")
        return 0

    repo = args.repo or None
    if not _publish_release(persist, repo):
        return 2

    print("[ok] build and publish finished")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
# ============================= [03] main — END ======================================
