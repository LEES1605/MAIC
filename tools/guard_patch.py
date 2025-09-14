# [01] START: tools/guard_patch.py
from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

MONITORED_EXTS = {".py", ".md", ".yaml", ".yml"}

START_RE = re.compile(r"^\s*(#|<!--)\s*\[(\d{2,3})\].*START", re.IGNORECASE)
END_RE   = re.compile(r"^\s*(#|<!--)\s*\[(\d{2,3})\].*END",   re.IGNORECASE)

# No‑Ellipsis Gate (U+2026). 소스에 '…' 리터럴은 쓰지 않습니다.
NO_ELLIPSIS_RE = re.compile(chr(0x2026))


@dataclass(frozen=True)
class Block:
    num: int
    start: int
    end: int


def _run(*cmd: str) -> str:
    # stderr를 stdout으로 합쳐 캡처 → fatal 메시지 등도 표준 출력에만 담기며
    # 호출자가 제어합니다.
    cp = subprocess.run(
        list(cmd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if cp.returncode != 0:
        raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
    return cp.stdout


def _changed_files(base: str, head: str) -> List[str]:
    out = _run("git", "diff", "--name-only", f"{base}..{head}")
    return [p for p in out.splitlines() if p.strip()]


def _file_exists_at_commit(commit: str, path: str) -> bool:
    try:
        _run("git", "cat-file", "-e", f"{commit}:{path}")
        return True
    except subprocess.CalledProcessError:
        return False


def _read_at_commit(commit: str, path: str) -> str:
    if not _file_exists_at_commit(commit, path):
        return ""
    return _run("git", "show", f"{commit}:{path}")


@dataclass
class DiffInfo:
    plus: Set[int]   # AFTER 파일에서 추가/변경된 라인 번호
    minus: Set[int]  # BEFORE 파일에서 삭제/변경된 라인 번호


def _parse_unified_diff(base: str, head: str, path: str) -> DiffInfo:
    """
    'git diff --unified=0 base..head -- path' 파싱.
    신규 파일 등으로 diff가 실패하면 AFTER 전체를 추가로 간주합니다.
    """
    plus: Set[int]
    minus: Set[int]
    try:
        text = _run("git", "diff", "--unified=0", "--no-color", f"{base}..{head}", "--", path)
    except subprocess.CalledProcessError:
        try:
            after_lines = Path(path).read_text(encoding="utf-8").splitlines()
        except Exception:
            after_lines = []
        plus = set(range(1, len(after_lines) + 1))
        minus = set()
        return DiffInfo(plus=plus, minus=minus)

    plus = set()
    minus = set()
    cur_plus = 0
    cur_minus = 0
    for ln in text.splitlines():
        if ln.startswith("@@"):
            m = re.search(r"-([0-9]+)(?:,([0-9]+))?\s+\+([0-9]+)(?:,([0-9]+))?", ln)
            if not m:
                continue
            a = int(m.group(1))
            c = int(m.group(3))
            cur_minus = a
            cur_plus = c
            continue
        if ln.startswith("---") or ln.startswith("+++") or ln == "":
            continue
        if ln.startswith("+"):
            plus.add(cur_plus)
            cur_plus += 1
            continue
        if ln.startswith("-"):
            minus.add(cur_minus)
            cur_minus += 1
            continue
        cur_plus += 1
        cur_minus += 1
    return DiffInfo(plus=plus, minus=minus)


def _parse_blocks(text: str) -> List[Block]:
    blocks: List[Block] = []
    stack: List[Tuple[int, int]] = []
    for i, ln in enumerate(text.splitlines(), 1):
        s = START_RE.match(ln)
        if s:
            num = int(s.group(2))
            stack.append((num, i))
            continue
        e = END_RE.match(ln)
        if e:
            num = int(e.group(2))
            if not stack:
                raise ValueError(f"END without START at line {i}")
            start_num, start_ln = stack.pop()
            if start_num != num:
                raise ValueError(f"Mismatched block numbers: {start_num}..{num} at line {i}")
            blocks.append(Block(num=num, start=start_ln, end=i))
    if stack:
        raise ValueError("Unclosed START block(s) at EOF")
    return sorted(blocks, key=lambda b: b.start)


def _check_numbering(blocks: List[Block]) -> List[str]:
    probs: List[str] = []
    expect = 1
    for b in blocks:
        if b.num != expect:
            probs.append(f"non-sequential block number: got {b.num}, expect {expect}")
            expect = b.num + 1
        else:
            expect += 1
    return probs


def _line_map(text: str) -> Dict[int, str]:
    return {i: ln for i, ln in enumerate(text.splitlines(), 1)}


def _block_of(line_no: int, blocks: List[Block]) -> Optional[Block]:
    for b in blocks:
        if b.start <= line_no <= b.end:
            return b
    return None


def _guard_file(path: str, base: str, head: str) -> List[str]:
    probs: List[str] = []
    ext = Path(path).suffix.lower()
    if ext not in MONITORED_EXTS:
        return probs

    diff = _parse_unified_diff(base, head, path)
    before = _read_at_commit(base, path)
    after = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""

    try:
        blocks_before = _parse_blocks(before) if before else []
        blocks_after = _parse_blocks(after) if after else []
    except Exception as e:
        probs.append(f"{path}: block parse error: {e}")
        return probs

    # (1) 번호 연속성 (after)
    probs.extend(f"{path}: {p}" for p in _check_numbering(blocks_after))

    # (2) 전체 블록 교체 규칙 (추가)
    after_lines = _line_map(after)
    touched_after: Set[int] = set()
    for ln_no in sorted(diff.plus):
        b = _block_of(ln_no, blocks_after)
        if b:
            touched_after.add(b.num)
    for num in sorted(touched_after):
        b = next(x for x in blocks_after if x.num == num)
        if b.start not in diff.plus or b.end not in diff.plus:
            probs.append(f"{path}: block [{b.num}] changed without START/END (need whole-block)")

    # (3) 전체 블록 삭제 규칙 (삭제)
    touched_before: Set[int] = set()
    for ln_no in sorted(diff.minus):
        b = _block_of(ln_no, blocks_before)
        if b:
            touched_before.add(b.num)
    for num in sorted(touched_before):
        b = next(x for x in blocks_before if x.num == num)
        if b.start not in diff.minus or b.end not in diff.minus:
            probs.append(f"{path}: block [{b.num}] deletion touches inside without START/END")

    # (4) No‑Ellipsis Gate
    for ln_no in diff.plus:
        txt = after_lines.get(ln_no, "")
        if NO_ELLIPSIS_RE.search(txt):
            probs.append(f"{path}:{ln_no}: contains Unicode ellipsis (U+2026) - forbidden")

    return probs


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch guard for numeric-block edits")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    args = ap.parse_args()

    files = _changed_files(args.base, args.head)
    problems: List[str] = []
    for p in files:
        problems.extend(_guard_file(p, args.base, args.head))

    if problems:
        print("[patch-guard] FAIL")
        for p in problems:
            print(" -", p)
        return 1
    print("[patch-guard] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [01] END: tools/guard_patch.py
