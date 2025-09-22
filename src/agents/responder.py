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
    t = (tone or "").strip() or "친절하고 명확하며 단계적인 설명"
    return "당신은 학생을 돕는 영어 선생님입니다. " + f"{t}을(를) 따르세요."


def _build_bundle(question: str, mode_key: str):
    try:
        mode = Mode.from_str(mode_key)
    except Exception:
        mode = Mode.GRAMMAR
    router = ModeRouter()
    return router.render_prompt(mode=mode, question=question, source_label="[AI지식]")


def _format_ctx_docs(docs: list[dict], max_docs: int = 5, max_snip: int = 360) -> str:
    """
    Top-K 문맥을 모델 친화 포맷으로 정리.
    - 인덱스 기반 참조 표기: [1], [2], ...
    - 스니펫은 길이 제한을 두어 토큰 낭비를 방지.
    """
    out: list[str] = []
    n = min(len(docs), max_docs)
    for i in range(n):
        d = docs[i] or {}
        title = str(d.get("title") or "").strip() or "(제목 없음)"
        path = str(d.get("path") or "").strip()
        snip = str(d.get("snippet") or "").strip()[: max_snip]
        out.append(f"[{i+1}] {title}\n- src: {path}\n- snippet: {snip}")
    return "\n\n".join(out)


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, object]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - SSOT Router 기반 프롬프트(섹션/규칙/라벨 표준 포함)
    - ctx.docs: RAG 문맥(Top-K) — title/snippet/path/score 의 경량 리스트
    - ctx.strict=True: 문맥이 비어 있으면 안전 종료(업로드/인덱싱 권고)
    - split_fallback=True: 콜백 미지원 provider에서도 의사 스트리밍
    """
    bundle = _build_bundle(question, mode)
    sys_p = _system_prompt_from_profile(bundle.profile.tone)

    docs = []
    strict = False
    if isinstance(ctx, dict):
        try:
            docs = list(ctx.get("docs") or [])
        except Exception:
            docs = []
        strict = bool(ctx.get("strict"))

    # Strict + 근거 없음: 안전한 종료 메시지(비스트리밍)
    if strict and not docs:
        yield (
            "제가 참고할 자료를 찾지 못했어요. 상단의 인덱싱 패널에서 자료를 준비하거나 "
            "지식 폴더(prepared/knowledge)에 파일을 추가한 뒤 다시 시도해 주세요."
        )
        return

    # 사용자 프롬프트에 '문맥만 사용' 규칙을 명시 주입
    ctx_block = _format_ctx_docs(docs) if docs else ""
    rules = [
        "아래 '문맥(Context)'만을 근거로 답하세요.",
        "문맥에 없는 사실은 추측하지 말고, 필요한 자료 업로드/인덱싱을 안내하세요.",
        "근거가 된 문맥 항목의 번호를 대괄호로 표시하세요. 예: [1], [2]",
        "한국어로 간결하게 설명하세요.",
    ]
    user_prompt = bundle.prompt
    if ctx_block:
        user_prompt += (
            "\n\n# Context (Top-K)\n" + ctx_block + "\n\n# Rules\n- " + "\n- ".join(rules)
        )

    # 스트리밍 호출
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=user_prompt,
        split_fallback=True,
    )
# [P4-04] END: src/agents/responder.py
