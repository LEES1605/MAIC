# -----------------------------------------------------------------------------
# src/agents/responder.py
# 주답변(피티쌤) — 공통 stream_llm + SSOT prompts
# -----------------------------------------------------------------------------
from __future__ import annotations
from typing import Dict, Iterator, Optional
from src.agents._common import stream_llm
from src.core.prompts import system_prompt_for_responder  # SSOT

def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, object]] = None
) -> Iterator[str]:
    """
    피티쌤 스트리밍 제너레이터.
    - 공통 stream_llm으로 실제/의사 스트리밍 모두 처리
    - 프롬프트는 SSOT(system_prompt_for_responder)
    """
    sys_p = system_prompt_for_responder(mode, ctx)
    yield from stream_llm(system_prompt=sys_p, user_input=question, split_fallback=True)
