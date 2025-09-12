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
        hint = "핵심 규칙 → 간단 예시 → 흔한 오해. 문장 짧게."
    elif m in ("sentence", "문장", "문장구조분석", "문장분석"):
        hint = "괄호규칙으로 구문 제시→해석→핵심 3개. 표처럼 간결히."
    elif m in ("passage", "지문", "지문분석", "지문설명"):
        hint = "요지→쉬운 예시→주제→제목. 근거 문장 인용."
    else:
        hint = "학생 눈높이: 핵심→예시→한 줄 정리."

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
