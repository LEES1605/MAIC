# ================================ [Answer Stream] ================================
from __future__ import annotations

import importlib
from typing import Any, Dict, Iterator, Optional

from src.agents._common import stream_llm


def _system_prompt(mode: str, ctx: Optional[Dict[str, Any]]) -> str:
    """
    system prompt를 SSOT에서 가져오되, 정적 import 대신 동적 import를 사용해
    mypy의 import-not-found 이슈를 회피한다.
    """
    try:
        mod = importlib.import_module("src.core.prompts")
        fn = getattr(mod, "system_prompt_for_responder", None)
        if callable(fn):
            return str(fn(mode, ctx))
    except Exception:
        pass
    return (
        "당신은 학생을 돕는 영어 선생님입니다. "
        "핵심→예시→한 줄 정리 순서로 짧고 명확하게 설명하세요."
    )


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - 공통 모듈의 stream_llm을 통해 실스트리밍/폴백을 일원화한다.
    - 로컬 헬퍼(_split_sentences/_on_piece/_runner) 정의 금지.
    """
    sys_p = _system_prompt(mode, ctx)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=question,
        split_fallback=True,
    )
