# [P4-06] START: tests/test_sentence_prompt_template.py (NEW)
from __future__ import annotations

from src.modes.types import Mode
from src.modes.router import ModeRouter


def test_sentence_prompt_contains_bracket_section() -> None:
    r = ModeRouter()
    b = r.render_prompt(mode=Mode.SENTENCE, question="Analyze this sentence.")
    up = b.prompt
    assert "괄호 규칙 라벨 표준" in up
    assert "라벨:" in up
    assert "[S I] [V stayed] [M at home]" in up
# [P4-06] END: tests/test_sentence_prompt_template.py
