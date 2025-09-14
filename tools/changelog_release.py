# [RC1] START: tools/changelog_release.py
from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")

# 환경변수
#   RELEASE_VERSION : 예) v0.2.0  (필수)
#   RELEASE_DATE    : 예) 2025-09-14 (선택, 기본 오늘)
#   REPO            : 예) owner/repo (선택, [Unreleased] 비교 링크 갱신에 사용)
# 동작:
#  - [Unreleased] 섹션 내용을 추출하여 "## [<version>] - <date>" 블록으로 내려쓰기
#  - [Unreleased] 헤더는 유지(빈 상태)
#  - [Unreleased] 비교 링크를 <version>...HEAD로 갱신(가능하면)


def _read_text(p: Path) -> str:
    if not p.exists():
        raise FileNotFoundError(f"changelog not found: {p}")
    return p.read_text(encoding="utf-8")


def _write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def _extract_unreleased(body: str) -> tuple[str, int, int]:
    """
    [Unreleased] 블록의 본문과 라인 범위를 반환.
    반환: (본문, start_idx, end_idx)
    """
    lines = body.splitlines()
    # '## [Unreleased]' 헤더 찾기
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("## [Unreleased]"):
            start = i
            break
    if start is None:
        raise ValueError("Unreleased section not found")

    # 다음 섹션(## [ ...) 또는 EOF까지
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## [") and "Unreleased" not in lines[j]:
            end = j
            break

    # 헤더 다음 줄부터 end-1까지가 본문
    content_lines = lines[start + 1 : end]
    # 위아래 공백 제거
    while content_lines and not content_lines[0].strip():
        content_lines.pop(0)
    while content_lines and not content_lines[-1].strip():
        content_lines.pop()
    return ("\n".join(content_lines).strip(), start, end)


def _update_unreleased_compare_link(body: str, version: str, repo: str | None) -> str:
    """
    하단의 [Unreleased]: https://github.com/<repo>/compare/<X>...HEAD 를
    [Unreleased]: https://github.com/<repo>/compare/<version>...HEAD 로 갱신.
    (repo 미지정 시 본문은 그대로 둠)
    """
    if not repo:
        return body
    pattern = re.compile(
        r"^\[Unreleased\]:\s*https://github\.com/.+?/compare/.+?\.\.\.HEAD\s*$",
        re.MULTILINE,
    )
    repl = f"[Unreleased]: https://github.com/{repo}/compare/{version}...HEAD"
    if pattern.search(body):
        return pattern.sub(repl, body)
    # 링크 라인이 없으면 끝에 추가
    return body.rstrip() + "\n" + repl + "\n"


def main() -> int:
    version = (os.getenv("RELEASE_VERSION") or "").strip()
    if not version:
        print("[release] ERROR: env RELEASE_VERSION is required (e.g., v0.2.0)", file=sys.stderr)
        return 2
    rel_date = (os.getenv("RELEASE_DATE") or "").strip() or str(date.today())
    repo = (os.getenv("REPO") or "").strip() or None

    raw = _read_text(CHANGELOG)
    content, s, e = _extract_unreleased(raw)

    # 비어 있으면 'No changes.'로라도 내려쓰기
    if not content:
        content = "_No changes._"

    lines = raw.splitlines()
    # 새로운 버전 블록 삽입 지점: Unreleased 블록 바로 아래
    new_block = []
    new_block.append(f"## [{version}] - {rel_date}")
    new_block.append(content)
    new_block.append("")  # 블록 구분 공백

    # 기존 [Unreleased] 본문은 비워 두되 헤더 유지
    new_lines = []
    new_lines.extend(lines[: s + 1])  # '## [Unreleased]' 포함
    new_lines.append("")               # 빈 줄 1개
    new_lines.extend(new_block)        # 새 버전 블록
    new_lines.extend(lines[e:])        # 나머지

    updated = "\n".join(new_lines)
    updated = _update_unreleased_compare_link(updated, version, repo)

    _write_text(CHANGELOG, updated)
    print(f"[release] Updated CHANGELOG with {version} ({rel_date}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [RC1] END: tools/changelog_release.py
