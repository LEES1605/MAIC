# [29B] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Iterator, Optional, Dict
from src.agents._common import stream_llm

# SSOT 프롬프트 로더
from src.core.prompt_loader import system_prompt_for


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, str]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - prompts.yaml → system 프롬프트 사용(핫리로드)
    - 공통 SSOT(stream_llm)만 호출하여 중복 제거
    - split_fallback=True: 콜백 미지원 provider에서 문장단위 의사 스트리밍
    """
    sys_p = system_prompt_for(mode)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=question,
        split_fallback=True,
    )
# [29B] END: src/agents/responder.py
