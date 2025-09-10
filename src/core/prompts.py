# -----------------------------------------------------------------------------
# src/core/prompts.py
# SSOT for system prompts (responder/evaluator) + mode canonicalization
# -----------------------------------------------------------------------------
from __future__ import annotations
from typing import Dict, Optional

# 표준 모드 키
# - UI(라디오)나 외부 호출에서 들어오는 다양한 문자열을 key로 정규화
_CANON: Dict[str, str] = {
    "문법": "grammar", "문법설명": "grammar", "grammar": "grammar",
    "문장": "sentence", "문장분석": "sentence", "문장구조분석": "sentence", "sentence": "sentence",
    "지문": "passage", "지문분석": "passage", "passage": "passage",
    # 확장 여지: "이야기": "story" 등
}

def canonical_mode(mode: str | None) -> str:
    s = (mode or "").strip().lower()
    return _CANON.get(s, _CANON.get(mode or "", "grammar"))

# ------------------------------ Responder ------------------------------------
def system_prompt_for_responder(mode: str | None, ctx: Optional[dict] = None) -> str:
    """
    주답변(피티쌤) 시스템 프롬프트.
    - 이유문법/문법서적 라벨이 있는 경우 톤과 구조를 살짝 조정.
    """
    key = canonical_mode(mode)
    label = ""
    if isinstance(ctx, dict):
        label = str(ctx.get("source_label") or "").strip()

    base = (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요."
    )

    if key == "grammar":
        tail = (
            " 핵심 규칙 → 간단 예시 → 흔한 오해 순으로 설명하세요."
        )
        if label == "[이유문법]":
            tail = (
                " 규칙의 '이유(왜 그런가)'를 먼저 짚고, "
                "핵심 규칙 → 반례/주의 → 미니 퀴즈(한 줄) 순으로 설명하세요."
            )
        elif label == "[문법서적]":
            tail = (
                " 사전적/정석적 설명을 우선하되, 학생이 이해할 수 있게 간결한 예시를 곁들이세요."
            )
    elif key == "sentence":
        tail = (
            " 문장 구조는 품사/구문 역할 중심으로 표처럼 정리하고, "
            "핵심 포인트 3개를 요약하세요."
        )
    elif key == "passage":
        tail = (
            " 지문은 주제/요지/세부정보를 구분하고, 각 주장에 대한 근거 문장을 명확히 제시하세요."
        )
    else:
        tail = " 핵심 → 예시 → 한 줄 정리로 설명하세요."

    return base + tail

# ------------------------------ Evaluator ------------------------------------
def system_prompt_for_evaluator(mode: str | None, ctx: Optional[dict] = None) -> str:
    """
    보완(미나쌤) 시스템 프롬프트.
    - 비평/채점/중복 나열 금지. 빠진 부분을 촘촘히 보완.
    """
    key = canonical_mode(mode)
    base = (
        "당신은 '미나쌤' 보조 선생님입니다. "
        "첫 번째 선생님(피티쌤)의 답변을 바탕으로, "
        "중복을 최소화하며 빠진 부분을 보충하고 쉬운 비유/예시 또는 심화 포인트를 추가하세요. "
        "비평/채점/메타 피드백은 금지."
    )
    if key == "grammar":
        tail = " 핵심 규칙 정리 → 예외/흔한오해 → 한 줄 정리 순서를 따르세요."
    elif key == "sentence":
        tail = " 품사/구문 역할을 간단 표로 정리하고, 핵심 포인트 3개를 보완하세요."
    elif key == "passage":
        tail = " 주제/요지/세부정보를 구분해 보완하고, 근거 문장을 명확히 인용하세요."
    else:
        tail = " 핵심 → 예시 → 한 줄 정리로 보완하세요."
    return base + tail

# ------------------------------ User prompts ---------------------------------
def user_prompt_for_evaluator(question: str, answer: str | None) -> str:
    q = (question or "").strip()
    a = (answer or "").strip()
    head = f"학생 질문:\n{q}"
    if a:
        head += (
            "\n\n첫 번째 선생님(피티쌤)의 답변을 바탕으로 보완해 주세요."
            f"\n\n[피티쌤의 답변]\n{a}\n"
        )
    head += (
        "\n[요청]\n- 비평 금지, 중복 최소화\n"
        "- 더 쉬운 설명 또는 심화 포인트 보완\n- 핵심 → 예시 → 한 줄 정리"
    )
    return head
