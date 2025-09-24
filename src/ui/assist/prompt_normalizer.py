# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — START =====
from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Optional

import yaml

ELLIPSIS_UC = "\u2026"


# ===== [02] helpers — START =====
def _sanitize_ellipsis(text: str) -> str:
    return text.replace(ELLIPSIS_UC, "...")


def _post_openai(api_key: str, model: str, messages: list[dict], temperature: float) -> str:
    req: Any = importlib.import_module("requests")
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = req.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    r.raise_for_status()
    data = r.json()
    content = (data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    return str(content or "")


def _build_prompt(grammar: str, sentence: str, passage: str) -> list[dict]:
    # 각 모드 입력은 "자연어 한 덩어리". 모델이 이를
    # persona(역할/톤) + system_instructions(절차/지시)로 자동 분해한다.
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
    OpenAI 실패 시 템플릿 폴백.
    """
    grammar_text = _sanitize_ellipsis(grammar_text)
    sentence_text = _sanitize_ellipsis(sentence_text)
    passage_text = _sanitize_ellipsis(passage_text)

    yaml_text = ""
    if openai_key:
        try:
            msgs = _build_prompt(grammar_text, sentence_text, passage_text)
            out = _post_openai(openai_key, openai_model, msgs, temperature=0.2)
            yaml_text = out.strip()
        except Exception:
            yaml_text = ""

    if not yaml_text:
        # Fallback: 최소 스키마
        data: Dict[str, Any] = {
            "version": "auto",
            "modes": {
                "grammar": {
                    "persona": grammar_text,
                    "system_instructions": "규칙→근거→예문→요약",
                    "guardrails": {"pii": True},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gpt-5-pro", "max_tokens": 800, "temperature": 0.2},
                },
                "sentence": {
                    "persona": sentence_text,
                    "system_instructions": "토큰화→구문(괄호규칙)→어감/의미분석",
                    "guardrails": {"pii": True},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gemini-pro", "max_tokens": 700, "temperature": 0.3},
                },
                "passage": {
                    "persona": passage_text,
                    "system_instructions": "요지→예시/비유→주제→제목",
                    "guardrails": {"pii": True},
                    "examples": [],
                    "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
                    "routing_hints": {"model": "gpt-5-pro", "max_tokens": 900, "temperature": 0.4},
                },
            },
        }
        yaml_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    # 최종 검증(파싱 실패 시 폴백)
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
