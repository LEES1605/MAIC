# [20B] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Iterator, Optional, Dict
from src.agents._common import stream_llm
from src.core.prompt_loader import get_bracket_rules


def _system_prompt(mode: str) -> str:
    """
    피티쌤(주답변) 프롬프트.
    - 문장 모드에서는 '사용자 제공 괄호규칙'을 우선 적용(문서/Secrets/ENV).
    - 과장 금지, 짧은 문장, 단계적 설명.
    """
    m = (mode or "").strip().lower()

    if m in ("sentence", "문장", "문장구조분석", "문장분석"):
        rules = get_bracket_rules()
        hint = (
            "다음 '사용자 괄호규칙'을 반드시 따르세요.\n"
            "<<<BRACKET_RULES>>>\n"
            f"{rules}\n"
            "<<<END_RULES>>>\n"
            "출력 형식: [괄호분석] → [해석] → [핵심 포인트 3개]."
        )
    elif m in ("grammar", "문법", "문법설명"):
        hint = "핵심 규칙 → 간단 예시 → 흔한 오해. 문장 짧게."
    elif m in ("passage", "지문", "지문분석", "지문설명"):
        hint = "요지→쉬운 예시→주제→제목. 근거 문장 인용."
    else:
        hint = "학생 눈높이: 핵심→예시→한 줄 정리."

    return (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 수식은 줄이고, "
        "짧고 명확한 단계적 설명을 사용하세요.\n" + hint
    )


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, str]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - 공통 SSOT(stream_llm)만 호출하여 중복 제거
    - split_fallback=True: 콜백 미지원 provider에서 문장단위 의사 스트리밍
    """
    sys_p = _system_prompt(mode)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=question,
        split_fallback=True,
    )
# [20B] END: src/agents/responder.py
