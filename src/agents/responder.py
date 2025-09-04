# ============================ [01] AGENT: RESPONDER — START ============================
"""
주 답변 에이전트 (자료 기반 1차 응답)
- 목표: 학생 눈높이로 간결한 설명 + 예문 1개
- 스트리밍 지원: 공급자가 콜백 스트리밍을 지원하지 않더라도, 최종 텍스트를 '글자 단위'로 흘려서 UX 유지
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from src.llm import providers


def _compose_prompts(question: str, mode: str, ctx: Optional[Dict[str, Any]]) -> Dict[str, str]:
    q = (question or "").strip()
    m = (mode or "문법설명").strip()

    sys = (
        "모든 출력은 한국어. 초등~중등 학생 눈높이. 과도한 배경설명 금지. "
        "핵심 규칙은 3~5개 bullet로 요약하고, 간단한 예문을 1개 포함. "
        "모르면 모른다고 말하고, 필요한 경우 추가 질문 1개 제안."
    )
    if m == "문장구조분석":
        sys += " S/V/O/C/M를 단계적으로 식별하고 불확실성은 '약 n%'로 표기."
    elif m == "지문분석":
        sys += " 먼저 한 줄 요지 → 구조 요약 → 핵심어 3~6개(이유 포함) 제시."

    hints = []
    if isinstance(ctx, dict):
        if ctx.get("hits"):
            hints.append("참고자료가 발견되었습니다.")
        if ctx.get("source_label"):
            hints.append(f"출처힌트={ctx.get('source_label')}")

    hint_block = "\n".join(hints) if hints else "참고자료 없음"

    user = f"[질문]\n{q}\n\n[모드]\n{m}\n\n[힌트]\n{hint_block}"
    return {"system": sys, "user": user}


def answer_stream(
    question: str,
    mode: str = "문법설명",
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    주 답변을 '토큰 스트림' 형태로 산출합니다.
    공급자가 콜백 스트리밍을 지원하면 그대로 사용, 아니면 결과 텍스트를 글자 단위로 흘립니다.
    예외가 나면 사람 친화적 메시지 한 줄을 흘린 뒤 종료합니다.
    """
    prompts = _compose_prompts(question, mode, ctx)

    try:
        acc: list[str] = []

        def _on_token(t: str) -> None:
            # 콜백 기반 스트리밍 누적
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
            full = "(응답이 비어있어요)"

        # 스트리밍(공급자 콜백 결과 또는 폴백 텍스트)
        for ch in full:
            yield ch
    except Exception as e:
        yield f"(오류) {type(e).__name__}: {e}"
# ============================= [01] AGENT: RESPONDER — END =============================
