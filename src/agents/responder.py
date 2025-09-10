# ================================ [01] Answer Stream — START ================================
from __future__ import annotations

from typing import Iterator, Dict, Any, Optional

from src.agents._common import _split_sentences, stream_llm


def _mode_hint(mode: str) -> str:
    """
    모드 key/라벨 모두 허용: grammar|sentence|passage(또는 한글 라벨) → 품질 규칙.
    """
    m = (mode or "").strip().lower()
    if m in ("grammar", "문법", "문법설명"):
        return "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 간결하게."
    if m in ("sentence", "문장", "문장구조분석"):
        return "품사/구문 역할을 표기하고 핵심 포인트 3개를 요약."
    if m in ("passage", "지문", "지문분석"):
        return "주제·요지·세부정보를 구분하고 근거 문장을 제시."
    return "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명."


def _system_prompt(mode: str) -> str:
    return (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 군더더기를 줄이고, "
        "짧은 문장과 단계적 설명, 소제목/불릿을 사용하세요. " + _mode_hint(mode)
    )


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, Any]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - provider가 스트리밍이면 토막 그대로,
    - 아니면 공통 래퍼가 문장 단위로 나눠 방출.
    """
    system_prompt = _system_prompt(mode)
    yield from stream_llm(system_prompt=system_prompt, user_input=question, split_fallback=True)
# ================================= [01] Answer Stream — END =================================
