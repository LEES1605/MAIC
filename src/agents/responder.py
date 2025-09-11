# src/agents/responder.py
# ================================= [Answer Agent] ==============================
from __future__ import annotations

from typing import Dict, Iterator, Optional

from src.agents._common import stream_llm  # 표준 파사드만 사용


def _system_prompt(mode: str) -> str:
    hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 쉽게 설명하세요.",
        "문장구조분석": "품사/구문 역할을 표처럼 정리하고 핵심 포인트 3개를 요약하세요.",
        "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 제시하세요.",
    }.get(mode, "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명하세요.")
    return (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요. " + hint
    )


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, any]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - 공용 파사드(stream_llm)만 호출 → mypy/테스트 일관성
    """
    sys_p = _system_prompt(mode)
    # 최종 방출 단위를 읽기 좋게 하려면 split_fallback=True 유지
    yield from stream_llm(system_prompt=sys_p, user_prompt=question, split_fallback=True)
