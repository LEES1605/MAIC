# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
import fnmatch
import io
import os
import sys
import tokenize
from pathlib import Path
from typing import Iterable, List, Tuple

ELLIPSIS = "\u2026"  # only U+2026 is forbidden; ASCII '...' is OK

# scan extensions
SCAN_EXTS = {
    ".py", ".pyi", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".md", ".txt", ".json", ".csv",
}

# default exclude: docs/markdown/config는 경고만(+ prompts.yaml 임시 완화)
#  - '**/prompts.yaml' 로 풀경로 매칭 보장
#  - '**/pyproject.toml' 로도 보강(편의)
DEFAULT_EXCLUDE = ["docs/**", "**/*.md", "**/pyproject.toml", "**/prompts.yaml"]
# ============================= [01] imports & cfg — END =============================



# ============================ [02] scanners — START =================================
def _py_ellipsis_lines(content: str) -> List[int]:
    """Python: COMMENT 토큰은 무시, 나머지 토큰 문자열에서 U+2026 위치 수집."""
    out: List[int] = []
    try:
        buf = io.StringIO(content)
        for tok in tokenize.generate_tokens(buf.readline):
            if tok.type == tokenize.COMMENT:
                continue
            if ELLIPSIS in tok.string:
                out.append(tok.start[0])
    except Exception:
        for i, line in enumerate(content.splitlines(), start=1):
            if ELLIPSIS in line:
                out.append(i)
    return sorted(set(out))


def _yaml_like_ellipsis_lines(content: str) -> List[int]:
    """YAML/TOML/INI: 행 전체 주석(#/;)은 스킵, 값 영역만 검사."""
    out: List[int] = []
    for i, line in enumerate(content.splitlines(), start=1):
        s = line.lstrip()
        if s.startswith("#") or s.startswith(";"):
            continue
        if ELLIPSIS in line:
            out.append(i)
    return out


def _plain_ellipsis_lines(content: str) -> List[int]:
    out: List[int] = []
    for i, line in enumerate(content.splitlines(), start=1):
        if ELLIPSIS in line:
            out.append(i)
    return out


def _find_ellipsis_in_file(path: Path) -> List[int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    ext = path.suffix.lower()
    if ext == ".py":
        return _py_ellipsis_lines(text)
    if ext in (".yml", ".yaml", ".toml", ".ini", ".cfg"):
        return _yaml_like_ellipsis_lines(text)
    return _plain_ellipsis_lines(text)
# ============================= [02] scanners — END ==================================


# ============================ [03] args — START =====================================
def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Fail CI on U+2026 (Unicode ellipsis). "
            "Skips .py comments and full-line YAML/TOML/INI comments."
        )
    )
    ap.add_argument("--root", default=".", help="Root directory to scan (default: .)")
    ap.add_argument(
        "--fix",
        action="store_true",
        help="Replace U+2026 with ASCII '...' in-place.",
    )
    ap.add_argument(
        "--exclude",
        default=",".join(DEFAULT_EXCLUDE),
        help="Comma-separated glob patterns excluded from blocking (still listed).",
    )
    ap.add_argument(
        "--warn-only",
        action="store_true",
        help="Do not fail the process; only print offenders (useful for docs).",
    )
    return ap.parse_args(argv)
# ============================= [03] args — END ======================================


# ============================ [04] main — START =====================================
def _match_any(path: str, patterns: Iterable[str]) -> bool:
    """Match against full path OR basename to be user-friendly."""
    base = path.rsplit("/", 1)[-1]
    for pat in patterns:
        p = pat.strip()
        if not p:
            continue
        if fnmatch.fnmatch(path, p) or fnmatch.fnmatch(base, p):
            return True
    return False


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    excludes = [p.strip() for p in (args.exclude or "").split(",") if p.strip()]

    blockers: List[Tuple[str, List[int]]] = []
    warnings: List[Tuple[str, List[int]]] = []

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SCAN_EXTS:
            continue

        rel = p.as_posix()
        try:
            lines = _find_ellipsis_in_file(p)
        except Exception:
            lines = []
        if not lines:
            continue

        if _match_any(rel, excludes):
            warnings.append((rel, lines))  # 경고 전용
            continue

        if args.fix:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if ELLIPSIS in txt:
                    p.write_text(txt.replace(ELLIPSIS, "..."), encoding="utf-8")
                    lines2 = _find_ellipsis_in_file(p)
                    if not lines2:
                        continue  # 수정 성공
                    lines = lines2
            except Exception:
                pass
        blockers.append((rel, lines))

    if warnings:
        print("U+2026 (warn-only):")
        for path, lines in warnings:
            head = ", ".join(f"L{n}" for n in lines[:8])
            tail = "" if len(lines) <= 8 else ", ..."
            print(f" - {path}: {head}{tail}")

    if blockers:
        print("U+2026 (blocking):")
        for path, lines in blockers:
            head = ", ".join(f"L{n}" for n in lines[:8])
            tail = "" if len(lines) <= 8 else ", ..."
            print(f" - {path}: {head}{tail}")
        return 0 if args.warn_only else 1

    return 0
# ============================= [04] main — END ======================================



# ============================ [05] entry — START ====================================
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
# ============================= [05] entry — END =====================================
