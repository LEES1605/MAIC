#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ========================= [01] docstring & imports — START =========================
"""
No‑Ellipsis Gate
- 목적: 코드/문서에 '중략본'이 섞이는 것을 방지합니다.
- 정책:
  1) 코드 파일에서 '줄 전체가 점 세 개(three-dots) 또는 유니코드 엘리시스'인 라인 → 차단
  2) (코드/문서 공통) 아래 **조건이 같은 줄에서 동시에** 충족되면 차단:
     • '중략' 또는 '생략' 단어가 있고
     • 줄임 표시(유니코드 U+2026 또는 점 세 개) **또는**
     • 스니핏 마커(예: snip 토큰) 표시가 있음
  ※ 위 설명은 라인별로 분리하여 기술해, 본 파일 도큐스트링이 게이트에 걸리지 않도록 했습니다.

사용법:
  python scripts/no_ellipsis_gate.py
옵션:
  --root <path>   : 스캔 시작 경로 (기본 '.')
  --verbose       : 상세 로그 출력
  --dry-run       : 리포트만(항상 0으로 종료)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, NamedTuple
# ========================= [01] docstring & imports — END ===========================


# =========================== [02] constants & config — START ========================
ELLIPSIS_UNICODE = "\u2026"  # …
CODE_EXTS = {
    ".py", ".ts", ".js", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".scala", ".dart",
    ".r", ".m", ".sh", ".zsh", ".fish", ".ps1",
    ".sql", ".html", ".css", ".scss",
    ".ini", ".cfg", ".toml", ".json",
}
DOC_EXTS = {".md", ".rst", ".txt", ".mdx", ".yaml", ".yml"}
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", ".venv", "venv",
    "__pycache__", "node_modules", "build", "dist",
}
SNIP_TOKENS = ("<<<", ">>>", "<<snip>>", "<<SNIP>>", "—8<—", "8<")
KOR_SKIP_WORDS = ("중략", "생략")
# =========================== [02] constants & config — END ==========================


# ============================= [03] types & helpers — START ========================
class Violation(NamedTuple):
    """(파일경로, 라인번호, 유형코드, 메시지)"""
    path: Path
    lineno: int
    code: str
    msg: str


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        ext = p.suffix.lower()
        if ext in CODE_EXTS or ext in DOC_EXTS:
            yield p


def _is_ellipsis_only_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if set(s) <= {"."} and len(s) >= 3:  # 점 세 개 이상만 있는 라인
        return True
    if set(s) <= {ELLIPSIS_UNICODE}:     # 유니코드 엘리시스만 있는 라인
        return True
    return False


def _has_snip_signature(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if any(tok in s for tok in SNIP_TOKENS):
        return True
    if any(k in s for k in KOR_SKIP_WORDS) and (ELLIPSIS_UNICODE in s or "..." in s):
        return True
    return False


def _should_flag_line(ext: str, line: str) -> Optional[tuple[str, str]]:
    """
    반환: (유형코드, 메시지) 또는 None
    - CODE_EXTS: '…/...' 만 라인, 혹은 '중략/생략'+(…/...' 또는 스니핏) → 차단
    - DOC_EXTS : '중략/생략'+(…/...' 또는 스니핏) → 차단 (문서 끝 '...' 오탐 방지)
    """
    if ext in CODE_EXTS:
        if _is_ellipsis_only_line(line):
            return ("ELLIPSIS_ONLY", "줄 전체가 줄임 표시만으로 구성됨")
        if _has_snip_signature(line):
            return ("SNIP_KO", "‘중략/생략’ + 줄임/스니핏 패턴")
    elif ext in DOC_EXTS:
        if _has_snip_signature(line):
            return ("SNIP_KO", "문서 내 ‘중략/생략’ + 줄임/스니핏 패턴")
    return None
# ============================= [03] types & helpers — END ==========================


# ================================ [04] scan — START ================================
def scan(root: Path, verbose: bool = False) -> List[Violation]:
    violations: List[Violation] = []
    for file in _iter_files(root):
        ext = file.suffix.lower()
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f"[skip] {file} ({e})", file=sys.stderr)
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            flagged = _should_flag_line(ext, line)
            if flagged:
                code, msg = flagged
                violations.append(Violation(file, i, code, msg))
    return violations
# ================================ [04] scan — END =================================


# ============================== [05] report — START ===============================
def _print_report(violations: Sequence[Violation]) -> None:
    if not violations:
        print("No‑Ellipsis Gate: ✅ 위반 없음")
        return

    print("No‑Ellipsis Gate: ❌ 위반 발견")
    for v in violations:
        print(f"  - {v.code:<13} | {v.path}:{v.lineno} | {v.msg}")

    print("\n가이드:")
    print("  1) 실제 '중략본'이라면 해당 파일을 원본 코드로 교체하세요.")
    print("  2) 정상 문서의 줄임 표시는 허용되지만, '중략/생략'과 스니핏 마커 동시 사용은 금지.")
    print("  3) 필요 시 규칙은 scripts/no_ellipsis_gate.py에서 조정할 수 있습니다.")
# ============================== [05] report — END =================================


# ================================ [06] main — START ===============================
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="No‑Ellipsis Gate")
    parser.add_argument("--root", default=".", help="스캔 시작 경로 (기본 '.')")
    parser.add_argument("--verbose", action="store_true", help="상세 로그")
    parser.add_argument("--dry-run", action="store_true", help="리포트만(항상 0으로 종료)")
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
# ================================ [06] main — END =================================
