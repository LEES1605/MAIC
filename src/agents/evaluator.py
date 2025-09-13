# [32B] START: src/agents/evaluator.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Iterator, Optional, Dict

from src.agents._common import stream_llm
from src.core.prompt_loader import (
    eval_instructions_for,
    eval_user_prompt_for,
    get_bracket_rules,
)


def _system_for_eval(mode: str) -> str:
    """
    평가자(system) 프롬프트 구성.
    - 기본은 prompts.yaml → modes.<라벨>.eval
    - 문장구조분석 모드는 괄호 규칙을 system 뒤에 부록으로 첨부
    """
    sys_p = eval_instructions_for(mode)
    if mode in ("sentence", "문장구조분석"):
        rules = get_bracket_rules()
        sys_p = f"{sys_p}\n\n[괄호 규칙(참고)]\n{rules}"
    return sys_p


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: str,
    ctx: Optional[Dict[str, str]] = None,
) -> Iterator[str]:
    """
    미나쌤 평가 스트리밍 제너레이터.
    - system: prompts.yaml → modes.<라벨>.eval (sentence는 괄호 규칙 첨부)
    - user:   prompts.yaml → modes.<라벨>.eval_user (미존재 시 기본 템플릿)
    """
    sys_p = _system_for_eval(mode)
    usr_p = eval_user_prompt_for(mode, question, answer, ctx or {})
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=usr_p,
        split_fallback=True,
    )
# [32B] END: src/agents/evaluator.py
