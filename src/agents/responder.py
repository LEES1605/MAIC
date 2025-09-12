# [24B] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Iterator, Optional, Dict
from src.agents._common import stream_llm
from src.core.prompt_loader import (
    get_bracket_rules,
    get_custom_mode_prompts,
)


def _default_system_by_mode(mode_key: str) -> str:
    m = (mode_key or "").strip().lower()
    if m == "sentence":
        return (
            "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
            "짧고 명확한 단계적 설명을 사용하세요.\n"
            "출력: 괄호분석 → 해석 → 핵심 포인트 3개."
        )
    if m == "passage":
        return (
            "당신은 학생을 돕는 영어 선생님입니다. 요지→쉬운 예시→주제→제목을 "
            "간결하게 정리하세요."
        )
    # grammar
    return (
        "당신은 학생을 돕는 영어 선생님입니다. 핵심 규칙→간단 예시→흔한 오해를 "
        "짧게 설명하세요."
    )


def _maybe_append_bracket_rules(system_txt: str) -> str:
    """
    문장 모드인데 사용자 system에 괄호 규칙 안내가 없으면
    사용자 제공 괄호규칙 블록을 덧붙인다.
    """
    s = system_txt or ""
    has_hint = bool(
        ("괄호" in s)
        or ("표기 규칙" in s)
        or ("bracket" in s.lower())
    )
    if has_hint:
        return s
    rules = get_bracket_rules()
    return (
        s
        + "\n\n[괄호/기호 표기 규칙 — 엄수]\n"
        + "<<<BRACKET_RULES>>>\n"
        + rules
        + "\n<<<END_RULES>>>"
    )


def _safe_format(template: str, mapping: Dict[str, str]) -> str:
    """
    {PLACEHOLDER}를 안전하게 치환(미지 키는 빈 문자열).
    """
    import re

    def repl(m):
        key = (m.group(1) or "").strip()
        return str(mapping.get(key, ""))

    return re.sub(r"{\s*([A-Za-z0-9_]+)\s*}", repl, template)


def _compose_prompts(
    mode_key: str, question: str, ctx: Optional[Dict[str, str]]
) -> tuple[str, str]:
    """
    반환: (system_prompt, user_prompt)
    - prompts.yaml(modes.*)의 사용자 정의 system/user가 있으면 우선 사용
    - 문장 모드는 괄호규칙 블록을 필요 시 부착
    """
    custom = get_custom_mode_prompts(mode_key)
    sys_txt = custom.get("system") or _default_system_by_mode(mode_key)
    usr_txt = custom.get("user") or ""

    if mode_key == "sentence":
        sys_txt = _maybe_append_bracket_rules(sys_txt)

    # user 템플릿이 있으면 안전 치환, 없으면 질문만 전달
    if usr_txt:
        mapping: Dict[str, str] = {
            "QUESTION": question,
            "question": question,
            "EVIDENCE_CLASS_NOTES": (ctx or {}).get("EVIDENCE_CLASS_NOTES", ""),
            "EVIDENCE_GRAMMAR_BOOKS": (ctx or {}).get("EVIDENCE_GRAMMAR_BOOKS", ""),
        }
        user_prompt = _safe_format(usr_txt, mapping)
        if ("{QUESTION}" not in usr_txt) and ("{question}" not in usr_txt):
            user_prompt = user_prompt.rstrip() + "\n\n[질문]\n" + question
    else:
        user_prompt = question

    return sys_txt, user_prompt


def answer_stream(
    *, question: str, mode: str, ctx: Optional[Dict[str, str]] = None
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - 내부 모드 키(mode)는 'grammar|sentence|passage'
    - 사용자 정의 prompts.yaml(modes.*)가 있으면 system/user를 우선 사용
    - split_fallback=True: 콜백 미지원 provider에서 문장 단위 의사 스트리밍
    """
    sys_p, user_p = _compose_prompts(mode, question, ctx)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=user_p,
        split_fallback=True,
    )
# [24B] END: src/agents/responder.py
