"""
[WAVE-0] Sanity Test: Ensure deleted modules do not exist and are not referenced.

이 테스트는 '삭제 대상 파일'이 리포에서 제거되었는지, 그리고
남아 있는 코드 어디에서도 해당 모듈 경로를 참조하지 않는지를 보증한다.

규약:
- 파일 존재 검사: 각 경로가 물리적으로 존재하면 실패
- 참조 검사: 전체 리포의 *.py를 훑어 문자열 기반으로 간단 탐지
  (정확한 AST 매칭보다는 '중복/나열 참조'를 잡아내기 위한 보수적 가드)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Tuple

# 리포 루트 추정: tests/ 상위가 리포 루트라고 가정 (Actions/pytest 표준)
REPO_ROOT = Path(__file__).resolve().parents[1]

# 삭제 대상(상대 경로)
DEAD_PATHS: Tuple[str, ...] = (
    "src/features/build_flow.py",
    "src/features/ui_header.py",
    "src/features/drive_card.py",
    "src/ui_admin.py",
    "src/ui_components.py",
    "src/ui_theme.py",
    "src/common/utils.py",
    "src/rag_engine.py",
    "src/rag/quality.py",
    "src/compat/llama.py",
)

# 문자열 기반 참조 패턴(모듈 경로 형태)
# - import src.features.build_flow
# - from src.features import build_flow
DEAD_MODULE_PATTERNS: Tuple[str, ...] = (
    "src.features.build_flow",
    "src.features.ui_header",
    "src.features.drive_card",
    "src.ui_admin",
    "src.ui_components",
    "src.ui_theme",
    "src.common.utils",   # 만약 common을 패키지로 사용했다면 대비
    "src.rag_engine",
    "src.rag.quality",
    "src.compat.llama",
)


def _iter_python_files(root: Path) -> Iterable[Path]:
    """리포 내 파이썬 파일을 순회하되, 일부 디렉터리는 제외한다."""
    EXCLUDE_DIRS = {
        ".git",
        ".github",
        "__pycache__",
        ".venv",
        "venv",
        "site-packages",
        "dist",
        "build",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)
        # 제외 디렉터리 필터
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                yield p / fname


def test_deleted_files_do_not_exist() -> None:
    """삭제 대상 파일이 물리적으로 존재하지 않아야 한다."""
    missing: List[str] = []
    existing: List[str] = []
    for rel in DEAD_PATHS:
        p = REPO_ROOT / rel
        if p.exists():
            existing.append(rel)
        else:
            missing.append(rel)
    assert not existing, (
        "다음 파일이 아직 리포에 남아 있습니다(삭제 필요):\n- " + "\n- ".join(existing)
    )
    # missing 목록 출력은 디버깅 힌트용
    assert missing, "DEAD_PATHS가 비어있거나 경로 계산에 문제가 있을 수 있습니다."


def test_no_remaining_references_to_dead_modules() -> None:
    """리포 전체에서 삭제된 모듈 이름을 더 이상 참조하지 않아야 한다."""
    offenders: List[str] = []
    for py in _iter_python_files(REPO_ROOT):
        # 이 테스트 파일 자체의 경로는 제외(자기 자신이 패턴을 포함)
        if py.name == Path(__file__).name:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # pragma: no cover - 드문 파일 인코딩 이슈 보호
            raise AssertionError(f"파일을 읽을 수 없습니다: {py}") from e

        for pat in DEAD_MODULE_PATTERNS:
            if pat in text:
                offenders.append(f"{py} :: contains '{pat}'")

    assert not offenders, (
        "삭제된 모듈을 참조하는 코드가 남아 있습니다:\n- " + "\n- ".join(offenders)
    )
