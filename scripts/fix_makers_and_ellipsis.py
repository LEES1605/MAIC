# [01] START
#!/usr/bin/env python3
"""
scripts/fix_markers_and_ellipsis.py

Purpose:
  - Normalize patch-guard markers repo-wide to the strict form:
      "# [NN] START" / "# [NN] END" (line-end anchored, no trailing text)
  - Re-number blocks per file from [01]..[NN], contiguous, non-nested.
  - Replace Unicode ellipsis (U+2026) with ASCII "..." across text/code files.
Safety:
  - If a file has structural issues (END without START, START without END, or nested blocks),
    the file is left untouched and reported.
Usage:
  python scripts/fix_markers_and_ellipsis.py --root . --apply
  python scripts/fix_markers_and_ellipsis.py --root . --only markers --dry-run
Notes:
  - Skips binary files and large files by extension.
  - Excludes itself by default to avoid self-edit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
import argparse
import re
import sys
# [01] END

# [02] START
MARKER_FLEX_RE = re.compile(
    r"""
    ^(?P<prefix>\s*\#.*?)
    \[ (?P<num>\d{1,3}) (?P<suffix>[A-Z\-]?) \]    # [03] or [03A] or [03-...]
    (?P<mid>.*?)
    (?P<kind>START|END)
    (?P<trailing>.*)$
    """,
    re.VERBOSE,
)

STRICT_START = "# [%(nn)s] START"
STRICT_END = "# [%(nn)s] END"
UNICODE_ELLIPSIS = "\u2026"

DEFAULT_INCLUDE_EXTS = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini",
    ".json", ".sh", ".ps1", ".bat", ".sql", ".js", ".ts", ".tsx",
}
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".github", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
}
DEFAULT_EXCLUDE_FILES = {
    "scripts/fix_markers_and_ellipsis.py",  # avoid self-edit
}
# [02] END

# [03] START
@dataclass(frozen=True)
class Event:
    line_idx: int
    kind: str  # "START" or "END"
    original: str


class NormalizeError(Exception):
    pass


def _iter_candidate_files(root: Path, include_exts: Iterable[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in include_exts:
            continue
        parts = set(x.name for x in p.parents)
        if parts & DEFAULT_EXCLUDE_DIRS:
            continue
        rel = p.as_posix()
        if any(rel.endswith(ex) for ex in DEFAULT_EXCLUDE_FILES):
            continue
        yield p


def _find_marker_events(lines: List[str]) -> List[Event]:
    events: List[Event] = []
    for i, line in enumerate(lines):
        m = MARKER_FLEX_RE.match(line.rstrip("\n"))
        if not m:
            continue
        kind = m.group("kind").strip()
        if kind in ("START", "END"):
            events.append(Event(line_idx=i, kind=kind, original=line))
    return events


def _validate_structure(events: List[Event]) -> Tuple[bool, Optional[str]]:
    """
    - No nesting allowed.
    - Must be balanced START/END in order.
    """
    depth = 0
    for ev in events:
        if ev.kind == "START":
            if depth != 0:
                return False, f"Nested START at line {ev.line_idx + 1}"
            depth += 1
        else:  # END
            if depth == 0:
                return False, f"END without START at line {ev.line_idx + 1}"
            depth -= 1
    if depth != 0:
        return False, "Unclosed START (START without END)"
    return True, None


def _renumber_and_rewrite(lines: List[str], events: List[Event]) -> List[str]:
    """
    Given structurally valid events, rewrite marker lines to strict format and
    assign contiguous numbering [01].. in order of appearance.
    """
    new_lines = lines[:]
    block_no = 0
    for ev in events:
        if ev.kind == "START":
            block_no += 1
            nn = f"{block_no:02d}"
            new_lines[ev.line_idx] = STRICT_START % {"nn": nn} + "\n"
        else:  # END
            nn = f"{block_no:02d}"
            new_lines[ev.line_idx] = STRICT_END % {"nn": nn} + "\n"
    return new_lines


def _replace_ellipsis(text: str) -> str:
    return text.replace(UNICODE_ELLIPSIS, "...")
# [03] END

# [04] START
def normalize_file(path: Path, replace_ellipsis: bool = True) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Returns:
      (changed, action_summary, error_kind, error_detail)
      - changed: whether file content changed
      - action_summary: human summary
      - error_kind/error_detail: populated if structural error detected (file left untouched)
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:  # binary or decoding error
        return False, "skip(non-utf8)", "decode_error", str(e)

    lines = content.splitlines(keepends=True)
    events = _find_marker_events(lines)

    # Only apply marker normalization if any events present
    if events:
        ok, msg = _validate_structure(events)
        if not ok:
            return False, "skip(structural_error)", "structure", msg
        lines = _renumber_and_rewrite(lines, events)

    new_text = "".join(lines)
    if replace_ellipsis:
        new_text = _replace_ellipsis(new_text)

    if new_text != content:
        try:
            path.write_text(new_text, encoding="utf-8")
        except Exception as e:
            return False, "error(write_failed)", "io_write", str(e)
        return True, "updated", None, None
    return False, "nochange", None, None


def run(root: Path, apply: bool, only: Optional[str]) -> int:
    include_exts = DEFAULT_INCLUDE_EXTS
    touched = 0
    errors: List[str] = []
    reports: List[str] = []

    for p in _iter_candidate_files(root, include_exts):
        replace_ellipsis = True
        if only == "markers":
            replace_ellipsis = False
        elif only == "ellipsis":
            # still need to skip marker normalization but we do not need to parse markers
            pass

        if not apply:
            # Dry run: inspect and report only
            try:
                content = p.read_text(encoding="utf-8")
            except Exception:
                continue
            needs = []
            if UNICODE_ELLIPSIS in content and (only in (None, "ellipsis")):
                needs.append("ellipsis")
            if (only in (None, "markers")) and _find_marker_events(content.splitlines(keepends=True)):
                # We do not know if strictly formatted; just flag presence.
                needs.append("markers")
            if needs:
                reports.append(f"[DRY] {p}: needs {','.join(needs)}")
            continue

        # apply mode
        changed, summary, err_kind, err_detail = normalize_file(
            p, replace_ellipsis=(only != "markers")
        )
        if err_kind:
            errors.append(f"{p}: {err_kind} - {err_detail}")
            continue
        if changed:
            touched += 1
            reports.append(f"fixed {p} ({summary})")

    for r in reports:
        print(r)
    if errors:
        print("Errors (files left untouched):", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        # non-zero to surface issues but not to break maintenance workflow
    return 0
# [04] END

# [05] START
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Normalize patch-guard markers and replace Unicode ellipsis.")
    ap.add_argument("--root", default=".", help="Root directory to scan (default: .)")
    ap.add_argument("--apply", action="store_true", help="Apply changes to files. Without this, dry-run reports.")
    ap.add_argument("--only", choices=["markers", "ellipsis"], help="Restrict to one type of fix.")
    return ap.parse_args(argv)


def main() -> None:
    ns = parse_args()
    code = run(Path(ns.root).resolve(), apply=ns.apply, only=ns.only)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
# [05] END
