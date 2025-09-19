# ============================ [05] FILE: tests/test_generate_mode_docs_smoke.py — START =============
from __future__ import annotations

import sys
from pathlib import Path


def test_generate_mode_docs_smoke(tmp_path: Path, monkeypatch) -> None:
    """
    문서 생성기가 에러 없이 동작하고, 핵심 섭션 헤더/표준 섹션명이 포함되는지 확인.
    - 레포 루트를 PYTHONPATH에 추가해 import 경로를 고정
    - 생성 결과: docs/_gpt/_generated/MODES.md
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from tools.generate_mode_docs import main

    # 실행
    rc = main()
    assert rc == 0

    out = Path("docs/_gpt/_generated/MODES.md")
    assert out.exists(), "generated MODES.md must exist"

    txt = out.read_text(encoding="utf-8")
    # 공통 헤더와 표준 섹션 헤더 확인
    assert "# MAIC 모드 가이드 (자동 생성)" in txt
    assert "### 섹션 순서" in txt
    # 표준 섹션명 중 일부 샘플
    assert "근거/출처" in txt
# ============================= [05] FILE: tests/test_generate_mode_docs_smoke.py — END =============
