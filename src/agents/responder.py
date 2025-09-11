# ================================ [Responder] =================================
from __future__ import annotations

from typing import Dict, Iterator, Optional

from src.agents._common import stream_llm


def _system_prompt(mode: str) -> str:
    """
    주답변(피티쌤) 시스템 프롬프트.
    - 모드에 따라 설명 톤/구성을 살짝 조정합니다.
    """
    hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순으로 쉽게 설명하세요.",
        "문장구조분석": "품사/구문 역할을 표처럼 정리하고 핵심 포인트 3개를 요약하세요.",
        "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 제시하세요.",
    }.get(mode, "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명하세요.")
    return (
        "당신은 학생을 돕는 영어 선생님(피티쌤)입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요. " + hint
    )


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    주답변 스트리밍 제너레이터.
    - 공통 스트리머(stream_llm)로 위임하여 실제/의사 스트리밍을 통합 처리합니다.
    """
    sys_p = _system_prompt(mode)
    # 표준화된 파라미터명(user_prompt) 사용. split_fallback은 공통 유틸이 내장 처리.
    yield from stream_llm(system_prompt=sys_p, user_prompt=question)
# ============================== [Responder: END] ==============================
