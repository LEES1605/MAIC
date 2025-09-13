# [03] START: tests/test_evaluator_prompt_shape.py (NEW)
from __future__ import annotations

from src.agents.evaluator import build_eval_prompt


def test_build_eval_prompt_contains_sections() -> None:
    sys_p, usr_p = build_eval_prompt(
        question="Why is the comma needed here?",
        answer="Because it separates clauses.",
        mode="grammar",
        source_label="[AI지식]",
    )

    assert "미나쌤" in sys_p
    assert "## 평가 기준" in usr_p
    assert "## 출력 스키마" in usr_p
    assert "## 학생 답변(평가 대상)" in usr_p
    assert "출처 라벨" in usr_p
# [03] END: tests/test_evaluator_prompt_shape.py (NEW)
