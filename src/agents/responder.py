# [01] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, Optional, Sequence, Union

from src.agents._common import stream_llm
from src.modes.router import ModeRouter
from src.modes.types import Mode, sanitize_source_label


def _system_prompt(profile_title: str) -> str:
    """
    '피티쌤' 톤의 시스템 프롬프트.
    - 불필요한 수사를 줄이고, 단계적·간결 설명을 유도
    - 모드 제목(프로필 타이틀)을 주입해 역할 고정을 강화
    """
    return (
        "당신은 학생을 돕는 영어 선생님 '피티쌤'입니다. "
        "친절하고 단계적으로 설명하고, 불필요한 말은 줄이세요. "
        "간결한 문장과 목록을 활용해 핵심→예시→요약 순으로 답변합니다. "
        f"(모드: {profile_title})"
    )


def _pick_fragments(ctx: Optional[Dict[str, object]]) -> Sequence[str]:
    """
    ctx에서 컨텍스트 조각을 추출(있다면).
    - 허용 키: 'fragments'|'context'|'hits'
    - 문자열/비문자 혼입 시 문자열로 강제 변환
    - 나머지 길이 제한/개수 제한은 Router.render_prompt()에서 클램프
    """
    if not isinstance(ctx, dict):
        return ()
    cand: Optional[Union[Sequence[object], object]] = (
        ctx.get("fragments") or ctx.get("context") or ctx.get("hits")
    )
    if isinstance(cand, (list, tuple)):
        return tuple(str(x) for x in cand)
    return ()


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - SSOT 라우터로 모드별 프롬프트 번들을 만들고 stream_llm으로 스트리밍
    - split_fallback=True: 콜백 미지원 provider에서 문장 단위 의사 스트리밍
    """
    # 1) 모드 정규화
    try:
        m = Mode.from_str(mode)
    except Exception:
        m = Mode.GRAMMAR

    # 2) 컨텍스트 & 라벨
    frags = _pick_fragments(ctx)
    raw_label = ""
    if isinstance(ctx, dict):
        raw_label = str(ctx.get("source_label") or "")
    label = sanitize_source_label(raw_label)

    # 3) Router로 프롬프트 번들 구성
    router = ModeRouter(ssot_root=Path("docs/_gpt"))
    bundle = router.render_prompt(
        mode=m,
        question=question,
        context_fragments=frags,
        source_label=label,
    )

    # 4) LLM 스트리밍
    sys_p = _system_prompt(bundle.profile.title)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=bundle.prompt,
        split_fallback=True,
    )
# [01] END: src/agents/responder.py (FULL REPLACEMENT)
