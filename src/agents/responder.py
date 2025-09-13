# [31B] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Iterator, Optional, Dict
from src.agents._common import stream_llm

# SSOT 프롬프트 로더
from src.core.prompt_loader import system_prompt_for, user_prompt_for


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, str]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - system: prompts.yaml → modes.<라벨>.system (핫리로드)
    - user:   prompts.yaml → modes.<라벨>.user   (미존재 시 question 폴백)
    - split_fallback=True: 콜백 미지원 provider에서 문장단위 의사 스트리밍
    """
    sys_p = system_prompt_for(mode)
    usr_p = user_prompt_for(mode, question, ctx or {})
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=usr_p,
        split_fallback=True,
    )
# [31B] END: src/agents/responder.py
