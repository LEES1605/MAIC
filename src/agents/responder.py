# [P4-04] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Dict, Iterator, Optional

from src.agents._common import stream_llm
from src.modes.types import Mode
from src.modes.router import ModeRouter


def _system_prompt_from_profile(tone: str) -> str:
    """
    모드 프로필의 tone을 반영한 시스템 프롬프트.
    라벨/스키마/규칙 등은 Router가 user 프롬프트로 구성한다.
    """
    t = tone.strip() or "친절하고 명확하며 단계적인 설명"
    return (
        "당신은 학생을 돕는 영어 선생님입니다. "  # 짧고 단정한 톤 유지(E501 회피)
        f"{t}을(를) 따르세요."
    )


def _build_bundle(question: str, mode_key: str):
    try:
        mode = Mode.from_str(mode_key)
    except Exception:
        mode = Mode.GRAMMAR
    router = ModeRouter()
    return router.render_prompt(mode=mode, question=question, source_label="[AI지식]")


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, str]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - SSOT Router 기반 프롬프트(섹션/규칙/라벨 표준 포함)
    - split_fallback=True: 콜백 미지원 provider에서 의사 스트리밍
    """
    bundle = _build_bundle(question, mode)
    sys_p = _system_prompt_from_profile(bundle.profile.tone)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=bundle.prompt,
        split_fallback=True,
    )
# [P4-04] END: src/agents/responder.py
