# src/agents/responder.py
# ================================ [01] Answer Stream — START =================
from __future__ import annotations

from typing import Iterator, Dict, Any, Optional
import re

from src.agents._common import stream_llm, _split_sentences  # public helpers


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
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - providers.stream_text → call_with_fallback(stream/callback) 순으로 시도
    - 전부 불가하면 문장 분리 기반 의사-스트리밍
    """
    sys_p = _system_prompt(mode)

    # 1) 공용 스트리머 사용: 호출 키는 user_text로 통일
    got_any = False
    for piece in stream_llm(system_prompt=sys_p, user_text=question, split_fallback=True):
        got_any = True
        yield str(piece or "")

    if got_any:
        return

    # 2) 폴백 (이론상 도달 X): 안전망
    for seg in _split_sentences(str(question or "")):
        yield seg
# ================================ [01] Answer Stream — END ===================
