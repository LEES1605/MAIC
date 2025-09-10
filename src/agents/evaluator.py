# -----------------------------------------------------------------------------
# src/agents/evaluator.py
# 보완(미나쌤) — 공통 stream_llm + SSOT prompts
# -----------------------------------------------------------------------------
from __future__ import annotations
from typing import Dict, Iterator, Optional
from src.agents._common import stream_llm
from src.core.prompts import (
    system_prompt_for_evaluator,
    user_prompt_for_evaluator,
)  # SSOT

def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    미나쌤 보완 스트림.
    - provider가 스트리밍을 지원하면 토막 단위로 yield
    - 아니면 최종 텍스트를 문장 단위로 분할하여 의사-스트리밍
    """
    sys_p = system_prompt_for_evaluator(mode, ctx)
    usr_p = user_prompt_for_evaluator(question, answer)
    yield from stream_llm(system_prompt=sys_p, user_input=usr_p, split_fallback=True)
