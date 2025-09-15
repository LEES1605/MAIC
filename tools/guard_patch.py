# ========================= [01] imports & constants — START =========================
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

ELLIPSIS_CHAR = "\u2026"  # forbidden
MARKER_RE = re.compile(r"\[\s*(\d{2})\s*\].*\b(START|END)\b", re.IGNORECASE)

# git diff hunk header example:
# @@ -old_start,old_len +new_start,new_len @@
HUNK_RE = re.compile(r"^@@\s*-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")

# ========================== [01] imports & constants — END ==========================


# ============================ [02] cli arguments — START ===========================
@dataclass(frozen=True)
class Args:
    base: str
    head: str
    paths: Tuple[str, ...]


def _parse_args(argv: Optional[Sequence[str]] = None) -> Args:
    p = argparse.ArgumentParser(prog="guard_patch")
    p.add_argument("--base", required=True, help="base commit sha")
    p.add_argument("--head", required=True, help="head commit sha")
    p.add_argument(
        "paths",
        nargs="*",
        help="optional path filters. if empty, all changed files are checked",
    )
    a = p.parse_args(argv)
    return Args(base=a.base, head=a.head, paths=tuple(a.paths or ()))
# ============================= [02] cli arguments — END ============================


# ============================== [03] git helpers — START ===========================
def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return out.stdout


def _changed_files(base: str, head: str, paths: Sequence[str]) -> List[str]:
    cmd = ["diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base}..{head}"]
    if paths:
        cmd.extend(list(paths))
    out = _git(*cmd)
    files = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return files


def _file_text_at(commit: str, path: str) -> str:
    # head에는 항상 존재. base에는 없을 수 있으므로 실패는 빈 문자열 처리.
    try:
        out = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if out.returncode != 0:
            return ""
        return out.stdout
    except Exception:
        return ""


def _changed_line_numbers(base: str, head: str, path: str) -> Set[int]:
    # 신버전 파일 전체 추가도 안전히 처리됨.
    cmd = ["diff", "-U0", f"{base}..{head}", "--", path]
    out = _git(*cmd)
    lines: Set[int] = set()
    for ln in out.splitlines():
        m = HUNK_RE.match(ln)
        if not m:
            continue
        start = int(m.group(1))
        length = int(m.group(2) or "1")
        for off in range(length or 1):
            lines.add(start + off)
    return lines
# =============================== [03] git helpers — END ============================


# ============================ [04] marker validators — START =======================
@dataclass(frozen=True)
class Marker:
    ident: int
    kind: str  # "START" or "END"
    line_no: int


def _scan_markers(text: str) -> List[Marker]:
    out: List[Marker] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        m = MARKER_RE.search(raw)
        if not m:
            continue
        ident = int(m.group(1))
        kind = m.group(2).upper()
        out.append(Marker(ident=ident, kind=kind, line_no=i))
    return out


def _validate_blocks(markers: Sequence[Marker]) -> List[str]:
    """완화된 v2: 숫자 구획만 검증(균형·순차)."""
    errs: List[str] = []
    if not markers:
        return errs

    # 1) START/END 균형(스택)
    stack: List[Marker] = []
    for m in markers:
        if m.kind == "START":
            stack.append(m)
            continue
        # END
        if not stack:
            errs.append(
                f"END without START at line {m.line_no} (block {m.ident:02d})"
            )
            continue
        prev = stack.pop()
        if prev.ident != m.ident:
            msg = (
                f"mismatched END: got {m.ident:02d} at {m.line_no}, "
                f"expected {prev.ident:02d} (START {prev.line_no})"
            )
            errs.append(msg)
    if stack:
        top = stack[-1]
        errs.append(
            f"unterminated START at line {top.line_no} (block {top.ident:02d})"
        )

    # 2) 숫자 구획 순차(01부터 1씩 증가, 중복 금지)
    starts = [m.ident for m in markers if m.kind == "START"]
    if starts:
        uniq = sorted(set(starts))
        expect = list(range(1, len(uniq) + 1))
        if uniq[0] != 1:
            errs.append(
                f"non-sequential block number: got {uniq[0]}, expect 1"
            )
        if uniq != expect:
            errs.append(
                f"block numbers must be 01..{expect[-1]:02d} without gaps"
            )
    return errs
# ============================= [04] marker validators — END ========================


# =============================== [05] file checks — START ==========================
def _check_no_ellipsis(head_text: str, changed_lines: Set[int]) -> List[str]:
    """U+2026(…) 금지. 변경 라인에서만 검사."""
    errs: List[str] = []
    if not changed_lines:
        return errs
    rows = head_text.splitlines()
    for i in changed_lines:
        if 1 <= i <= len(rows):
            if ELLIPSIS_CHAR in rows[i - 1]:
                errs.append(
                    f"Unicode ellipsis (U+2026) forbidden at line {i}"
                )
    return errs


def _check_file(base: str, head: str, path: str) -> List[str]:
    head_text = _file_text_at(head, path)
    if not head_text:
        return []

    changed = _changed_line_numbers(base, head, path)
    errors: List[str] = []

    # a) 금지 문자
    for e in _check_no_ellipsis(head_text, changed):
        errors.append(f"{path}: {e}")

    # b) 숫자 구획(있을 때만 적용)
    markers = _scan_markers(head_text)
    if markers:
        for e in _validate_blocks(markers):
            errors.append(f"{path}: {e}")

    return errors
# ================================ [05] file checks — END ===========================


# ================================= [06] main — START ===============================
def main(argv: Optional[Sequence[str]] = None) -> int:
    a = _parse_args(argv)
    files = _changed_files(a.base, a.head, a.paths)

    all_errs: List[str] = []
    for p in files:
        all_errs.extend(_check_file(a.base, a.head, p))

    if all_errs:
        print("[patch-guard] FAIL")
        for e in all_errs:
            print(f" - {e}")
        return 1

    print("[patch-guard] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# ================================== [06] main — END ================================
