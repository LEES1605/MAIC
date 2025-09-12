# src/agents/responder.py
# ================================ Answer Stream ================================
from __future__ import annotations

from typing import Iterator, Optional, Dict
from src.agents._common import stream_llm


def _system_prompt(mode: str) -> str:
    """
    피티쌤(주답변) 시스템 프롬프트.
    - 모드 키('grammar'|'sentence'|'passage')와 한글 라벨을 모두 인식.
    - 간결·단계·예시 우선. 과장/불필요한 수식 금지.
    """
    m = (mode or "").strip().lower()
    if m in ("grammar", "문법", "문법설명"):
        hint = "핵심 규칙 → 간단 예시 → 흔한 오해 순서로, 문장 짧게."
    elif m in ("sentence", "문장", "문장구조분석"):
        hint = (
            "괄호규칙으로 구문을 먼저 제시하고, 품사/역할 표를 간단히. "
            "핵심 포인트 3개를 한 줄씩."
        )
    elif m in ("passage", "지문", "지문분석"):
        hint = "주제·요지·세부 근거를 구분하고, 쉬운 예시로 평이화."
    else:
        hint = "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명."

    return (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요. " + hint
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
