# src/agents/evaluator.py
# ============================== [01] Co-Teacher Evaluator — START ============
"""
Co-teacher(미나쌤): 첫 답변을 보완하는 스트리밍 출력.
- 실스트리밍 우선, 불가 시 문장 단위 분할 폴백
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional, Any
from src.agents._common import stream_llm, _split_sentences


def _system_prompt(mode: str) -> str:
    mode_hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 학생 눈높이에 맞춰 설명.",
        "문장구조분석": "품사/구문 역할을 표로 정리, 핵심 3포인트 요약.",
        "지문분석": "주제/요지/세부정보 구분, 근거 문장 제시.",
    }.get(mode, "핵심→예시→한 줄 정리 순으로 간결히 설명.")
    return (
        "당신은 '미나쌤'이라는 보조 선생님입니다. 비평/채점 금지, "
        "중복 최소화, 쉬운 비유/예시 또는 심화 포인트 보완. " + mode_hint
    )


def _user_prompt(question: str, answer: Optional[str]) -> str:
    a = (answer or "").strip()
    head = "학생 질문:\n" + question.strip()
    if a:
        head += (
            "\n\n[피티쌤의 답변]\n"
            f"{a}\n\n[요청]\n- 비평 금지, 중복 최소화\n"
            "- 쉬운 설명 또는 심화 포인트 보완\n- 핵심 → 예시 → 한 줄 정리"
        )
    else:
        head += (
            "\n\n[요청]\n- 핵심 → 예시 → 한 줄 정리\n"
            "- 질문 의도에 맞는 보완 설명"
        )
    return head


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    미나쌤 보완 스트림.
    - provider가 스트리밍을 지원하면 토막 단위로 yield
    - 아니면 최종 텍스트를 문장 단위로 분할 후 여러 번 yield
    """
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    sys_p = _system_prompt(mode)
    usr_p = _user_prompt(question, answer)

    got_any = False
    for piece in stream_llm(system_prompt=sys_p, user_text=usr_p, split_fallback=True):
        got_any = True
        yield str(piece or "")

    if got_any:
        return

    # 안전망 폴백(이론상 도달 X)
    for seg in _split_sentences(usr_p):
        yield seg
# ============================== [01] Co-Teacher Evaluator — END =============
