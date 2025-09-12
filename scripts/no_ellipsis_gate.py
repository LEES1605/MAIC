# [27A] START: scripts/no_ellipsis_gate.py (FULL REPLACEMENT)
from __future__ import annotations

import argparse
import sys
import os
import re
from pathlib import Path
from typing import List, Tuple, Iterable


# ==========================
# 설정(기본값: 문서/프롬프트 전용)
# ==========================
DEFAULT_INCLUDE = [
    "README.md",
    "prompts.yaml",
    "docs/**/*.md",
    "docs/**/*.rst",
    "docs/**/*.txt",
    "prompts/**/*.md",
    "prompts/**/*.txt",
    "prompts/**/*.yaml",
    "prompts/**/*.yml",
]

DEFAULT_EXCLUDE = [
    ".git/**",
    ".github/**",
    "venv/**",
    ".venv/**",
    "node_modules/**",
    "__pycache__/**",
    "build/**",
    "dist/**",
]

# 코드 파일은 기본적으로 제외(요청 시 --check-code로 opt-in)
CODE_GLOBS = [
    "**/*.py",
    "src/**/*.py",
    "tests/**/*.py",
    "scripts/**/*.py",
]

# 허용 마커(화이트리스트): 프롬프트 문맥에서 사용하는 내부 표식
ALLOWED_MARKERS = [
    "--START_ANSWER--",
    "--END_ANSWER--",
    "--BRACKET_RULES--",
    "--END_BRACKET_RULES--",
]

# 스니핏/줄임표 패턴(화이트리스트 외에는 모두 ‘스니핏’으로 간주)
SNIPPET_PATTERNS = [
    r"<<<?",   # << 또는 <<< (LLM 표식류)
    r">>>?",   # >> 또는 >>>
    r"\[\s*\.\.\.\s*\]",  # [ ... ] 류
    r"\.\.\.",            # ...
    r"…",                 # 단일 문자 줄임표
]


class Violation(Tuple[str, str, int, str]):
    """(code, relpath, lineno, message)"""


def _expand_braces(pattern: str) -> List[str]:
    """'*.{md,txt}' 같은 브레이스 패턴을 fnmatch 용으로 풀어준다."""
    m = re.search(r"\{([^}]+)\}", pattern)
    if not m:
        return [pattern]
    head = pattern[:m.start()]
    tail = pattern[m.end():]
    alts = [x.strip() for x in m.group(1).split(",") if x.strip()]
    out = []
    for a in alts:
        out.extend(_expand_braces(head + a + tail))
    return out


def _path_match_any(p: Path, patterns: Iterable[str], root: Path) -> bool:
    from fnmatch import fnmatch
    rp = str(p.relative_to(root).as_posix())
    for pat in patterns:
        for exp in _expand_braces(pat):
            if fnmatch(rp, exp):
                return True
    return False


def _collect_files(root: Path, includes: List[str], excludes: List[str]) -> List[Path]:
    files: List[Path] = []
    for pat in includes:
        for exp in _expand_braces(pat):
            files.extend(root.glob(exp))
    uniq = []
    seen = set()
    for f in files:
        if f.is_dir():
            continue
        rel = f.resolve()
        if rel in seen:
            continue
        if _path_match_any(f, excludes, root):
            continue
        seen.add(rel)
        uniq.append(f)
    return sorted(uniq)


def _line_is_ellipsis_only(s: str) -> bool:
    t = s.strip()
    return t in ("...", "…")


def _line_has_snippet(s: str) -> bool:
    if any(marker in s for marker in ALLOWED_MARKERS):
        return False
    return any(re.search(pat, s) for pat in SNIPPET_PATTERNS)


def _window(lines: List[str], i: int, radius: int = 2) -> List[Tuple[int, str]]:
    lo = max(0, i - radius)
    hi = min(len(lines), i + radius + 1)
    return [(k, lines[k]) for k in range(lo, hi)]


def _scan_file(path: Path, root: Path) -> List[Violation]:
    txt = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    vios: List[Violation] = []

    # 1) ELLIPSIS_ONLY: 줄 전체가 ... 또는 … 인 경우
    for i, line in enumerate(txt, start=1):
        if _line_is_ellipsis_only(line):
            vios.append(("ELLIPSIS_ONLY", str(path.relative_to(root)), i, "줄 전체가 '…' 또는 '...'로만 구성됨"))

    # 2) SNIP_KO: 같은 파일에서 '중략|생략'과 스니핏이 근접(±2줄)한 경우
    #    - 문서 내 실제 생략본/스니핏 혼용을 금지
    for i, line in enumerate(txt, start=1):
        if re.search(r"(중략|생략)", line):
            for k, near in _window(txt, i - 1, radius=2):
                if _line_has_snippet(near) or _line_is_ellipsis_only(near):
                    vios.append(("SNIP_KO", str(path.relative_to(root)), i, "‘중략/생략’ + 스니핏/…/... 패턴"))
                    break

    return vios


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="No‑Ellipsis Gate (docs/prompts only by default)")
    ap.add_argument("--root", default=".", help="project root")
    ap.add_argument("--include", action="append", default=[], help="additional include glob (can repeat)")
    ap.add_argument("--exclude", action="append", default=[], help="additional exclude glob (can repeat)")
    ap.add_argument("--check-code", action="store_true", help="also scan code (*.py) — opt-in")
    ap.add_argument("--allowed-markers", default=",".join(ALLOWED_MARKERS),
                    help="comma-separated whitelist markers")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()

    # allow runtime extension of allowed markers
    markers = [m.strip() for m in str(args.allowed_markers or "").split(",") if m.strip()]
    ALLOWED_MARKERS[:] = markers  # type: ignore[index]

    includes = list(DEFAULT_INCLUDE)
    excludes = list(DEFAULT_EXCLUDE)

    # user overrides
    includes.extend(args.include or [])
    excludes.extend(args.exclude or [])

    # code scan opt-in
    if args.check_code:
        includes.extend(CODE_GLOBS)

    files = _collect_files(root, includes, excludes)

    all_vios: List[Violation] = []
    for f in files:
        try:
            all_vios.extend(_scan_file(f, root))
        except Exception:
            # 텍스트가 아닌 파일 등은 조용히 패스
            continue

    if not all_vios:
        print("No‑Ellipsis Gate: ✅ 통과")
        return 0

    print("No‑Ellipsis Gate: ❌ 위반 발견")
    for code, rel, ln, msg in all_vios:
        print(f"  - {code:<12} | {root.joinpath(rel)}:{ln} | {msg}")

    print("\n가이드:")
    print("  1) 실제 '중략본'이면 원본 텍스트로 교체하세요.")
    print("  2) 정상 문서의 줄임표는 허용되지만,")
    print("     '중략/생략'과 스니핏 마커의 근접 사용(±2줄)은 금지입니다.")
    print("  3) 프롬프트 표식은 --allowed-markers 에 등록하면 제외됩니다.")
    print("  4) 코드(.py)는 기본 제외이며, 필요 시 --check-code 로 포함하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# [27A] END: scripts/no_ellipsis_gate.py
