#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSOT workspace pointer checker

- FAIL 조건:
  1) 파일 내 'COMMIT_SHA' 문자열 존재
  2) Source-of-Truth 라인에 '@<hex_SHA>' 사용 (예: @edd0826...)
- PASS: 위 위반 없음
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Sequence

HEX_SHA_RE = re.compile(r"@[0-9a-f]{7,40}\b", re.I)

def check_one(path: Path) -> list[str]:
    msgs: list[str] = []
    if not path.exists():
        return msgs  # 파일이 없으면 검사 생략
    txt = path.read_text(encoding="utf-8", errors="ignore")
    if "COMMIT_SHA" in txt:
        msgs.append(f"{path}: contains 'COMMIT_SHA' (remove manual SHA policy)")
    # Source-of-Truth 라인에서 @main/@release만 허용(sha 금지)
    for line in txt.splitlines():
        if "Source-of-Truth:" in line and HEX_SHA_RE.search(line):
            msgs.append(f"{path}: Source-of-Truth pins a raw commit SHA")
    return msgs

def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=["WORKSPACE_INDEX.md"])
    args = ap.parse_args(argv)

    violations: list[str] = []
    for p in args.path:
        violations += check_one(Path(p))

    if violations:
        print("SSOT Pointer Check: ❌ violations")
        for m in violations:
            print("  -", m)
        return 1
    print("SSOT Pointer Check: ✅ ok")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
