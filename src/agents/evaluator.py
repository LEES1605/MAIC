# ============================= [Co-Teacher Evaluator] ============================
from __future__ import annotations

import importlib
from typing import Any, Dict, Iterator, Optional

from src.agents._common import stream_llm


def _compose_prompts(
    *,
    mode: str,
    question: str,
    answer: Optional[str],
    ctx: Optional[Dict[str, Any]],
) -> tuple[str, str]:
    """
    system/user prompt를 SSOT에서 가져오되, 동적 import로 처리한다.
    SSOT 미존재/실패 시 안전한 기본 프롬프트로 폴백한다.
    """
    sys_p: Optional[str] = None
    usr_p: Optional[str] = None

    try:
        mod = importlib.import_module("src.core.prompts")
        f_sys = getattr(mod, "system_prompt_for_evaluator", None)
        f_usr = getattr(mod, "user_prompt_for_evaluator", None)
        if callable(f_sys):
            sys_p = str(f_sys(mode, ctx))
        if callable(f_usr):
            usr_p = str(f_usr(question, answer))
    except Exception:
        pass

    if not sys_p:
        sys_p = (
            "당신은 보조 선생님입니다. 첫 답변을 바탕으로 더 쉽게 이해할 "
            "예시/핵심/한 줄 정리를 보완하세요. 비평은 금지."
        )
    if not usr_p:
        head = "학생 질문:\n" + (question or "").strip()
        tail = "\n\n[첫 답변 기반 보완 요청]" if (answer or "").strip() else ""
        usr_p = head + tail

    return sys_p, usr_p


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    보완 스트림(미나쌤).
    - 피티쌤 답변을 바탕으로 부족한 부분을 보완한다.
    - 공통 stream_llm 사용으로 실스트리밍/폴백을 일원화한다.
    """
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    sys_p, usr_p = _compose_prompts(
        mode=mode,
        question=question,
        answer=answer,
        ctx=ctx,
    )
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=usr_p,
        split_fallback=True,
    )
