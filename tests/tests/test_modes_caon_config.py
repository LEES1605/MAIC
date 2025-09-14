# [03] START: tests/test_modes_canon_config.py
from __future__ import annotations

from pathlib import Path

import pytest

from src.modes.profiles import get_profile
from src.modes.types import Mode


def test_canon_adds_required_sections(tmp_path: Path) -> None:
    """
    _canon.yaml의 required가 없어도 Fallback required로 보강되고,
    있으면 설정 기준으로 보강되는지 확인한다.
    """
    # 1) SSOT 미지정: Fallback으로 '근거/출처'가 반드시 포함되어야 함
    prof_g = get_profile(Mode.GRAMMAR)
    assert "근거/출처" in prof_g.sections

    # 2) SSOT 지정: 최소 구성의 _canon.yaml을 생성해도 정상 보강
    root = tmp_path / "docs/_gpt"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    (root / "modes" / "_canon.yaml").write_text(
        "modes:\n"
        "  grammar:\n"
        "    order: [\"핵심 규칙\", \"근거/출처\"]\n"
        "    required: [\"근거/출처\"]\n",
        encoding="utf-8",
    )
    prof_g2 = get_profile(Mode.GRAMMAR, ssot_root=root)
    assert "근거/출처" in prof_g2.sections


def test_canon_synonyms_normalized(tmp_path: Path) -> None:
    """
    synonyms가 있으면 동의어가 표준명으로 치환된다.
    """
    root = tmp_path / "docs/_gpt"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    (root / "modes" / "_canon.yaml").write_text(
        "modes:\n"
        "  passage:\n"
        "    order: [\"요지/주제\", \"근거/출처\"]\n"
        "    required: [\"근거/출처\"]\n"
        "synonyms:\n"
        "  \"핵심 요지\": \"요지/주제\"\n",
        encoding="utf-8",
    )
    # SSOT 템플릿이 없어도, 내장 프로필 섹션 + 동의어/순서 규칙으로 정규화된다.
    prof_p = get_profile(Mode.PASSAGE, ssot_root=root)
    assert prof_p.sections[0] == "요지/주제"
    assert "근거/출처" in prof_p.sections
# [03] END: tests/test_modes_canon_config.py
