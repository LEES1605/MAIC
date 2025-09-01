# ============================ prompt_modes.py — START ============================
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class PromptSpec:
    key: str
    title: str
    system: str
    user_prefix: str


# 모드 정의(필요시 확장: 'grammar' | 'sentence' | 'passage' ...)
_PROMPTS: Dict[str, PromptSpec] = {
    "grammar": PromptSpec(
        key="grammar",
        title="어법 모드",
        system=(
            "당신은 영어 문법 교사입니다. 학생이 올린 문장을 분석하여 "
            "문법적 오류를 짚고 근거를 간명하게 제시하세요. "
            "가능하면 중학생도 이해할 표현을 사용합니다."
        ),
        user_prefix="문장:",
    ),
    "sentence": PromptSpec(
        key="sentence",
        title="문장 모드",
        system=(
            "당신은 영작 코치입니다. 학생의 목적과 톤에 맞는 자연스러운 문장을 "
            "여러 안으로 제시하고, 선택 이유를 짧게 덧붙이세요."
        ),
        user_prefix="의도/문맥:",
    ),
    "passage": PromptSpec(
        key="passage",
        title="지문 모드",
        system=(
            "당신은 독해 코치입니다. 학생이 제공한 지문을 요약하고, "
            "핵심 어휘/문법 포인트를 뽑은 뒤, 핵심질문 3개를 제시하세요."
        ),
        user_prefix="지문:",
    ),
}


def get_prompt_spec(mode: str, default: str = "sentence") -> PromptSpec:
    """
    모드 키로 PromptSpec 반환. 모르는 값이면 default로 폴백.
    """
    key = (mode or "").strip().lower()
    return _PROMPTS.get(key) or _PROMPTS[default]


def list_modes() -> Dict[str, str]:
    """UI 라디오/셀렉트에 쓰기 좋은 (key -> title) 매핑."""
    return {k: v.title for k, v in _PROMPTS.items()}


def build_user_prompt(mode: str, user_text: str) -> str:
    """
    모드별 user 프리픽스를 붙여 단순 프롬프트를 구성.
    (상위 레이어에서 system 프롬프트는 별도로 사용)
    """
    spec = get_prompt_spec(mode)
    t = (user_text or "").strip()
    return f"{spec.user_prefix} {t}" if t else spec.user_prefix


# ============================= prompt_modes.py — END =============================
