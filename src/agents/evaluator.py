# src/agents/evaluator.py
# ============================== Evaluator Stream ===============================
from __future__ import annotations

from typing import Iterator, Optional, Dict, List
from src.agents._common import stream_llm


def _load_mode_spec(mode_key: str) -> Dict[str, List[str] | str]:
    """
    SSOT(src.core.modes)을 우선하여 모드 정의를 불러오고, 실패 시 안전 폴백.
    Returns:
        {"key": ..., "label": ..., "sections": [...], "eval_focus": [...]}
    """
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

    # --- Fallbacks (문법/문장/지문) ---
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
        "sections": ["핵심규칙", "근거", "예문", "역예문(선택)", "한 줄 요약"],
        "eval_focus": ["정확도", "근거 제시", "간결성"],
    }


def _system_prompt(mode_key: str) -> str:
    """
    미나쌤(품질 평가자) 시스템 프롬프트.
    - 형식/규칙 준수 여부를 간결하게 진단하고, 개선 포인트를 3개 이내로 제시.
    - 문장 모드일 때 괄호규칙 라벨 세트 강제.
    """
    spec = _load_mode_spec(mode_key)
    sections = "·".join(spec["sections"]) if spec["sections"] else "형식 미정"
    focus = "·".join(spec["eval_focus"]) if spec["eval_focus"] else "정확도"

    # 괄호규칙 라벨: S/V/O/C/M/Sub/Rel/ToInf/Ger/Part/Appo/Conj
    bracket_rules = (
        "문장 모드에서는 다음 라벨만 사용했는지 확인: "
        "S,V,O,C,M,Sub,Rel,ToInf,Ger,Part,Appo,Conj. "
        "예: [Sub because it rained], [S I] [V stayed] [M at home]"
    )

    return (
        "당신은 '미나쌤' 품질 평가자입니다. 역할: 학생에게 친절하지만 정확한 피드백 제공. "
        "원칙: 과장 금지, 간결, 근거 제시, 번호 목록은 3개 이내.\n"
        f"- 모드: {spec['label']} / 필수 섹션: {sections}\n"
        f"- 평가 관점: {focus}\n"
        f"- 형식 위반·사실 오류·모호함을 우선 지적\n"
        f"- {bracket_rules}"
    )


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: str,
    ctx: Optional[Dict[str, str]] = None,
) -> Iterator[str]:
    """
    미나쌤 평가 스트리밍 제너레이터.
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

    user_prompt = (
        "[입력]\n"
        f"- 질문: {question}\n"
        f"- 모드: {spec['label']} ({spec['key']})\n"
        "- 답변(피티쌤): <<START_ANSWER>>\n"
        f"{answer}\n"
        "<<END_ANSWER>>\n\n"
        "[검토 기준]\n"
        f"1) 섹션 구성(순서={sections}) 및 누락 여부\n"
        "2) 괄호규칙 준수(문장 모드일 때만): 라벨 세트는 고정 "
        "(S,V,O,C,M,Sub,Rel,ToInf,Ger,Part,Appo,Conj)\n"
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
