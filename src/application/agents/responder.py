# [P4-04] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Dict, Iterator, Optional

from src.application.agents._common import stream_llm
from src.application.modes.types import Mode
from src.application.modes.router import ModeRouter

try:
    import streamlit as _st  # 세션 오버라이드(페르소나/자연어 지시) 읽기
except Exception:
    _st = None  # pragma: no cover


def _system_prompt_from_profile(tone: str) -> str:
    """
    모드 프로필의 tone을 반영한 시스템 프롬프트.
    라벨/스키마/규칙 등은 Router가 user 프롬프트로 구성한다.
    """
    t = (tone or "").strip() or "친절하고 명확하며 단계적인 설명"
    return (
        "당신은 학생을 돕는 영어 선생님입니다. "
        f"{t}을(를) 따르세요."
    )


def _build_bundle(question: str, mode_key: str):
    try:
        mode = Mode.from_str(mode_key)
    except Exception:
        mode = Mode.GRAMMAR
    router = ModeRouter()
    return router.render_prompt(mode=mode, question=question, source_label="[AI지식]")


def _read_overrides(mode_key: str) -> Dict[str, str]:
    """세션에서 모드별 오버라이드(페르소나/자연어 지시)를 읽는다."""
    if _st is None:
        return {"persona": "", "inst": ""}
    ss = getattr(_st, "session_state", {})
    persona = str(ss.get(f"__persona_{mode_key}") or "").strip()
    inst = str(ss.get(f"__prompt_{mode_key}") or "").strip()
    return {"persona": persona, "inst": inst}


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, str]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - SSOT Router 기반 프롬프트(섹션/규칙/라벨 표준 포함)
    - 세션 오버라이드(페르소나/자연어 지시)를 '추가 지시'로 병합
    - split_fallback=True: 콜백 미지원 provider에서 의사 스트리밍
    """
    bundle = _build_bundle(question, mode)
    sys_p = _system_prompt_from_profile(bundle.profile.tone)

    # 세션 오버라이드 병합
    ov = _read_overrides(mode)
    if ov["persona"]:
        # 사용자 페르소나가 있으면 시스템 프롬프트 상단에 우선 배치
        sys_p = f"{ov['persona'].strip()}\n\n{sys_p}"
    user_p = bundle.prompt
    if ov["inst"]:
        user_p = f"{user_p}\n\n# 사용자 정의 지시\n{ov['inst'].strip()}"

    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=user_p,
        split_fallback=True,
    )
# [P4-04] END: src/agents/responder.py (FULL REPLACEMENT)
