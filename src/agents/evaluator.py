# [20C] START: src/agents/evaluator.py (REPLACE OR ADD)
from __future__ import annotations

from typing import Iterator, Optional, Dict, List
from src.agents._common import stream_llm
from src.core.prompt_loader import get_bracket_rules


def _load_mode_spec(mode_key: str) -> Dict[str, List[str] | str]:
    key = (mode_key or "").strip().lower()
    try:
        from src.core.modes import MODES
        if key in MODES and getattr(MODES[key], "enabled", True):
            m = MODES[key]
            return {
                "key": m.key,
                "label": m.label,
                "sections": list(getattr(m, "output_shape", []) or []),
                "eval_focus": list(getattr(m, "eval_focus", []) or []),
            }
    except Exception:
        pass
    if key == "sentence":
        return {
            "key": "sentence",
            "label": "문장",
            "sections": ["토큰화", "구문(괄호규칙)", "의미해석", "개선 제안"],
            "eval_focus": ["규칙 준수", "분석 일관성", "재현성"],
        }
    if key == "passage":
        return {
            "key": "passage",
            "label": "지문",
            "sections": ["핵심 요지", "쉬운 예시/비유", "주제", "제목"],
            "eval_focus": ["평이화", "정보 보존", "집중도"],
        }
    return {
        "key": "grammar",
        "label": "문법",
        "sections": ["핵심규칙", "근거", "예문", "역예문(선택)", "한 줄 총평"],
        "eval_focus": ["정확도", "근거 제시", "간결성"],
    }


def _system_prompt(mode_key: str) -> str:
    spec = _load_mode_spec(mode_key)
    sections = "·".join(spec["sections"]) if spec["sections"] else "형식 미정"
    focus = "·".join(spec["eval_focus"]) if spec["eval_focus"] else "정확도"

    br = ""
    if spec["key"] == "sentence":
        br_rules = get_bracket_rules()
        br = (
            "\n[사용자 괄호규칙 — 반드시 이 규칙으로만 판단]\n"
            "<<<BRACKET_RULES>>>\n"
            f"{br_rules}\n"
            "<<<END_RULES>>>\n"
        )

    return (
        "당신은 '미나쌤' 품질 평가자입니다. 역할: 학생에게 친절하지만 정확한 피드백 제공. "
        "원칙: 과장 금지, 간결, 근거 제시, 번호 목록은 3개 이내.\n"
        f"- 모드: {spec['label']} / 필수 섹션: {sections}\n"
        f"- 평가 관점: {focus}\n"
        f"- 형식 위반·사실 오류·모호함을 우선 지적" + br
    )


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: str,
    ctx: Optional[Dict[str, str]] = None,
) -> Iterator[str]:
    """
    출력 형식(고정):
    [형식 체크]
    - 섹션: OK|FAIL (사유)
    - 괄호규칙: OK|FAIL (사유; 문장 모드만 표기)
    - 사실성: OK|WARN (사유)
    [피드백]
    - 개선점 1
    - 개선점 2
    - (선택) 개선점 3
    [한 줄 총평]
    - 핵심 요약 한 문장
    """
    spec = _load_mode_spec(mode)
    sections = " · ".join(spec["sections"]) if spec["sections"] else "형식 미정"

    # 사용자 규칙을 user_prompt에도 한번 더 박아 넣어 판단 기준을 명확화
    add_rules = ""
    if spec["key"] == "sentence":
        add_rules = (
            "\n[괄호규칙(사용자 제공)]\n"
            "<<<BRACKET_RULES>>>\n"
            f"{get_bracket_rules()}\n"
            "<<<END_RULES>>>\n"
        )

    user_prompt = (
        "[입력]\n"
        f"- 질문: {question}\n"
        f"- 모드: {spec['label']} ({spec['key']})\n"
        "- 답변(피티쌤): <<START_ANSWER>>\n"
        f"{answer}\n"
        "<<END_ANSWER>>\n"
        f"{add_rules}\n"
        "[검토 기준]\n"
        f"1) 섹션 구성(순서={sections}) 및 누락 여부\n"
        "2) 괄호규칙 준수(문장 모드일 때만)\n"
        "3) 사실성/근거 제시의 명확성\n"
        "4) 개선 포인트: 2~3개, 간결한 명사구로\n\n"
        "[출력 형식]\n"
        "[형식 체크]\n"
        "- 섹션: OK|FAIL (사유)\n"
        "- 괄호규칙: OK|FAIL (사유; 문장 모드만 표기)\n"
        "- 사실성: OK|WARN (사유)\n"
        "[피드백]\n"
        "- …\n"
        "- …\n"
        "- (선택) …\n"
        "[한 줄 총평]\n"
        "- …"
    )

    yield from stream_llm(
        system_prompt=_system_prompt(mode),
        user_prompt=user_prompt,
        split_fallback=True,
    )
# [20C] END: src/agents/evaluator.py
