# ============================== [01] Co-Teacher Evaluator — START ==============================
"""
Evaluator agent (Co-teacher mode)

역할
- 첫 번째 답변(지피티)을 '비평'하지 않고, 학생의 이해를 돕도록 '보완'합니다.
- 더 쉬운 설명(비유/예시) 또는 더 심화된 맥락을 추가하되, 중복을 최소화합니다.
- 학생의 질문과 모드(문법설명/문장구조분석/지문분석)에 맞춰 톤과 형식을 조절합니다.

출력 톤
- 짧은 문장, 단계적 설명, 핵심 → 예시 → 한 줄 정리 순서 권장
- 금지: 평가/비판/채점/점수/메타 피드백
- 권장: "추가로 이런 점도 알아두면 좋아요", "쉽게 말하면 …", "심화: …"

Streaming
- 현재 구현은 provider의 비스트리밍 응답을 받아 문장 단위로 나눠 다회 `yield`합니다.
- 실제 토큰 스트리밍 콜백 연동은 후속 단계에서 연결합니다.
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional, Any, List
import inspect
import re


def _system_prompt(mode: str) -> str:
    mode_hint = {
        "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순으로, 초등~중등 눈높이에 맞춰 설명하세요.",
        "문장구조분석": "품사/구문 역할을 표로 정리하고, 핵심 포인트 3개를 간결히 요약하세요.",
        "지문분석": "지문의 주제/요지/세부정보 구분과 근거 문장을 명확히 제시하세요.",
    }.get(mode, "학생 수준에 맞춰 핵심→예시→한 줄 정리 순으로 설명하세요.")

    return (
        "당신은 '미나'라는 이름의 보조 선생님(Co-teacher)입니다. "
        "첫 번째 선생님(지피티)의 답변을 바탕으로 학생이 더 쉽게 이해하도록 "
        "'보완 설명'을 제공합니다. "
        "비평/평가/채점은 금지하며, 중복을 최소화하고 빠진 부분을 보충하거나 "
        "더 쉬운 비유·예시, 또는 심화 포인트를 추가하세요. "
        f"{mode_hint} "
        "스타일: 친절한 한국어, 짧은 문장, 불릿/번호 목록 적극 사용, 과한 이모지는 지양."
    )


def _user_prompt(question: str, answer: Optional[str]) -> str:
    # answer(지피티 응답)이 없을 수도 있으므로 방어적으로 구성
    a = (answer or "").strip()
    head = "학생 질문:\n" + question.strip()
    if a:
        head += (
            "\n\n첫 번째 선생님(지피티)의 답변 요약을 바탕으로 보완해 주세요."
        )
        body = (
            "\n\n[지피티의 답변]\n"
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


def _split_sentences(text: str) -> List[str]:
    """
    아주 단순한 문장 분할. 후속 단계에서 src.llm.streaming 연동 예정.
    """
    if not text:
        return []
    # 문장 끝 기호 기준으로 분리(한국어/영어 혼용)
    parts = re.split(r"(?<=[\.!\?。！？])\s+", text.strip())
    # 빈 토큰 제거, 공백 유지
    return [p for p in parts if p]


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    첫 번째 답변(지피티)을 '기반'으로 학생에게 도움이 되는 보완 설명을 생성해
    문장 단위로 `yield`합니다.

    Parameters
    ----------
    question : str
        학생 질문 원문.
    mode : str
        "문법설명" | "문장구조분석" | "지문분석" 등.
    answer : Optional[str]
        주 답변(지피티)의 전체 텍스트. 없으면 ctx['answer']를 조회합니다.
    ctx : Optional[dict]
        추가 컨텍스트. {'answer': '...'} 형태를 지원합니다.
    """
    # ── 입력 정리 ─────────────────────────────────────────────────────────────
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    system_prompt = _system_prompt(mode)
    user_prompt = _user_prompt(question, answer)

    # ── provider 호출 준비 ────────────────────────────────────────────────────
    try:
        from src.llm import providers as _prov  # type: ignore
    except Exception as e:
        yield f"(오류) provider 로딩 실패: {type(e).__name__}: {e}"
        return

    call = getattr(_prov, "call_with_fallback", None)
    if not callable(call):
        yield "(오류) LLM 어댑터(call_with_fallback)를 사용할 수 없습니다."
        return

    params = inspect.signature(call).parameters

    kwargs: Dict[str, Any] = {}
    if "messages" in params:
        kwargs["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    else:
        # 단일 프롬프트 인터페이스 호환
        joined = system_prompt + "\n\n" + user_prompt
        if "prompt" in params:
            kwargs["prompt"] = joined
        elif "user_prompt" in params:
            kwargs["user_prompt"] = user_prompt
        if "system_prompt" in params:
            kwargs["system_prompt"] = system_prompt
        elif "system" in params:
            kwargs["system"] = system_prompt

    # 스트리밍 콜백 파라미터가 있더라도, 현재 단계에서는 비스트리밍 호출로 통일
    try:
        res = call(**kwargs)
    except Exception as e:
        yield f"(오류) {type(e).__name__}: {e}"
        return

    text = res.get("text") if isinstance(res, dict) else str(res)
    if not text:
        text = (
            "보완할 내용을 찾지 못했어요. 질문을 조금 더 구체적으로 알려줄래요?"
        )

    # ── 문장 단위로 분할하여 다회 yield ───────────────────────────────────────
    for chunk in _split_sentences(text):
        yield chunk
# =============================== [01] Co-Teacher Evaluator — END ===============================
