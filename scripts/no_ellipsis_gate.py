#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ========================== [01] module docstring — START =========================
"""
No‑Ellipsis Gate

목적
- 코드/문서에 '중략본'이 섞이는 것을 방지합니다.

정책
  1) (코드 파일) 줄 전체가 점(3개 이상)만이거나, 순수한 ellipsis(U+2026)만인 라인 → 차단
  2) (코드/문서 공통) 아래 **두 조건을 동시에 만족**하면 차단:
     - '중략' 또는 '생략'
     - ellipsis(U+2026) 또는 3‑dots, 또는 스니핏 마커(angled‑triple 등)

거짓 양성 최소화
  * 일반 텍스트에서 자연스러운 ellipsis는 허용합니다.
  * YAML/MD 등 문서류는 2) 조건에서만 검사합니다.

사용법
  python scripts/no_ellipsis_gate.py
옵션
  --root <path>     : 스캔 시작 경로 (기본 '.')
  --verbose         : 상세 로그 출력
  --dry-run         : 리포트만 출력하고 항상 0으로 종료
  --include-self    : 이 스크립트 파일도 스캔(기본은 제외)
"""
# =========================== [01] module docstring — END ==========================

# ============================ [02] imports & consts — START =======================
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, NamedTuple

ELLIPSIS_UNICODE = "\u2026"  # U+2026 (…)
CODE_EXTS = {
    # 주요 코드/스크립트 확장자
    ".py", ".ts", ".js", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".scala", ".dart",
    ".r", ".m", ".sh", ".zsh", ".fish", ".ps1",
    ".sql", ".html", ".css", ".scss",
    # 구성/데이터 중 코드스러운 것들
    ".ini", ".cfg", ".toml", ".json",
}
DOC_EXTS = {
    # 문서류: 엄격도 완화 (스니핏/중략 패턴만)
    ".md", ".rst", ".txt", ".mdx", ".yaml", ".yml",
}

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", ".venv", "venv",
    "__pycache__", "node_modules", "build", "dist",
}

# 스니핏 마커(실제 기호). 다른 파일에서는 탐지하고, 이 파일은 기본 스킵.
SNIP_TOKENS = ("<<<", ">>>", "<<snip>>", "<<SNIP>>", "—8<—", "8<")
KOR_SKIP_WORDS = ("중략", "생략")

SELF_PATH = Path(__file__).resolve()
SELF_BASENAME = SELF_PATH.name
# ============================ [02] imports & consts — END =========================

# ============================= [03] types & helpers — START =======================
class Violation(NamedTuple):
    """
    (파일경로, 라인번호, 유형코드, 메시지) 튜플.
    유형코드:
      - ELLIPSIS_ONLY : 줄 전체가 ellipsis 또는 3‑dots
      - SNIP_KO       : '중략/생략' + (ellipsis/3‑dots/스니핏) 동시 등장
    """


def _iter_files(root: Path, *, include_self: bool) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # 제외 디렉터리
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        # 자기 자신은 기본 제외
        if not include_self:
            try:
                if p.resolve() == SELF_PATH or p.name == SELF_BASENAME:
                    continue
            except Exception:
                # 해석 실패 시에도 파일명 기준으로 방어
                if p.name == SELF_BASENAME:
                    continue
        # 확장자 분류
        ext = p.suffix.lower()
        if ext in CODE_EXTS or ext in DOC_EXTS:
            yield p


def _is_ellipsis_only_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # '...' (3개 이상) 또는 ellipsis(U+2026)만으로 구성된 라인
    if set(s) <= {"."} and len(s) >= 3:
        return True
    if set(s) <= {ELLIPSIS_UNICODE}:
        return True
    return False


def _has_snip_signature(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # 스니핏 마커(<<<, >>> 등)
    if any(tok in s for tok in SNIP_TOKENS):
        return True
    # '중략/생략' + (ellipsis(U+2026) 또는 3‑dots)
    if any(k in s for k in KOR_SKIP_WORDS) and (
        ELLIPSIS_UNICODE in s or "..." in s
    ):
        return True
    return False


def _should_flag_line(ext: str, line: str) -> Optional[Tuple[str, str]]:
    """
    반환:
      (유형코드, 메시지) 또는 None (정상)

    정책:
      - CODE_EXTS: _is_ellipsis_only_line → 차단, _has_snip_signature → 차단
      - DOC_EXTS : _has_snip_signature → 차단 (오탐 최소화)
    """
    if ext in CODE_EXTS:
        if _is_ellipsis_only_line(line):
            return ("ELLIPSIS_ONLY", "줄 전체가 ellipsis/3‑dots 만으로 구성됨")
        if _has_snip_signature(line):
            return ("SNIP_KO", "‘중략/생략’ + (ellipsis/3‑dots/스니핏) 패턴")
    elif ext in DOC_EXTS:
        if _has_snip_signature(line):
            return ("SNIP_KO", "문서 내 ‘중략/생략’ + (ellipsis/3‑dots/스니핏) 패턴")
    return None
# ============================= [03] types & helpers — END =========================

# ================================== [04] core — START ============================
def scan(root: Path, *, include_self: bool, verbose: bool = False) -> List[Violation]:
    violations: List[Violation] = []
    for file in _iter_files(root, include_self=include_self):
        ext = file.suffix.lower()
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            # 바이너리/읽기 실패 파일은 스킵(원인만 verbose로)
            if verbose:
                print(f"[skip] {file} ({e})", file=sys.stderr)
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            flagged = _should_flag_line(ext, line)
            if flagged:
                code, msg = flagged
                violations.append(Violation(file, i, code, msg))
    return violations


def _print_report(violations: Sequence[Violation]) -> None:
    if not violations:
        print("No‑Ellipsis Gate: ✅ 위반 없음")
        return

    print("No‑Ellipsis Gate: ❌ 위반 발견")
    for path, lineno, code, msg in violations:
        print(f"  - {code:<13} | {path}:{lineno} | {msg}")

    # 가이드(표시는 하되, 금지 패턴을 문자 그대로 쓰지 않음)
    print("\n가이드:")
    print("  1) 실제 '중략본'이면 원본 코드로 교체하세요.")
    print("  2) 정상 문서의 ellipsis(U+2026)는 허용되지만,")
    print("     '중략/생략'과 ellipsis(또는 3‑dots), 스니핏 마커의 동시 사용은 금지입니다.")
    print("  3) 필요 시 규칙은 scripts/no_ellipsis_gate.py에서 조정하세요.")
# =================================== [04] core — END =============================

# ================================== [05] cli — START =============================
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="No‑Ellipsis Gate")
    parser.add_argument("--root", default=".", help="스캔 시작 경로 (기본 '.')")
    parser.add_argument("--verbose", action="store_true", help="상세 로그")
    parser.add_argument("--dry-run", action="store_true", help="리포트만 (항상 0으로 종료)")
    parser.add_argument(
        "--include-self",
        action="store_true",
        help="이 스크립트 파일도 스캔(기본은 제외)",
    )
    args = parser.parse_args(argv)

    # 환경변수로도 self-scan 제어 가능(명시 옵션이 우선)
    env_include_self = os.getenv("NO_ELLIPSIS_INCLUDE_SELF", "").lower() in ("1", "true")
    include_self = bool(args.include_self or env_include_self)

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"[error] 경로 없음: {root}", file=sys.stderr)
        return 2

    violations = scan(root, include_self=include_self, verbose=args.verbose)
    _print_report(violations)

    if args.dry_run:
        return 0
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
# =================================== [05] cli — END ==============================
