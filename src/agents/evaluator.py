# ============================ [01] AGENT: EVALUATOR — START ============================
"""
평가·보완 에이전트 (2차 피드백)
- 목표: 주 답변을 '친절하게' 평가하고, 누락/오해소지/난이도를 보완
- 산출 형식(권장):
  1) 한 줄 판정(정확/부분정확/부족)
  2) 핵심 보완점 2~3개 (bullet)
  3) 더 쉬운 예문 1개 (선택)
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from src.llm import providers


def _compose_prompts(
    answer: str,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    a = (answer or "").strip()
    q = (question or "").strip()
    m = (mode or "문법설명").strip()

    sys = (
        "너는 학생 친화적인 '코치'야. 주 답변의 정확성, 누락, 난이도를 간결히 평가하고, "
        "꼭 필요한 보완만 제시해. 폄하 금지, 비난 금지. 말투는 따뜻하고 간단하게."
    )
    if m == "문장구조분석":
        sys += " S/V/O/C/M 용어를 그대로 사용하되, 의미가 어려우면 한글로 풀어줘."
    elif m == "지문분석":
        sys += " 요지/구조/핵심어 기준으로 평가·보완."

    wants = (
        "아래 형식을 꼭 지켜줘:\n"
        "1) 판정: 정확/부분정확/부족 중 하나\n"
        "2) 보완: • … • … (2~3줄)\n"
        "3) 쉬운 예문: … (있으면 1개)"
    )

    hints = []
    if isinstance(ctx, dict) and ctx.get("source_label"):
        hints.append(f"출처힌트={ctx.get('source_label')}")

    hint_block = "\n".join(hints) if hints else "추가 힌트 없음"

    user = (
        f"[질문]\n{q}\n\n[주답변]\n{a}\n\n[모드]\n{m}\n\n[요청]\n{wants}\n\n[힌트]\n{hint_block}"
    )
    return {"system": sys, "user": user}


def evaluate_stream(
    *,
    answer: str,
    question: str,
    mode: str = "문법설명",
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    주 답변에 대한 평가·보완을 스트리밍으로 제공합니다.
    공급자가 콜백 스트리밍을 지원하지 않으면, 최종 텍스트를 글자 단위로 흘립니다.
    """
    prompts = _compose_prompts(answer, question, mode, ctx)

    try:
        acc: list[str] = []

        def _on_token(t: str) -> None:
            acc.append(str(t or ""))

        res = providers.call_with_fallback(
            system=prompts["system"],
            prompt=prompts["user"],
            temperature=0.2,
            stream=True,
            on_token=_on_token,
        )
        full = "".join(acc) if acc else str(res.get("text") or "")
        if not full:
            full = "(평가 결과가 비어있어요)"

        for ch in full:
            yield ch
    except Exception as e:
        yield f"(오류) {type(e).__name__}: {e}"
# ============================= [01] AGENT: EVALUATOR — END =============================
