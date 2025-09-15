# [01] START
#!/usr/bin/env python3
"""
scripts/hotfix_patch_guard.py

Normalize patch-guard END lines and auto-close a trailing unmatched START.

- Rewrite any marker END line to the strict form: "# [NNX] END" (line-end).
- If the last marker is a START, append a matching "# [NNX] END" at EOF.
- No renumbering is performed; original identifiers are preserved.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
import argparse
import re
import sys
# [01] END

# [02] START
MARK_RE = re.compile(
    r"^\s*\#.*\[\s*(?P<num>\d{2})(?P<suf>[A-Z]?)\s*\].*?(?P<edge>START|END)\s*(?P<trail>.*)$",
    re.IGNORECASE,
)

STRICT = {
    "START": "# [%(ident)s] START",
    "END": "# [%(ident)s] END",
}

INCLUDE_EXTS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini",
    ".json", ".sh", ".ps1", ".bat",
}
EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
# [02] END

# [03] START
@dataclass(frozen=True)
class Event:
    idx: int
    ident: str   # "03" or "03A"
    kind: str    # "START" or "END"


def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in INCLUDE_EXTS:
            continue
        if set(x.name for x in p.parents) & EXCLUDE_DIRS:
            continue
        yield p


def parse_events(lines: List[str]) -> List[Event]:
    evs: List[Event] = []
    for i, s in enumerate(lines):
        m = MARK_RE.match(s.rstrip("\n"))
        if not m:
            continue
        ident = (m.group("num") + (m.group("suf") or "")).upper()
        edge = m.group("edge").upper()
        evs.append(Event(idx=i, ident=ident, kind=edge))
    return evs
# [03] END

# [04] START
def normalize_markers(text: str) -> Tuple[str, bool]:
    changed = False
    lines = text.splitlines(keepends=True)
    evs = parse_events(lines)

    # 1) END 라인을 정규형으로 교체
    for ev in evs:
        if ev.kind != "END":
            continue
        new_line = STRICT["END"] % {"ident": ev.ident} + "\n"
        if lines[ev.idx].rstrip("\n") != new_line.rstrip("\n"):
            lines[ev.idx] = new_line
            changed = True

    # 2) 파일 마지막 이벤트가 START면 EOF에 END 삽입(안전 케이스)
    if evs and evs[-1].kind == "START":
        lines.append(STRICT["END"] % {"ident": evs[-1].ident} + "\n")
        changed = True

    return "".join(lines), changed


def run(root: Path, apply: bool) -> int:
    touched = 0
    for p in iter_files(root):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        new_text, changed = normalize_markers(text)
        if not changed:
            continue
        if not apply:
            print(f"[DRY] would fix {p}")
            continue
        try:
            p.write_text(new_text, encoding="utf-8")
            touched += 1
            print(f"fixed {p}")
        except Exception as e:
            print(f"error writing {p}: {e}", file=sys.stderr)
    print(f"done. changed={touched}")
    return 0
# [04] END

# [05] START
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Hotfix patch-guard markers.")
    ap.add_argument("--root", default=".", help="Project root (default: .)")
    ap.add_argument("--apply", action="store_true", help="Apply changes. Default: dry-run.")
    return ap.parse_args(argv)


def main() -> None:
    ns = parse_args()
    code = run(Path(ns.root).resolve(), apply=ns.apply)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
# [05] END
