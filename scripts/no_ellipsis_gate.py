# [01] START
#!/usr/bin/env python3
"""
scripts/no_ellipsis_gate.py

Fail CI if Unicode ellipsis (U+2026) appears in code files.
Use --fix to replace it with ASCII "...".
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple
import argparse
import sys

TARGET = "\u2026"  # do NOT use the literal char in this file

INCLUDE_EXTS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".sh", ".bat", ".ps1",
}
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", "docs",
}
EXCLUDE_FILES = {"prompts.yaml"}
# [01] END

# [02] START
def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in INCLUDE_EXTS:
            continue
        if set(x.name for x in p.parents) & EXCLUDE_DIRS:
            continue
        if p.name in EXCLUDE_FILES:
            continue
        yield p


def scan_file(p: Path) -> List[Tuple[int, int]]:
    locs: List[Tuple[int, int]] = []
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return locs
    idx = 0
    while True:
        found = text.find(TARGET, idx)
        if found == -1:
            break
        line = text.count("\n", 0, found) + 1
        col = found - (text.rfind("\n", 0, found) + 1)
        locs.append((line, col))
        idx = found + 1
    return locs
# [02] END

# [03] START
def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fail CI on U+2026 (Unicode ellipsis) inside code files.")
    ap.add_argument("--root", default=".", help="Root directory to scan (default: .)")
    ap.add_argument("--fix", action="store_true", help="Replace with ASCII '...' in-place.")
    return ap.parse_args(argv)


def main() -> None:
    ns = parse_args()
    root = Path(ns.root).resolve()
    bad: List[str] = []
    fixed = 0

    for p in iter_files(root):
        locs = scan_file(p)
        if not locs:
            continue
        if ns.fix:
            try:
                t = p.read_text(encoding="utf-8").replace(TARGET, "...")
                p.write_text(t, encoding="utf-8")
                fixed += 1
            except Exception as e:
                bad.append(f"{p}: fix failed: {e}")
                continue
        else:
            msg = ", ".join([f"L{ln}:{co}" for (ln, co) in locs[:5]])
            more = "" if len(locs) <= 5 else f" (+{len(locs)-5} more)"
            bad.append(f"{p}: found at {msg}{more}")

    if ns.fix:
        print(f"Replaced ellipsis in {fixed} file(s).")

    if bad and not ns.fix:
        print("Unicode ellipsis (U+2026) found in:", file=sys.stderr)
        for b in bad:
            print(" -", b, file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
# [03] END
