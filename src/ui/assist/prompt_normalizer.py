# ======================= [FILE: src/ui/assist/prompt_normalizer.py] — START =======================
from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Optional

import yaml

# ===== [01] imports — START =====
ELLIPSIS_UC = "\u2026"
# ===== [01] imports — END =====

# ===== [02] helpers — START =====
def _sanitize_ellipsis(text: str) -> str:
    return text.replace(ELLIPSIS_UC, "...")


def _post_openai(api_key: str, model: str, messages: list[dict], temperature: float) -> str:
    req: Any = importlib.import_module("requests")
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = req.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    r.raise_for_status()
    data = r.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return str(content or "")


def _build_prompt(grammar: str, sentence: str, passage: str) -> list[dict]:
    sys = (
        "You are a prompt normalizer. Convert the user's free text into a YAML that "
        "conforms to this schema:\n"
        "version: auto\n"
        "modes:\n"
        "  grammar: {persona, system_instructions, guardrails, examples, "
        "citations_policy, routing_hints}\n"
        "  sentence: {...}\n"
        "  passage: {...}\n"
        "Rules:\n"
        "- Korean output. Keep lines concise. No fancy markup.\n"
        "- citations_policy must be exactly: \"[이유문법]/[문법서적]/[AI지식]\".\n"
        "- routing_hints.model: grammar=gpt-5-pro, sentence=gemini-pro, passage=gpt-5-pro.\n"
        "- guardrails: include pii:true.\n"
        "- examples: short or empty list.\n"
        "- Return only YAML. No explanations."
    )
    user = (
        "원문(문법):\n" + grammar.strip() + "\n\n"
        "원문(문장):\n" + sentence.strip() + "\n\n"
        "원문(지문):\n" + passage.strip() + "\n\n"
        "위 내용을 기반으로 스키마에 맞는 YAML을 작성해 주세요."
    )
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]
# ===== [02] helpers — END =====

# ===== [03] normalize_to_yaml — START =====
def normalize_to_yaml(
    *,
    grammar_text: str,
    sentence_text: str,
    passage_text: str,
    openai_key: Optional[str],
    openai_model: str = "gpt-4o-mini",
) -> str:
    """
    Free text(문법/문장/지문)를 스키마 기반 YAML로 정리.
    - OpenAI 키가 있으면 Chat Completions로 생성.
    - 실패 시 템플릿 기반 최소 YAML로 폴백.
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
        # Fallback: 최소 스키마로 구성
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

    # 최종 YAML 검증 및 정리
    try:
        obj = yaml.safe_load(yaml_text)
        if not isinstance(obj, dict):
            raise ValueError("root must be mapping")
    except Exception:
        # 폴백 YAML
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
# ===== [03] normalize_to_yaml — END =====
# ======================= [FILE: src/ui/assist/prompt_normalizer.py] — END =======================
