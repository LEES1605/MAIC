# ============================= [Co-Teacher Eval] ==============================
from __future__ import annotations

from typing import Dict, Iterator, Optional

from src.agents._common import stream_llm


def _system_prompt(mode: str) -> str:
    """
    보조 선생님(미나쌤) 시스템 프롬프트.
    - 비평/채점 금지, 중복 최소화, 보완 설명/예시 중심.
    """
    mode_hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 학생 눈높이에 맞춰 설명.",
        "문장구조분석": "품사/구문 역할을 표처럼 정리, 핵심 포인트 3개 요약.",
        "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 명확히 제시.",
    }.get(mode, "핵심→예시→한 줄 정리 순으로 간결히 설명.")
    return (
        "당신은 '미나쌤'이라는 보조 선생님(Co-teacher)입니다. "
        "첫 번째 선생님(피티쌤)의 답변을 바탕으로, 학생이 더 쉽게 이해하도록 "
        "중복을 최소화하며 빠진 부분을 보충하고 쉬운 비유/예시 또는 심화 포인트를 "
        "추가하세요. 비평/채점/메타 피드백은 금지. " + mode_hint
    )


def _user_prompt(question: str, answer: Optional[str]) -> str:
    """
    미나쌤 사용자 프롬프트 구성:
    - 피티쌤 답변이 있으면 이를 근거로 '보완'에 집중
    - 없으면 질문 자체를 보완 설명
    """
    q = (question or "").strip()
    a = (answer or "").strip()
    head = f"학생 질문:\n{q}"

    if a:
        body = (
            "\n\n[피티쌤의 답변]\n"
            f"{a}\n\n[요청]\n"
            "- 비평 금지, 중복 최소화\n"
            "- 더 쉬운 설명 또는 심화 포인트 보완\n"
            "- 핵심 → 예시 → 한 줄 정리"
        )
    else:
        body = (
            "\n\n[요청]\n"
            "- 핵심 → 예시 → 한 줄 정리\n"
            "- 질문 의도에 맞는 보완 설명"
        )
    return head + body


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    보완 설명 스트리밍.
    - 공통 스트리머(stream_llm)로 위임하여 실제/의사 스트리밍을 통합 처리합니다.
    """
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    sys_p = _system_prompt(mode)
    usr_p = _user_prompt(question, answer)
    # 표준화된 파라미터명(user_prompt) 사용. split_fallback은 공통 유틸이 내장 처리.
    yield from stream_llm(system_prompt=sys_p, user_prompt=usr_p)
# =========================== [Co-Teacher Eval: END] ==========================
