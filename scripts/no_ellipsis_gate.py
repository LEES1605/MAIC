#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ======================= [01] module docstring & imports — START =======================
"""
No-Ellipsis Gate
- 목적: 코드/문서에 '중략본' 유입을 방지한다.

- 정책:
  1) 코드 파일에서 '줄 전체가 ... 또는 …' 인 라인은 차단한다.
  2) (코드/문서 공통) 아래 **두 조건을 동시에 만족**하면 차단한다:
     - '중략' 또는 '생략'
     - 아래 중 하나: U+2026(수평 생략기호) / 점 세 개(`...`) / 스니핏 마커(연속 꺾쇠 등)

- 거짓 양성 최소화:
  * 일반 텍스트 내 자연스러운 U+2026은 허용
  * YAML/MD 등은 2) 조건에서만 검사(문서 끝 구분자 등 오탐 최소화)

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
from typing import Iterable, List, NamedTuple, Optional, Sequence
# ======================== [01] module docstring & imports — END ========================


# =========================== [02] constants & settings — START =========================
ELLIPSIS_UNICODE = "\u2026"  # …

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

# 문서류: 엄격도 완화 (스니핏/중략 조합만 검사)
DOC_EXTS = {".md", ".rst", ".txt", ".mdx", ".yaml", ".yml"}

# 제외 디렉터리/파일
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", ".venv", "venv",
    "__pycache__", "node_modules", "build", "dist",
}
EXCLUDED_FILES = {"no_ellipsis_gate.py"}  # 자기검열 방지

# 스니핏 마커(검출 토큰) — 원문 토큰은 코드 내부에서만 보관
SNIP_TOKENS = (
    "<" * 3,          # "<<<"
    ">" * 3,          # ">>>"
    "<" * 2 + "snip" + ">" * 2,   # "<<snip>>"
    "<" * 2 + "SNIP" + ">" * 2,   # "<<SNIP>>"
    "—8<—",
    "8<",
)

# 한국어 생략어 키워드
KOR_SKIP_WORDS = ("중략", "생략")
# ============================ [02] constants & settings — END ==========================


# ============================== [03] types & helpers — START ==========================
class Violation(NamedTuple):
    """
    위반 레코드: (파일경로, 라인번호, 유형코드, 메시지)
    유형코드:
      - ELLIPSIS_ONLY : 줄 전체가 … 또는 ... 만으로 구성
      - SNIP_KO       : '중략/생략' + (U+2026/점3개/스니핏) 조합
    """
    path: Path
    lineno: int
    code: str
    msg: str


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name in EXCLUDED_FILES:
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
    # '중략/생략' + (… 또는 ...) 의 동시 등장(한 라인 기준)
    if any(k in s for k in KOR_SKIP_WORDS) and (ELLIPSIS_UNICODE in s or "..." in s):
        return True
    return False


def _should_flag_line(ext: str, line: str) -> Optional[tuple[str, str]]:
    """
    반환:
      (유형코드, 메시지) 또는 None(정상)
    정책:
      - CODE_EXTS: _is_ellipsis_only_line → 차단, _has_snip_signature → 차단
      - DOC_EXTS : _has_snip_signature → 차단 (오탐 최소화)
    """
    if ext in CODE_EXTS:
        if _is_ellipsis_only_line(line):
            return ("ELLIPSIS_ONLY", "줄 전체가 '…' 또는 '...'로만 구성됨")
        if _has_snip_signature(line):
            return ("SNIP_KO", "‘중략/생략’ + (U+2026/점3개/스니핏) 조합")
    elif ext in DOC_EXTS:
        if _has_snip_signature(line):
            return ("SNIP_KO", "문서 내 ‘중략/생략’ + (U+2026/점3개/스니핏) 조합")
    return None
# =============================== [03] types & helpers — END ===========================


# ================================ [04] core scan — START ==============================
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
# ================================= [04] core scan — END ===============================


# =============================== [05] reporting & cli — START =========================
def _print_report(violations: Sequence[Violation]) -> None:
    if not violations:
        print("No-Ellipsis Gate: ✅ 위반 없음")
        return

    print("No-Ellipsis Gate: ❌ 위반 발견")
    for path, lineno, code, msg in violations:
        print(f"  - {code:<13} | {path}:{lineno} | {msg}")

    # 가이드(같은 줄에 '중략/생략'과 점3개/생략문자/스니핏이 함께 오지 않도록 문구 분리)
    print("\n가이드:")
    print("  1) 실제 '중략본'이라면 해당 파일을 원본 코드로 교체하세요.")
    print("  2) 정상 문서의 U+2026(…) 표기는 허용됩니다.")
    print("     단, '중략' 또는 '생략'과 스니핏 마커(연속 꺾쇠 등)의 조합은 금지입니다.")
    print("  3) 필요 시 Gate 규칙은 scripts/no_ellipsis_gate.py에서 조정할 수 있습니다.")


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
# ================================ [05] reporting & cli — END ==========================


# =================================== [06] entrypoint — START ==========================
if __name__ == "__main__":
    raise SystemExit(main())
# ==================================== [06] entrypoint — END ===========================
