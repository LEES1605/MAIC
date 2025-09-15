#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch-Guard (Relaxed)

정책(완화판):
  - START/END 쌍의 "짝맞춤"과 "중첩 금지"만 강제.
  - 블록 전체 교체 의무 없음(블록 내부 일부 라인 변경 허용).
  - 번호([NN] 또는 [NNX])는 순차성 권고, 강제하지 않음.
  - [NNX]에서 X는 대문자 1글자(예: [03B]) 허용.
  - 마커 라인은 다음 형태만 인식:
      * Python/YAML 주석: ^\s*#.*\[(\d{2})([A-Z])?\].*\b(START|END)\b
      * Markdown 맨 앞:  ^\[(\d{2})([A-Z])?\].*\b(START|END)\b
  - U+2026(…) 금지(문서/코드 모두).

입력:
  --base, --head : (선택) diff 범위를 좁히기 위한 힌트. 실패 시 안전 폴백.

종료코드:
  0 = PASS, 1 = FAIL
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


# -------- 설정 --------
TEXT_EXTS = {
    ".py", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".json", ".sh"
}
ELLIPSIS = "\u2026"  # 금지 문자


@dataclass(frozen=True)
class Marker:
    line_no: int
    ident: str    # "02" or "02B"
    kind: str     # "START" or "END"
    raw: str


# Python/YAML 주석형: "# ... [NN] ... START/END"
RE_COMMENT = re.compile(
    r"^\s*#.*\[(?P<num>\d{2})(?P<sfx>[A-Z])?\].*\b(?P<kind>START|END)\b", re.IGNORECASE
)

# Markdown 맨 앞: "[NN] ... START/END"
RE_MD = re.compile(
    r"^\[(?P<num>\d{2})(?P<sfx>[A-Z])?\].*\b(?P<kind>START|END)\b", re.IGNORECASE
)

# 폭 넓은 텍스트 판정(바이너리 회피)
def _is_text_candidate(p: Path) -> bool:
    if p.suffix.lower() in TEXT_EXTS:
        return True
    # 기타 확장자는 크기 작고 널바이트 없으면 텍스트로 가정
    try:
        b = p.read_bytes()[:4096]
        return b.find(b"\x00") < 0
    except Exception:
        return False


def _run(cmd: Sequence[str]) -> Tuple[int, str]:
    try:
        cp = subprocess.run(cmd, check=False, capture_output=True, text=True)
        out = (cp.stdout or "").strip()
        if not out and cp.stderr:
            out = cp.stderr.strip()
        return cp.returncode, out
    except Exception as e:
        return 1, str(e)


def _changed_files(base: Optional[str], head: Optional[str]) -> List[Path]:
    # 우선 Git diff 시도
    candidates: List[str] = []
    if base and head:
        rc, out = _run(["git", "diff", "--name-only", f"{base}..{head}"])
        if rc == 0 and out:
            candidates = [s for s in out.splitlines() if s.strip()]
    if not candidates:
        # PR 환경이 아니거나 실패 시: 추적 중인 텍스트 파일 전체 검사
        rc, out = _run(["git", "ls-files"])
        if rc == 0 and out:
            candidates = [s for s in out.splitlines() if s.strip()]
        else:
            # 최후: 작업 디렉터리 전체(상대경로) 스캔
            for p in Path(".").rglob("*"):
                if p.is_file():
                    candidates.append(str(p))

    files: List[Path] = []
    for s in candidates:
        p = Path(s)
        if p.exists() and p.is_file() and _is_text_candidate(p):
            files.append(p)
    # uniq 유지
    seen = set()
    out: List[Path] = []
    for p in files:
        if p.as_posix() not in seen:
            seen.add(p.as_posix())
            out.append(p)
    return out


def _read_text(p: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"):
        try:
            return p.read_text(encoding=enc)
        except Exception:
            continue
    return ""


def _collect_markers(text: str) -> List[Marker]:
    markers: List[Marker] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = RE_COMMENT.search(line)
        if not m:
            m = RE_MD.search(line)
        if not m:
            continue
        ident = m.group("num") + (m.group("sfx") or "")
        kind = m.group("kind").upper()
        markers.append(Marker(i, ident, kind, line.rstrip()))
    return markers


def _validate_pairs(markers: List[Marker]) -> List[str]:
    """
    중첩 금지 + 짝맞춤만 검사.
    - START 다음에는 반드시 같은 ident의 END가 나와야 한다.
    - 다른 ident로 "중첩 START" 금지.
    - END가 먼저 나오면 오류.
    """
    errs: List[str] = []
    stack: List[Marker] = []
    for m in markers:
        if m.kind == "START":
            if stack:
                prev = stack[-1]
                errs.append(
                    f"nested block not allowed: {m.ident} START at line {m.line_no} while {prev.ident} still open (START line {prev.line_no})"
                )
            stack.append(m)
        else:  # END
            if not stack:
                errs.append(f"END without START: {m.ident} at line {m.line_no}")
                continue
            prev = stack.pop()
            if prev.ident != m.ident:
                errs.append(
                    f"mismatched END: got {m.ident} at line {m.line_no}, expected {prev.ident} (START line {prev.line_no})"
                )
    if stack:
        open_list = ", ".join(f"{x.ident}@{x.line_no}" for x in stack)
        errs.append(f"unclosed START remains: {open_list}")
    return errs


def _scan_ellipsis(text: str) -> List[int]:
    lines: List[int] = []
    if ELLIPSIS not in text:
        return lines
    for i, line in enumerate(text.splitlines(), start=1):
        if ELLIPSIS in line:
            lines.append(i)
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Patch-Guard (Relaxed)")
    ap.add_argument("--base", default=os.getenv("BASE_SHA") or "", help="optional base sha")
    ap.add_argument("--head", default=os.getenv("HEAD_SHA") or "", help="optional head sha")
    args = ap.parse_args(argv)

    targets = _changed_files(args.base or None, args.head or None)
    errors: List[str] = []

    for p in targets:
        txt = _read_text(p)
        # 1) Ellipsis 금지
        bad = _scan_ellipsis(txt)
        if bad:
            for ln in bad:
                errors.append(f"{p.as_posix()}:{ln}: contains Unicode ellipsis (U+2026) - forbidden")

        # 2) START/END 쌍 검증 (해당 파일에 마커가 있는 경우에만)
        markers = _collect_markers(txt)
        if markers:
            ers = _validate_pairs(markers)
            for e in ers:
                errors.append(f"{p.as_posix()}: {e}")

    if errors:
        print("[patch-guard] FAIL")
        for e in errors:
            print(f" - {e}")
        return 1

    print("[patch-guard] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
