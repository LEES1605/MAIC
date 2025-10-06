# [01] START: src/prompt_modes.py (FULL REPLACEMENT)
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

from src.modes.router import ModeRouter
from src.modes.types import Mode


@dataclass(frozen=True)
class PromptSpec:
    key: str
    title: str
    system: str
    user_prefix: str


# 모드 메타(타이틀/시스템 최소 가이드) — 본문 프롬프트는 ModeRouter가 생성
_MODES_META: Dict[Mode, PromptSpec] = {
    Mode.GRAMMAR: PromptSpec(
        key=Mode.GRAMMAR.value,
        title="어법(문법설명) 모드",
        system="규칙→예시→반례→요약 순으로 간결명확하게. 용어는 풀어서 설명.",
        user_prefix="질의:",
    ),
    Mode.SENTENCE: PromptSpec(
        key=Mode.SENTENCE.value,
        title="문장분석 모드",
        system=(
            "문장 구조를 괄호 규칙으로 분석하고 근거를 제시하세요. "
            "섹션 순서를 반드시 고정 유지."
        ),
        user_prefix="질의:",
    ),
    Mode.PASSAGE: PromptSpec(
        key=Mode.PASSAGE.value,
        title="지문설명 모드",
        system="문단별 요지→핵심문장→어휘·표현→한줄요약 순서를 고정.",
        user_prefix="질의:",
    ),
}


_router = ModeRouter()


def get_prompt_spec(mode: str, default: str = "sentence") -> PromptSpec:
    """
    기존 시그니처 유지. title/system은 최소 가이드만 제공하고,
    실제 user 프롬프트 본문은 build_user_prompt()에서 ModeRouter로 생성합니다.
    """
    try:
        m = Mode.from_str(mode)
    except Exception:
        m = Mode.from_str(default)
    return _MODES_META[m]


def list_modes() -> Dict[str, str]:
    """UI 라디오/셀렉트에 쓰기 좋은 (key -> title) 매핑."""
    return {m.value: meta.title for m, meta in _MODES_META.items()}


def build_user_prompt(
    mode: str,
    user_text: str,
    *,
    context_fragments: Optional[Sequence[str]] = None,
    source_label: Optional[str] = None,
) -> str:
    """
    (변경) 기존에는 단순 prefix만 붙였지만,
    이제 ModeRouter가 만든 '전체 프롬프트(섹션/규칙 포함)'를 반환합니다.
    호출부는 기존대로 system=spec.system, user=build_user_prompt(...)로 사용해도 됩니다.
    """
    m = Mode.from_str(mode)
    bundle = _router.render_prompt(
        mode=m,
        question=(user_text or "").strip(),
        context_fragments=context_fragments,
        source_label=source_label,
    )
    return bundle.prompt
# [01] END: src/prompt_modes.py
