# ============================ [01] imports & cfg — START ============================
from __future__ import annotations

import argparse
import io
import os
import sys
import tokenize
from pathlib import Path
from typing import List, Tuple

ELLIPSIS = "\u2026"  # Unicode ellipsis ONLY (ASCII '...' is OK)

# 확장자 정책: 코드/설정/문서 전반을 보되, .py 주석은 무시
SCAN_EXTS = {
    ".py", ".pyi", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".txt", ".json", ".csv",
}
# ============================= [01] imports & cfg — END =============================


# ============================ [02] scanners — START =================================
def _py_ellipsis_lines(path: Path, content: str) -> List[int]:
    """
    Python 파일에서 '주석은 건너뛰고' 나머지 토큰에 포함된 U+2026의 라인 번호를 수집.
    - tokenize 모듈로 COMMENT 토큰을 필터링
    - STRING/NAME/OP 등 모든 비-주석 토큰은 검사
    """
    out: List[int] = []
    try:
        buf = io.StringIO(content)
        for tok in tokenize.generate_tokens(buf.readline):
            tok_type = tok.type
            tok_str = tok.string
            # 주석은 무시
            if tok_type == tokenize.COMMENT:
                continue
            # 나머지 토큰 안에 '…'가 있으면 해당 시작 라인 기록
            if ELLIPSIS in tok_str:
                out.append(tok.start[0])
    except Exception:
        # 토크나이즈 실패 시 라인 단위 폴백(주석 무시는 못 하지만, 실패를 삼키지 않음)
        for i, line in enumerate(content.splitlines(), start=1):
            if ELLIPSIS in line:
                out.append(i)
    return sorted(set(out))


def _yaml_ellipsis_lines(content: str) -> List[int]:
    """
    YAML: 라인이 주석(#)으로 '시작'하면 무시.
    (값 뒤에 오는 '트레일링 주석'까지 완벽 식별하진 않음 — 간단/안전한 규칙)
    """
    out: List[int] = []
    for i, line in enumerate(content.splitlines(), start=1):
        s = line.lstrip()
        if s.startswith("#"):
            continue
        if ELLIPSIS in line:
            out.append(i)
    return out


def _plain_ellipsis_lines(content: str) -> List[int]:
    """그 외 파일 유형: 전체 라인 검사(주석 예외 처리 없음)."""
    out: List[int] = []
    for i, line in enumerate(content.splitlines(), start=1):
        if ELLIPSIS in line:
            out.append(i)
    return out


def _find_ellipsis_in_file(path: Path) -> List[int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    ext = path.suffix.lower()

    if ext == ".py":
        return _py_ellipsis_lines(path, text)
    if ext in (".yml", ".yaml"):
        return _yaml_ellipsis_lines(text)
    return _plain_ellipsis_lines(text)
# ============================= [02] scanners — END ==================================


# ============================ [03] args — START =====================================
def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Fail CI on U+2026 in repository. Skips comments in .py and full-line comments in YAML."
    )
    ap.add_argument("--root", default=".", help="Root directory to scan (default: .)")
    ap.add_argument("--fix", action="store_true", help="Replace with ASCII '...' in-place.")
    return ap.parse_args(argv)
# ============================= [03] args — END ======================================


# ============================ [04] main — START =====================================
def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()

    offenders: List[Tuple[str, List[int]]] = []

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SCAN_EXTS:
            continue

        try:
            lines = _find_ellipsis_in_file(p)
        except Exception:
            lines = []
        if not lines:
            continue

        # --fix: 파일 내 모든 U+2026 → '...' 치환 (주석 포함 전체 치환)
        if args.fix:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if ELLIPSIS in txt:
                    p.write_text(txt.replace(ELLIPSIS, "..."), encoding="utf-8")
                    # 치환 후 재검사(주석/비주석 가릴 필요 없이 없어졌는지만 확인)
                    recheck = _find_ellipsis_in_file(p)
                    if not recheck:
                        continue  # 수정 성공 → 리포팅 제외
                    lines = recheck
            except Exception:
                pass

        offenders.append((p.as_posix(), lines))

    if offenders:
        print("Unicode ellipsis (U+2026) found in:")
        for path, lines in offenders:
            # 최대 8개까지만 라인 표기(너무 길어지지 않게)
            head = ", ".join(f"L{n}" for n in lines[:8])
            tail = "" if len(lines) <= 8 else ", ..."
            print(f" - {path}: found at {head}{tail}")
        return 1

    return 0
# ============================= [04] main — END ======================================


# ============================ [05] entry — START ====================================
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
# ============================= [05] entry — END =====================================
