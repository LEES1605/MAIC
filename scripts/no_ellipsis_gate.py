#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============ [01] module docstring & imports — START ============
"""
No‑Ellipsis Gate
- 목적: 코드/문서에 '중략본'이 섞이는 것을 방지합니다.

정책(요약):
  1) 코드 파일에서 '줄 전체가 ... 또는 …' 인 라인 → 차단
  2) 코드/문서에서 '중략' 또는 '생략'과
     '…' 또는 '...' 또는 스니핏 마커(<<<, >>>, <<snip>> 등)가
     동시에 등장 → 차단

거짓 양성 최소화:
  * 일반 텍스트의 자연스러운 '…'는 허용
  * 문서류(MD/RST/TXT/YAML)는 ② 규칙만 검사
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, NamedTuple
# ============ [01] module docstring & imports — END ==============


# =============== [02] constants & config — START =================
ELLIPSIS_UNICODE = "\u2026"  # “…”

# 주요 코드/스크립트 확장자
CODE_EXTS = {
    ".py", ".ts", ".js", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".scala", ".dart",
    ".r", ".m", ".sh", ".zsh", ".fish", ".ps1",
    ".sql", ".html", ".css", ".scss",
    ".ini", ".cfg", ".toml", ".json",
}

# 문서류: 엄격도 완화(스니핏/중략 패턴만 검사)
DOC_EXTS = {".md", ".rst", ".txt", ".mdx", ".yaml", ".yml"}

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn",
    ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist",
}

# 🔒 자기 자신은 항상 제외(정책 설명 문자열 때문에 자가-오탐 방지)
SELF_EXCLUDED_FILES = {Path(__file__).resolve()}
SELF_EXCLUDED_NAMES = {"no_ellipsis_gate.py"}

# 스니핏/중략 패턴
SNIP_TOKENS = ("<<<", ">>>", "<<snip>>", "<<SNIP>>", "—8<—", "8<")
KOR_SKIP_WORDS = ("중략", "생략")
# =============== [02] constants & config — END ===================


# =============== [03] types & helpers — START ====================
class Violation(NamedTuple):
    """(파일경로, 라인번호, 유형코드, 메시지)"""
    path: Path
    lineno: int
    code: str
    message: str


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # 제외 디렉터리
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        # 자기 자신 제외
        try:
            if p.resolve() in SELF_EXCLUDED_FILES or p.name in SELF_EXCLUDED_NAMES:
                continue
        except Exception:
            # resolve 실패 시 이름만으로 판단
            if p.name in SELF_EXCLUDED_NAMES:
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
# =============== [03] types & helpers — END ======================


# ============ [04] decision per line — START =====================
def _should_flag_line(ext: str, line: str) -> Optional[tuple[str, str]]:
    """
    반환: (유형코드, 메시지) 또는 None(정상)

    정책:
      - CODE_EXTS: _is_ellipsis_only_line → 차단,
                   _has_snip_signature → 차단
      - DOC_EXTS : _has_snip_signature → 차단(오탐 최소화)
    """
    if ext in CODE_EXTS:
        if _is_ellipsis_only_line(line):
            return ("ELLIPSIS_ONLY", "줄 전체가 '…' 또는 '...'로만 구성됨")
        if _has_snip_signature(line):
            return ("SNIP_KO", "‘중략/생략’ + 스니핏/…/... 패턴")
    elif ext in DOC_EXTS:
        if _has_snip_signature(line):
            return ("SNIP_KO", "문서 내 ‘중략/생략’ + 스니핏/…/... 패턴")
    return None
# ============ [04] decision per line — END =======================


# ================= [05] scanner — START ==========================
def scan(root: Path, verbose: bool = False) -> List[Violation]:
    violations: List[Violation] = []
    for file in _iter_files(root):
        ext = file.suffix.lower()
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            if verbose:
                print(f"[skip] {file} ({e})", file=sys.stderr)
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            flagged = _should_flag_line(ext, line)
            if flagged:
                code, msg = flagged
                violations.append(Violation(file, i, code, msg))
    return violations
# ================= [05] scanner — END ============================


# ============== [06] CLI & report — START ========================
def _print_report(violations: Sequence[Violation]) -> None:
    if not violations:
        print("No‑Ellipsis Gate: ✅ 위반 없음")
        return

    print("No‑Ellipsis Gate: ❌ 위반 발견")
    for path, lineno, code, msg in violations:
        print(f"  - {code:<13} | {path}:{lineno} | {msg}")

    print("\n가이드:")
    print("  1) 실제 '중략본'이면 원본 코드로 교체하세요.")
    print("  2) 정상 문서의 줄임표는 허용되지만,")
    print("     '중략/생략'과 스니핏 마커의 동시 사용은 금지입니다.")
    print("  3) 필요 시 규칙은 scripts/no_ellipsis_gate.py에서 조정하세요.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="No‑Ellipsis Gate")
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
# ============== [06] CLI & report — END ==========================
