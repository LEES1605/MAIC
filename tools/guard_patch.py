# ============================ [01] imports & constants — START ============================
from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple

# 금지 문자(ASCII만 허용): Unicode ellipsis
ELLIPSIS = "\u2026"

# 블록 마커: 라인 주석 안에서 [NN][A-Z?] 식별자와 START/END 키워드를 탐지
# 예: "# ===== [07] RERUN GUARD utils — START ====="
#     "# ...  # [07] END"
MARK_RE = re.compile(
    r"^\s*#.*\[\s*(?P<num>\d{2})(?P<suf>[A-Z]?)\s*\].*(?P<edge>START|END)\s*$",
    re.IGNORECASE,
)

# git diff hunk 헤더: "@@ -a,b +c,d @@"
HUNK_RE = re.compile(
    r"^@@\s+- (?P<amin>\d+),(?P<alen>\d+)\s+\+(?P<pmin>\d+),(?P<plen>\d+)\s+@@"
)

# 출력 포맷(게이트 메시지와 동일한 톤)
FAIL_HEADER = "[patch-guard] FAIL"
ELLIPSIS_MSG = "contains Unicode ellipsis (U+2026) - forbidden"
PARTIAL_MSG = "block [{ident}] changed without START/END (need whole-block)"
DELETE_INNER_MSG = "block [{ident}] deletion touches inside without START/END"
MISMATCH_END_MSG = (
    "mismatched END: got {got} at line {line}, expected {exp} "
    "(START line {start_line})"
)
END_NO_START_MSG = "END without START at line {line}"
# ============================ [01] imports & constants — END ==============================


# =============================== [02] data models — START =================================
@dataclass(frozen=True)
class Marker:
    ident: str
    line_no: int
    is_start: bool


@dataclass(frozen=True)
class Block:
    ident: str
    start: int
    end: int  # 포함 범위(START 라인~END 라인)

    @property
    def inner_range(self) -> Tuple[int, int]:
        # 블록 내부(START/END 제외)
        return (self.start + 1, self.end - 1) if self.end - self.start >= 2 else (0, -1)
# =============================== [02] data models — END ===================================
# ============================== [03] small helpers — START =================================
def _run(cmd: Sequence[str]) -> str:
    out = subprocess.run(
        list(cmd), check=False, capture_output=True, text=True
    )
    return out.stdout or ""


def _lines_with_ellipsis(text: str) -> List[int]:
    lines: List[int] = []
    for i, s in enumerate(text.splitlines(), start=1):
        if ELLIPSIS in s:
            lines.append(i)
    return lines


def _parse_markers(text: str) -> Tuple[List[Marker], List[str]]:
    """파일 텍스트에서 START/END 마커를 추출하고 기초 오류를 리턴."""
    markers: List[Marker] = []
    errs: List[str] = []
    for i, s in enumerate(text.splitlines(), start=1):
        match = MARK_RE.match(s)  # re.Match | None (로컬 변수명 충돌 방지)
        if not match:
            continue
        ident = f"{match.group('num')}{match.group('suf')}".upper()
        edge = match.group("edge").upper()
        markers.append(Marker(ident=ident, line_no=i, is_start=edge == "START"))

    # 쌍 매칭 검증(파일 내부)
    stack: List[Marker] = []
    for mk in markers:
        if mk.is_start:
            stack.append(mk)
            continue
        # END
        if not stack:
            errs.append(END_NO_START_MSG.format(line=mk.line_no))
            continue
        prev_mk: Marker = stack.pop()
        if prev_mk.ident != mk.ident:
            errs.append(
                MISMATCH_END_MSG.format(
                    got=mk.ident,
                    line=mk.line_no,
                    exp=prev_mk.ident,
                    start_line=prev_mk.line_no,
                )
            )
    # 남은 START는 허용(후속 블록 교체 시 diff가 분리될 수 있음)
    # 완벽한 짝맞춤은 아래 build_blocks에서 다시 확인
    return markers, errs


def _build_blocks(markers: Sequence[Marker]) -> Tuple[List[Block], List[str]]:
    """마커로 블록(START~END) 목록을 구성."""
    blocks: List[Block] = []
    errs: List[str] = []
    stack: List[Marker] = []
    for mk in markers:
        if mk.is_start:
            stack.append(mk)
        else:
            if not stack:
                errs.append(END_NO_START_MSG.format(line=mk.line_no))
                continue
            prev_mk: Marker = stack.pop()
            if prev_mk.ident != mk.ident:
                errs.append(
                    MISMATCH_END_MSG.format(
                        got=mk.ident,
                        line=mk.line_no,
                        exp=prev_mk.ident,
                        start_line=prev_mk.line_no,
                    )
                )
                continue
            blocks.append(Block(ident=mk.ident, start=prev_mk.line_no, end=mk.line_no))
    # START 남아서 짝이 없으면 내부 규약상 허용하지 않음
    for start_mk in stack:
        # START에 대응하는 END가 없음
        errs.append(
            f"START without END: [{start_mk.ident}] opened at line {start_mk.line_no}"
        )
    return blocks, errs


def _range_to_set(r: Tuple[int, int]) -> Set[int]:
    a, b = r
    if a <= 0 or b <= 0 or b < a:
        return set()
    return set(range(a, b + 1))
# ============================== [03] small helpers — END ===================================

# =============================== [04] diff utils — START ===================================
def _changed_lines_plus(base: str, head: str, path: str) -> Set[int]:
    """HEAD 기준 추가/변경된 라인(plus)을 집합으로 반환."""
    out = _run(["git", "diff", "-U0", base, head, "--", path])
    plus: Set[int] = set()
    for line in out.splitlines():
        m = HUNK_RE.match(line.strip())
        if not m:
            continue
        pmin = int(m.group("pmin"))
        plen = int(m.group("plen"))
        if plen == 0:
            continue
        plus.update(range(pmin, pmin + plen))
    return plus


def _changed_lines_minus(base: str, head: str, path: str) -> Set[int]:
    """BASE 기준 삭제된 라인(minus)을 집합으로 반환."""
    out = _run(["git", "diff", "-U0", base, head, "--", path])
    minus: Set[int] = set()
    for line in out.splitlines():
        m = HUNK_RE.match(line.strip())
        if not m:
            continue
        amin = int(m.group("amin"))
        alen = int(m.group("alen"))
        if alen == 0:
            continue
        minus.update(range(amin, amin + alen))
    return minus
# =============================== [04] diff utils — END =====================================


# ============================== [05] validators — START ====================================
def _check_ellipsis(path: Path, head_text: str, errors: List[str]) -> None:
    bad = _lines_with_ellipsis(head_text)
    for ln in bad:
        errors.append(f"{path.as_posix()}:{ln}: {ELLIPSIS_MSG}")


def _check_blocks_whole_replace(
    path: Path,
    head_text: str,
    base_text: str,
    base_sha: str,
    head_sha: str,
    errors: List[str],
) -> None:
    """
    규칙:
      - 파일에 블록 마커가 있다면, 블록 내부를 수정할 때 START/END 라인도 함께 변경되어야 한다.
      - 삭제가 블록 내부를 건드리면 마찬가지로 START/END 동반 변경이 있어야 한다.
    """
    markers, perr = _parse_markers(head_text)
    errors.extend(f"{path.as_posix()}: {e}" for e in perr)
    if not markers:
        # 마커가 없다면 이 검사는 생략(번호 규약 강제하지 않음)
        return

    blocks, berr = _build_blocks(markers)
    errors.extend(f"{path.as_posix()}: {e}" for e in berr)
    if not blocks:
        return

    plus = _changed_lines_plus(base_sha, head_sha, path.as_posix())
    minus = _changed_lines_minus(base_sha, head_sha, path.as_posix())

    # HEAD 파일에서 마커 라인 집합
    head_lines = head_text.splitlines()
    start_lines = {b.start for b in blocks if 1 <= b.start <= len(head_lines)}
    end_lines = {b.end for b in blocks if 1 <= b.end <= len(head_lines)}
    marker_lines = start_lines | end_lines

    # 1) 내부 수정이 있으면 START/END 동반 변경 필요
    for b in blocks:
        inner = _range_to_set(b.inner_range)
        if not inner:
            continue
        touched = inner & plus
        if touched and not ({b.start, b.end} <= plus):
            errors.append(f"{path.as_posix()}: {PARTIAL_MSG.format(ident=b.ident)}")

    # 2) 삭제가 base의 블록 내부를 건드렸는데, HEAD에서 어떤 마커도 바뀌지 않았다면 실패
    if minus:
        if not (plus & marker_lines):
            for b in blocks:
                # 보수적으로: 삭제가 있었다면 각 블록에 대해 경고를 내리되,
                # 한 번이라도 마커 변경이 있으면 통과.
                errors.append(
                    f"{path.as_posix()}: "
                    f"{DELETE_INNER_MSG.format(ident=b.ident)}"
                )
            # 중복 과다 보고 방지: 한 번만 내리고 종료
            return
# ============================== [05] validators — END ======================================


# ================================ [06] main — START ========================================
def _changed_files(base_sha: str, head_sha: str) -> List[Path]:
    out = _run(["git", "diff", "--name-only", base_sha, head_sha])
    files = [Path(p.strip()) for p in out.splitlines() if p.strip()]
    return files


def _git_show(sha: str, path: Path) -> str:
    out = _run(["git", "show", f"{sha}:{path.as_posix()}"])
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="guard_patch")
    p.add_argument("--base", required=True, help="base commit sha")
    p.add_argument("--head", required=True, help="head commit sha")
    args = p.parse_args(argv)

    base_sha = str(args.base)
    head_sha = str(args.head)

    files = _changed_files(base_sha, head_sha)
    all_errors: List[str] = []

    for path in files:
        # 워크트리(HEAD)의 최신 내용
        head_text = Path(path).read_text(encoding="utf-8", errors="ignore") \
            if Path(path).exists() else ""
        base_text = _git_show(base_sha, path)

        _check_ellipsis(path, head_text, all_errors)
        _check_blocks_whole_replace(
            path, head_text, base_text, base_sha, head_sha, all_errors
        )

    if all_errors:
        print(FAIL_HEADER)
        for e in all_errors:
            print(f" - {e}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
# ================================ [06] main — END ==========================================
