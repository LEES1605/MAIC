#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
No-Ellipsis Gate
- 목적: 코드/문서에 '중략본'이 섞이는 것을 방지한다.
- 정책:
  1) 코드 파일에서 '줄 전체가 ... 또는 …' 인 라인 → 차단
  2) (코드/문서 공통) '중략' 또는 '생략'이면서 동시에 '…' 또는 '...' 또는 스니핏 마커(<<<, >>>, <<snip>> 등)를 포함 → 차단
- 거짓 양성 최소화:
  * 일반 텍스트 내 자연스러운 '…'는 허용
  * YAML, MD 등은 2) 조건에서만 검사 (문서 끝 구분자 '...' 등 오탐 최소화)

사용법:
  python scripts/no_ellipsis_gate.py
옵션:
  --root <path>   : 스캔 시작 경로 (기본 '.')
  --verbose       : 상세 로그 출력
  --dry-run       : 종료 코드를 0으로 유지(리포트만)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

ELLIPSIS_UNICODE = "\u2026"  # …
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

SNIP_TOKENS = ("<<<", ">>>", "<<snip>>", "<<SNIP>>", "—8<—", "8<")
KOR_SKIP_WORDS = ("중략", "생략")


class Violation(Tuple[Path, int, str, str]):
    """
    (파일경로, 라인번호, 유형코드, 메시지) 튜플.
    유형코드:
      - ELLIPSIS_ONLY : 줄 전체가 … 또는 ...
      - SNIP_KO       : '중략/생략' + 스니핏/…/...
    """


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # 제외 디렉터리
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        # 확장자 분류
        ext = p.suffix.lower()
        if ext in CODE_EXTS or ext in DOC_EXTS:
            yield p


def _is_ellipsis_only_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # '...' (3개 이상) 또는 '…'(하나 이상)만으로 구성된 라인
    if set(s) <= {"."} and len(s) >= 3:
        return True
    if set(s) <= {ELLIPSIS_UNICODE}:
        return True
    return False


def _has_snip_signature(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if any(tok in s for tok in SNIP_TOKENS):
        return True
    # '중략/생략' + (… 또는 ...) 의 동시 등장
    if any(k in s for k in KOR_SKIP_WORDS) and (ELLIPSIS_UNICODE in s or "..." in s):
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
            return ("ELLIPSIS_ONLY", "줄 전체가 '…' 또는 '...'로만 구성됨")
        if _has_snip_signature(line):
            return ("SNIP_KO", "‘중략/생략’ + 스니핏/…/... 패턴 발견")
    elif ext in DOC_EXTS:
        if _has_snip_signature(line):
            return ("SNIP_KO", "문서 내 ‘중략/생략’ + 스니핏/…/... 패턴 발견")
    return None


def scan(root: Path, verbose: bool = False) -> List[Violation]:
    violations: List[Violation] = []
    for file in _iter_files(root):
        ext = file.suffix.lower()
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            # 안전을 위해 바이너리/읽기실패 파일은 스킵하되, verbose에만 노출
            if verbose:
                print(f"[skip] {file} ({e})", file=sys.stderr)
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            flagged = _should_flag_line(ext, line)
            if flagged:
                code, msg = flagged
                violations.append((file, i, code, msg))
    return violations


def _print_report(violations: Sequence[Violation]) -> None:
    if not violations:
        print("No-Ellipsis Gate: ✅ 위반 없음")
        return

    print("No-Ellipsis Gate: ❌ 위반 발견")
    for path, lineno, code, msg in violations:
        print(f"  - {code:<13} | {path}:{lineno} | {msg}")

    # 가이드
    print("\n가이드:")
    print("  1) 실제 '중략본'이라면 해당 파일을 원본 코드로 교체하세요.")
    print("  2) 정상 문서에서의 '…'는 허용되지만, '중략/생략'과 스니핏 마커는 사용하지 마세요.")
    print("  3) 필요 시 Gate 규칙을 scripts/no_ellipsis_gate.py에서 조정할 수 있습니다.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="No-Ellipsis Gate")
    parser.add_argument("--root", default=".", help="스캔 시작 경로 (기본 '.')")
    parser.add_argument("--verbose", action="store_true", help="상세 로그")
    parser.add_argument("--dry-run", action="store_true", help="리포트만 (항상 0으로 종료)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"[error] 경로 없음: {root}", file=sys.stderr)
        return 2

    violations = scan(root, verbose=args.verbose)
    _print_report(violations)

    if args.dry_run:
        return 0
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
