# ============================= [Co-Teacher Evaluator] ============================
from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from src.agents._common import stream_llm


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    보완 스트림(미나쌤).
    - 피티쌤 답변을 바탕으로, 중복은 줄이고 빠진 부분을 보완.
    - 실스트리밍 우선, 아니면 문장 분할로 의사-스트리밍.
    """
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    # SSOT prompts (존재하면 사용, 없으면 안전 폴백)
    try:
        from src.core.prompts import (  # type: ignore
            system_prompt_for_evaluator as _spe,
            user_prompt_for_evaluator as _upe,
        )
        sys_p = _spe(mode, ctx)
        usr_p = _upe(question, answer)
    except Exception:
        sys_p = (
            "당신은 보조 선생님입니다. 첫 답변을 바탕으로 더 쉽게 이해할 "
            "예시/핵심/한 줄 정리를 보완하세요. 비평은 금지."
        )
        head = "학생 질문:\n" + question.strip()
        tail = ""
        if (answer or "").strip():
            tail = "\n\n[첫 답변 기반 보완 요청]"
        usr_p = head + tail

    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=usr_p,
        split_fallback=True,
    )
