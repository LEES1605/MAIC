#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================= [01] module docstring & imports — START =============================
"""
No‑Ellipsis Gate

목적:
  - 코드/문서에 '중략본'이 섞이는 것을 방지.

정책:
  1) 코드 파일에서 '줄 전체가 …(U+2026) 또는 ...' 인 라인은 차단.
  2) (코드/문서 공통) 아래 **두 조건을 동시에 만족**하면 차단:
     - 해당 줄에 '중략' 또는 '생략'이 존재하고
     - 같은 줄에 스니핏 마커(예: <<<, >>>, <<snip>> 등) **또는 줄임표(ellipsis)**가 존재

오탐 최소화:
  * 일반 텍스트 내 자연스러운 줄임표는 허용.
  * YAML/MD 등 문서는 2) 규칙만 적용(문서 끝의 '...' 백매터 등 오탐 방지).

사용법:
  python scripts/no_ellipsis_gate.py
옵션:
  --root <path> : 스캔 시작 경로 (기본 '.')
  --verbose     : 상세 로그
  --dry-run     : 리포트만 출력하고 항상 0으로 종료
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, NamedTuple
# ============================= [01] module docstring & imports — END ===============================


# =================================== [02] constants & config — START ===============================
ELLIPSIS_UNICODE = "\u2026"  # “…” (U+2026)

# 주요 코드/스크립트 확장자
CODE_EXTS = {
    ".py", ".ts", ".js", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".scala", ".dart",
    ".r", ".m", ".sh", ".zsh", ".fish", ".ps1",
    ".sql", ".html", ".css", ".scss",
    # 구성/데이터 중 코드스러운 것들
    ".ini", ".cfg", ".toml", ".json",
}

# 문서류: 엄격도 완화(스니핏/중략+줄임표 동시패턴만 차단)
DOC_EXTS = {".md", ".rst", ".txt", ".mdx", ".yaml", ".yml"}

# 제외 디렉터리
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn",
    ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".venv", "venv",
    "__pycache__", "node_modules", "build", "dist",
}

# 스니핏/줄임표/표식 토큰
SNIP_TOKENS = ("<<<", ">>>", "<<snip>>", "<<SNIP>>", "—8<—", "8<")
KOR_SKIP_WORDS = ("중략", "생략")

# 게이트 자기 자신은 항상 제외(자가-오탐 방지)
SELF_EXCLUDED_FILES = {Path(__file__).resolve()}
SELF_EXCLUDED_NAMES = {"no_ellipsis_gate.py"}  # 혹시 경로 해상도가 다를 경우 대비
# =================================== [02] constants & config — END =================================


# =================================== [03] types & helpers — START ==================================
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
        # 디렉터리 제외
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        # 게이트 자기 자신 제외
        try:
            rp = p.resolve()
            if rp in SELF_EXCLUDED_FILES or p.name in SELF_EXCLUDED_NAMES:
                continue
        except Exception:
            if p.name in SELF_EXCLUDED_NAMES:
                continue
        # 확장자 분류
        ext = p.suffix.lower()
        if ext in CODE_EXTS or ext in DOC_EXTS:
            yield p


def _is_ellipsis_only_line(line: str) -> bool:
    """줄 전체가 줄임표로만 구성됐는지 검사(코드 파일 전용)."""
    s = line.strip()
    if not s:
        return False
    # '...' (3개 이상)만으로 구성
    if set(s) <= {"."} and len(s) >= 3:
        return True
    # '…' (하나 이상)만으로 구성
    if set(s) <= {ELLIPSIS_UNICODE}:
        return True
    return False


def _has_snip_signature(line: str) -> bool:
    """스니핏 마커 또는 (중략/생략 + 줄임표) 동시 등장 여부."""
    s = line.strip()
    if not s:
        return False
    # 스니핏 마커면 즉시 플래그
    if any(tok in s for tok in SNIP_TOKENS):
        return True
    # '중략/생략' + (유니코드 줄임표 또는 '...')
    # ⚠️ 한 줄 단위 매칭만 수행한다(설명문·예시는 줄 바꿈으로 회피 가능).
    has_ko = any(k in s for k in KOR_SKIP_WORDS)
    has_ell = (ELLIPSIS_UNICODE in s) or ("..." in s)
    return bool(has_ko and has_ell)
# =================================== [03] types & helpers — END ====================================


# ================================= [04] decision per line — START ==================================
def _should_flag_line(ext: str, line: str) -> Optional[Tuple[str, str]]:
    """
    반환: (유형코드, 메시지) 또는 None(정상)
    정책:
      - CODE_EXTS: _is_ellipsis_only_line → 차단, _has_snip_signature → 차단
      - DOC_EXTS : _has_snip_signature → 차단(오탐 최소화)
    """
    if ext in CODE_EXTS:
        if _is_ellipsis_only_line(line):
            return ("ELLIPSIS_ONLY", "줄 전체가 줄임표 기호만으로 구성됨")
        if _has_snip_signature(line):
            return ("SNIP_KO", "‘중략/생략’과 스니핏/줄임표가 같은 줄에서 발견됨")
    elif ext in DOC_EXTS:
        if _has_snip_signature(line):
            return ("SNIP_KO", "문서 줄에서 ‘중략/생략’과 스니핏/줄임표가 동시에 발견됨")
    return None
# ================================== [04] decision per line — END ===================================


# ===================================== [05] scanner — START ========================================
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
# ====================================== [05] scanner — END =========================================


# ====================================== [06] CLI & report — START ==================================
def _print_report(violations: Sequence[Violation]) -> None:
    if not violations:
        print("No‑Ellipsis Gate: ✅ 위반 없음")
        return

    print("No‑Ellipsis Gate: ❌ 위반 발견")
    for path, lineno, code, msg in violations:
        print(f"  - {code:<12} | {path}:{lineno} | {msg}")

    # 가이드(설명과 예시는 '한 줄 동시' 패턴을 피해서 작성)
    print("\n가이드:")
    print("  1) 실제 중략본이면 원본 코드로 교체하세요.")
    print("  2) 정상 문서에서 줄임표를 쓸 수는 있지만,")
    print("     '중략/생략'을 같은 줄에 두고 스니핏 표식(예: <<<, >>> 등)을 함께 쓰지 마세요.")
    print("  3) 필요 시 Gate 규칙은 scripts/no_ellipsis_gate.py에서 조정할 수 있습니다.")


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
# ======================================= [06] CLI & report — END ===================================
