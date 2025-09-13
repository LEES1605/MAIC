# [01] START: tests/test_modes_ssot_templates.py (NEW FILE)
import pytest

pytest.importorskip("yaml")  # SSOT 템플릿 로딩 검증에 PyYAML 필요

from src.modes.types import Mode
from src.modes.profiles import get_profile


def test_grammar_template_sections():
    prof = get_profile(Mode.GRAMMAR)
    assert "핵심 규칙" in prof.sections
    assert "근거/출처" in prof.sections


def test_passage_template_sections():
    prof = get_profile(Mode.PASSAGE)
    assert "요지/주제" in prof.sections
    assert "근거/출처" in prof.sections
# [01] END: tests/test_modes_ssot_templates.py
