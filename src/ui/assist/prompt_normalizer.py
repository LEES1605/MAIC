# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — START =====
from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Optional, Tuple

import yaml

ELLIPSIS_UC = "\u2026"


# ===== [02] helpers — START =====
def _sanitize_ellipsis(text: str) -> str:
    """U+2026 → '...' 치환(ruff/CI 안전)."""
    return (text or "").replace(ELLIPSIS_UC, "...")


def _thin(text: str) -> str:
    """양끝 공백 정리 + 연속 공백 간소화."""
    t = (text or "").replace("\r\n", "\n").strip()
    # 너무 공격적으로 줄이지 않고, 기본적인 불필요 공백만 정리
    return "\n".join(line.rstrip() for line in t.splitlines()).strip()


def _post_openai(api_key: str, model: str, messages: list[dict], temperature: float) -> str:
    """OpenAI Chat Completions (schema 재작성 시도). 실패하면 호출측에서 폴백."""
    req: Any = importlib.import_module("requests")
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = req.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    r.raise_for_status()
    data = r.json()
    content = (data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    return str(content or "")


def _autosplit_persona_and_rules(block: str) -> Tuple[str, str]:
    """
    자연어 한 덩어리를 (persona, system_instructions)로 대략 분해.
    - 첫 빈줄(또는 'AI 페르소나' 표제) 전까지 → persona
    - 이후 불릿/명령형 문장/번호 목록 → system_instructions
    실패하면 전부 persona로 두고, 기본 system 지시를 짧게 제공.
    """
    t = _thin(block)
    if not t:
        return "", ""

    # 1) 표제어 기준 가벼운 분리
    lowers = t.lower()
    cut_keys = ("ai 작업 지침", "작업 지침", "분석 지침", "지침:", "instructions", "prompt")
    cut = -1
    for k in cut_keys:
        pos = lowers.find(k)
        if pos >= 0:
            cut = max(cut, pos)
    if cut >= 0:
        persona = t[:cut].strip()
        rules = t[cut:].strip()
        if persona and rules:
            return persona, rules

    # 2) 빈 줄 기준
    parts = [p for p in t.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        first = parts[0].strip()
        rest = "\n\n".join(parts[1:]).strip()
        return first, rest

    # 3) 폴백: 전부 persona로
    return t, ""


def _build_prompt(grammar: str, sentence: str, passage: str) -> list[dict]:
    """
    OpenAI에 '자연어 한 덩어리 × 3'을 넘겨 정형 스키마 YAML을 얻기 위한 시스템 프롬프트.
    (환경에 따라 이 경로는 건너뛰고 폴백 YAML을 사용해도 충분히 동작)
    """
    sys = (
        "You are a prompt normalizer. "
        "Given one free-form Korean text for each mode, "
        "produce a YAML that strictly follows this schema:\n"
        "version: auto\n"
        "modes:\n"
        "  grammar: {persona, system_instructions, guardrails, examples, "
        "citations_policy, routing_hints}\n"
        "  sentence: {persona, system_instructions, guardrails, examples, "
        "citations_policy, routing_hints}\n"
        "  passage: {persona, system_instructions, guardrails, examples, "
        "citations_policy, routing_hints}\n"
        "Rules:\n"
        "- For each mode, split the single input into two: "
        "concise persona (1-3 lines) and actionable "
        "system_instructions (≤5 bullet lines). "
        "Do not copy input verbatim; summarize clearly.\n"
        "- Korean output only. No extra commentary; return YAML only.\n"
        "- citations_policy must be exactly: "
        "\"[이유문법]/[문법서적]/[AI지식]\".\n"
        "- routing_hints.model: grammar=gpt-5-pro, sentence=gemini-pro, "
        "passage=gpt-5-pro.\n"
        "- guardrails: include pii:true. examples: keep short or empty.\n"
    )
    user = (
        "입력(문법 한 덩어리):\n" + grammar.strip() + "\n\n"
        "입력(문장 한 덩어리):\n" + sentence.strip() + "\n\n"
        "입력(지문 한 덩어리):\n" + passage.strip() + "\n\n"
        "위 3개 입력을 분석해 스키마에 맞는 YAML을 생성해 주세요."
    )
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]
# ===== [02] helpers — END =====


# ===== [03] public API — START =====
def normalize_from_single_block(
    *,
    text: str,
    openai_key: Optional[str],
    openai_model: str = "gpt-4o-mini",
) -> str:
    """
    (관대한 경로) 자연어 '한 덩어리'만 받아 3개 모드 모두를 채운 YAML을 생성.
    - OpenAI 호출은 선택(키 없으면 폴백)
    - 페르소나/시스템지시는 간단 휴리스틱으로 자동 분리
    """
    t = _sanitize_ellipsis(text or "")
    return normalize_to_yaml(
        grammar_text=t, sentence_text=t, passage_text=t,
        openai_key=openai_key, openai_model=openai_model,
    )


def normalize_to_yaml(
    *,
    grammar_text: str,
    sentence_text: str,
    passage_text: str,
    openai_key: Optional[str],
    openai_model: str = "gpt-4o-mini",
) -> str:
    """
    세 모드 입력(각각 자연어 한 덩어리)을 받아 스키마 적합 YAML 생성.
    OpenAI 실패 시 '관대한 폴백'으로 최소 스키마를 보장.
    """
    # 0) 전처리: …/공백/빈값 처리 & 단일 입력 복제 허용
    grammar_text = _thin(_sanitize_ellipsis(grammar_text))
    sentence_text = _thin(_sanitize_ellipsis(sentence_text)) or grammar_text
    passage_text = _thin(_sanitize_ellipsis(passage_text)) or grammar_text

    yaml_text = ""
    if openai_key:
        try:
            msgs = _build_prompt(grammar_text, sentence_text, passage_text)
            out = _post_openai(openai_key, openai_model, msgs, temperature=0.2)
            yaml_text = (out or "").strip()
        except Exception:
            yaml_text = ""

    if not yaml_text:
        # ===== 폴백: 관대한 자동 분해로 최소 스키마 보장 =====
        g_p, g_s = _autosplit_persona_and_rules(grammar_text)
        s_p, s_s = _autosplit_persona_and_rules(sentence_text)
        p_p, p_s = _autosplit_persona_and_rules(passage_text)

        def _sys_default(s: str, default: str) -> str:
            return s if s else default

        data: Dict[str, Any] = {
            "version": "auto",
            "modes": {
                "grammar": {
                    "persona": g_p or grammar_text,
                    "system_instructions": _sys_default(
                        g_s, "규칙→근거→예문→요약"
                    ),
                    "guardrails": {"pii": True},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gpt-5-pro", "max_tokens": 800, "temperature": 0.2},
                },
                "sentence": {
                    "persona": s_p or sentence_text,
                    "system_instructions": _sys_default(
                        s_s, "토큰화→구문(괄호규칙)→어감/의미분석"
                    ),
                    "guardrails": {"pii": True},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gemini-pro", "max_tokens": 700, "temperature": 0.3},
                },
                "passage": {
                    "persona": p_p or passage_text,
                    "system_instructions": _sys_default(
                        p_s, "요지→예시/비유→주제→제목"
                    ),
                    "guardrails": {"pii": True},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gpt-5-pro", "max_tokens": 900, "temperature": 0.4},
                },
            },
        }
        yaml_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    # 3) 최종 파싱 검증(실패하면 다시 최소 폴백 생성)
    try:
        obj = yaml.safe_load(yaml_text)
        if not isinstance(obj, dict):
            raise ValueError("root must be mapping")
    except Exception:
        obj = {
            "version": "auto",
            "modes": {
                "grammar": {
                    "persona": grammar_text,
                    "system_instructions": "",
                    "guardrails": {},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gpt-5-pro"},
                },
                "sentence": {
                    "persona": sentence_text,
                    "system_instructions": "",
                    "guardrails": {},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gemini-pro"},
                },
                "passage": {
                    "persona": passage_text,
                    "system_instructions": "",
                    "guardrails": {},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gpt-5-pro"},
                },
            },
        }
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)
# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — END =====
