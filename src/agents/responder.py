# [P4-04] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Dict, Iterator, List, Optional

from src.agents._common import stream_llm
from src.modes.types import Mode
from src.modes.router import ModeRouter
from src.rag.label import canonicalize_label  # RAG 라벨 고정


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


def _format_context_from_hits(hits: List[Dict[str, object]], limit: int = 3) -> str:
    if not hits:
        return ""
    lines: List[str] = []
    for h in hits[: max(1, int(limit))]:
        title = str(h.get("title") or "") or str(h.get("path") or "")
        snip = str(h.get("snippet") or "")
        # 안전 길이(ASCII ellipsis만 사용)
        if len(snip) > 220:
            snip = snip[:217] + "..."
        lines.append(f"- {title}: {snip}")
    return "## 참고 자료(요약)\n" + ("\n".join(lines))


def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, object]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - SSOT Router 기반 프롬프트(섹션/규칙/라벨 표준 포함)
    - RAG 상위 히트를 '참고 자료' 블록으로 주입
    - split_fallback=True: 콜백 미지원 provider에서 의사 스트리밍
    """
    bundle = _build_bundle(question, mode)
    sys_p = _system_prompt_from_profile(bundle.profile.tone)

    hits = []
    src_label = "[AI지식]"
    if isinstance(ctx, dict):
        try:
            hits = list(ctx.get("hits") or [])
        except Exception:
            hits = []
        try:
            src_label = str(ctx.get("source_label") or src_label)
        except Exception:
            pass

    # 참고 자료 블록 구성
    user_prompt = str(bundle.prompt or "")
    ctx_block = _format_context_from_hits(hits, limit=3)
    if ctx_block:
        canon = canonicalize_label(src_label)
        user_prompt = (
            f"{user_prompt}\n\n{ctx_block}\n\n"
            "## 답변 지침\n"
            "- 위 '참고 자료'를 **우선 근거**로 사용하세요.\n"
            "- 문장단 인용을 간단히 달되, 프로젝트 표기법을 따르세요 "
            f"(예: {canon}).\n"
            "- 만약 참고 자료로는 근거가 부족하면, '근거 부족'을 명시하고 "
            "업로드/인덱싱을 권유하세요."
        )
    else:
        user_prompt = (
            f"{user_prompt}\n\n"
            "## 참고 자료 없음\n"
            "- 규칙/정의/예시를 중심으로 답변하고, "
            "필요하면 업로드/인덱싱을 권유하세요."
        )

    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=user_prompt,
        split_fallback=True,
    )
# [P4-04] END: src/agents/responder.py (FULL REPLACEMENT)
