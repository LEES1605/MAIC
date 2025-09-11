# ================================ [Answer Stream] ================================
from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from src.agents._common import stream_llm


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - 로컬 헬퍼 정의 금지(공통 모듈 사용).
    - provider가 실스트리밍을 지원하면 그대로, 아니면 문장 분할로 의사-스트리밍.
    """
    # SSOT system prompt (존재하면 사용, 없으면 안전 폴백)
    try:
        from src.core.prompts import system_prompt_for_responder as _spr
        sys_p = _spr(mode, ctx)
    except Exception:
        sys_p = (
            "당신은 학생을 돕는 영어 선생님입니다. 핵심→예시→한 줄 정리 순서로 "
            "짧고 명확하게 설명하세요."
        )

    # 호출부-정의부 계약: user_prompt 사용, split_fallback 제어
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=question,
        split_fallback=True,
    )
