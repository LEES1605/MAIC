# ============================== [01] Co-Teacher Evaluator — START ==============================
from __future__ import annotations

from typing import Dict, Iterator, Optional, Any

from src.agents._common import _split_sentences, stream_llm


def _mode_hint(mode: str) -> str:
    m = (mode or "").strip().lower()
    if m in ("grammar", "문법", "문법설명"):
        return "핵심 규칙 보완 + 쉬운 예시 + 한 줄 정리."
    if m in ("sentence", "문장", "문장구조분석"):
        return "품사/구문 역할 보완, 핵심 포인트 3개 보강."
    if m in ("passage", "지문", "지문분석"):
        return "근거 문장 보강, 요지/세부 차이 명확화."
    return "핵심→예시→한 줄 정리로 간결히 보완."


def _system_prompt(mode: str) -> str:
    return (
        "당신은 '미나쌤'이라는 보조 선생님(Co‑teacher)입니다. "
        "첫 번째 선생님(피티쌤)의 답변을 바탕으로, 학생이 더 쉽게 이해하도록 "
        "중복을 최소화하며 빠진 부분을 보충하고 쉬운 비유/예시 또는 심화 포인트를 추가하세요. "
        "비평·채점·메타 피드백은 금지. " + _mode_hint(mode)
    )


def _user_prompt(question: str, answer: Optional[str]) -> str:
    a = (answer or "").strip()
    head = "학생 질문:\n" + question.strip()
    if a:
        head += "\n\n첫 번째 선생님(피티쌤)의 답변을 바탕으로 보완해 주세요."
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
    ctx: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """
    미나쌤 보완 스트림.
    - provider 스트리밍이면 그대로,
    - 아니면 먼저 한 번에 방출(요약형), 그마저 없으면 문장 단위 폴백.
    """
    if not answer and ctx and isinstance(ctx, dict):
        maybe = ctx.get("answer")
        if isinstance(maybe, str):
            answer = maybe

    sys_p = _system_prompt(mode)
    usr_p = _user_prompt(question, answer)

    # 1차: 스트리밍/폴백(한 번에) 시도
    got_any = False
    for piece in stream_llm(system_prompt=sys_p, user_input=usr_p, split_fallback=False):
        got_any = True
        yield str(piece or "")

    if got_any:
        return

    # 2차: 문장 분할 폴백
    try:
        from src.llm import providers as prov
        call = getattr(prov, "call_with_fallback", None)
    except Exception:
        call = None

    if callable(call):
        try:
            res = call(messages=[{"role": "system", "content": sys_p},
                                 {"role": "user", "content": usr_p}])
        except Exception as e:  # pragma: no cover
            yield f"(오류) {type(e).__name__}: {e}"
            return
        txt = res.get("text") if isinstance(res, dict) else str(res)
        if not txt:
            txt = "보완할 내용을 찾지 못했어요. 질문을 조금 더 구체적으로 알려줄래요?"
        for chunk in _split_sentences(txt):
            yield chunk
        return

    yield "보완 에이전트를 사용할 수 없어서, 주 답변만 제공했어요."
# =============================== [01] Co-Teacher Evaluator — END ===============================
