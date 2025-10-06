# [01] START: src/agents/evaluator.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Dict, Iterator, Optional, Tuple

from src.agents._common import stream_llm
from src.modes.types import sanitize_source_label  # SSOT 라벨 가드
from src.core.modes import MODES, ModeSpec, find_mode_by_label  # 평가 루브릭 SSOT


def _get_mode_spec(mode_key_or_label: str) -> ModeSpec:
    """
    입력(영문 key 또는 한글 라벨)으로 ModeSpec을 안전히 획득.
    실패 시 'grammar' 폴백.
    """
    key = (mode_key_or_label or "").strip()
    # 1) key 우선
    spec = MODES.get(key)
    if spec is not None:
        return spec
    # 2) label 매칭
    by_label = find_mode_by_label(key)
    if by_label is not None:
        return by_label
    # 3) fallback
    return MODES["grammar"]


def _system_prompt(profile_title: str) -> str:
    """
    미나쌤(평가자) 톤: 간결·정확·근거 지향.
    """
    return (
        "당신은 '미나쌤'입니다. 학생을 존중하면서도 "
        "간결·정확·근거 중심으로 평가하세요. "
        f"(모드: {profile_title})"
    )


def build_eval_prompt(
    *,
    question: str,
    answer: str,
    mode: str,
    source_label: Optional[str] = None,
) -> Tuple[str, str]:
    """
    테스트/재사용을 위해 분리한 빌더.
    Returns: (system_prompt, user_prompt)
    """
    spec = _get_mode_spec(mode)
    label = sanitize_source_label(source_label)

    # 출력 스키마는 평가 친화적으로 고정(모드 공통)
    schema = (
        "1) 칭찬/강점\n"
        "2) 아쉬운 점·오류\n"
        "3) 구체적 교정 제안(예시 포함)\n"
        "4) 점수(10점, 정수)\n"
        "5) 한 줄 피드백\n"
        "6) 근거/출처"
    )

    lines = []
    lines.append(f"# [미나쌤 평가] — {spec.label}")
    lines.append("")
    lines.append("## 평가 기준")
    for it in spec.eval_focus:
        lines.append(f"- {it}")
    lines.append("")
    if spec.prompt_rules:
        lines.append("## 준수 규칙")
        for it in spec.prompt_rules:
            lines.append(f"- {it}")
        lines.append("")
    lines.append("## 출력 스키마(순서 고정)")
    lines.append(schema)
    lines.append("")
    lines.append(f"**출처 라벨**: {label}")
    lines.append("")
    lines.append("## 질문")
    lines.append(question.strip())
    lines.append("")
    lines.append("## 학생 답변(평가 대상)")
    lines.append(answer.strip())
    lines.append("")
    lines.append("> 위 스키마를 **순서대로** 준수하고, 불필요한 수사는 줄이세요.")

    user_prompt = "\n".join(lines).strip()
    sys_prompt = _system_prompt(spec.label)
    return sys_prompt, user_prompt


def evaluate_stream(
    *,
    question: str,
    mode: str,
    answer: str,
    ctx: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    평가(미나쌤) 스트리밍 제너레이터.
    - SSOT 루브릭(ModeSpec.eval_focus/prompt_rules) 기반 평가 프롬프트 생성
    - sanitize_source_label()로 라벨 화이트리스트 강제
    """
    label = None
    if isinstance(ctx, dict):
        label = str(ctx.get("source_label") or "")

    sys_p, usr_p = build_eval_prompt(
        question=question, answer=answer, mode=mode, source_label=label
    )

    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=usr_p,
        split_fallback=True,
    )
# [01] END: src/agents/evaluator.py (FULL REPLACEMENT)
