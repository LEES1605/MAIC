# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — START =====
from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Optional

import yaml

ELLIPSIS_UC = "\u2026"

# ===== [02] low-level helpers — START =====
def _sanitize_ellipsis(text: str) -> str:
    # U+2026 → "..." 로 치환(검증/툴링 일관성)
    return (text or "").replace(ELLIPSIS_UC, "...")

def _strip_code_fences(s: str) -> str:
    """```yaml ... ``` 같은 코드펜스를 관대하게 제거."""
    if not s:
        return ""
    t = s.strip()
    if t.startswith("```"):
        # 첫 줄 셀렉터(예: ```yaml) 제거
        t = t.split("\n", 1)[-1]
    if t.endswith("```"):
        t = t.rsplit("```", 1)[0]
    return t.strip()

def _coerce_str(x: Any) -> str:
    """list→문장, dict→JSON compact, 그 외→str."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, list):
        return "\n".join([_coerce_str(i) for i in x if i is not None]).strip()
    if isinstance(x, dict):
        try:
            return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(x)
    return str(x)

def _get_syn(d: Dict[str, Any], *names: str, default=None):
    """여러 동의어 중 존재하는 첫 키 반환."""
    for n in names:
        if n in d:
            return d[n]
    return default

def _ensure_map(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}

def _ensure_modes(obj: Dict[str, Any]) -> Dict[str, Any]:
    """루트에 modes가 없거나 1~2개만 있어도 세 모드가 채워지도록 관대하게 보정."""
    obj = _ensure_map(obj)
    modes = _ensure_map(obj.get("modes", {}))

    # 단일 블록만 넘어온 경우(문자열/맵) → grammar에 우선 배치
    if not modes:
        blob = { "persona": _coerce_str(obj.get("persona") or ""),
                 "system_instructions": _coerce_str(_get_syn(obj, "system_instructions", "system.instructions", "system", default="")) }
        modes = {"grammar": blob}

    # 각 모드 보정 함수
    def _norm_mode(key: str, block: Any, *, default_persona: str, default_sys: str) -> Dict[str, Any]:
        b = _ensure_map(block)
        persona = _coerce_str(_get_syn(b, "persona", "tone", default=default_persona))
        sysi = _coerce_str(_get_syn(b, "system_instructions", "system.instructions", "system", "instructions", default=default_sys))
        guard = _ensure_map(_get_syn(b, "guardrails", "guard", default={"pii": True}))
        cites = _coerce_str(_get_syn(b, "citations_policy", "citations.policy", "citationsPolicy",
                                     default="[이유문법]/[문법서적]/[AI지식]"))
        rh = _ensure_map(_get_syn(b, "routing_hints", "routing.hints", default={}))
        # 모델 기본값(합의안): grammar=gpt-5-pro, sentence=gemini-pro, passage=gpt-5-pro
        default_model = {"grammar":"gpt-5-pro", "sentence":"gemini-pro", "passage":"gpt-5-pro"}.get(key, "gpt-5-pro")
        rh.setdefault("model", _coerce_str(_get_syn(rh, "model", "llm", default=default_model)))
        rh.setdefault("max_tokens", 800 if key=="grammar" else (700 if key=="sentence" else 900))
        rh.setdefault("temperature", 0.2 if key=="grammar" else (0.3 if key=="sentence" else 0.4))
        return {
            "persona": persona,
            "system_instructions": sysi,
            "guardrails": guard or {"pii": True},
            "examples": _get_syn(b, "examples", "few_shots", default=[]) or [],
            "citations_policy": cites or "[이유문법]/[문법서적]/[AI지식]",
            "routing_hints": rh,
        }

    # 부족한 모드는 가장 가까운 것을 복제
    g_src = modes.get("grammar", {})
    s_src = modes.get("sentence", g_src)
    p_src = modes.get("passage", s_src)

    modes["grammar"]  = _norm_mode("grammar",  g_src,
                                   default_persona=_coerce_str(_get_syn(g_src, "persona", default="")),
                                   default_sys="규칙→근거→예문→요약")
    modes["sentence"] = _norm_mode("sentence", s_src,
                                   default_persona=_coerce_str(_get_syn(s_src, "persona", default="")),
                                   default_sys="토큰화→구문(괄호규칙)→어감/의미분석")
    modes["passage"]  = _norm_mode("passage",  p_src,
                                   default_persona=_coerce_str(_get_syn(p_src, "persona", default="")),
                                   default_sys="요지→예시/비유→주제→제목")

    obj["version"] = obj.get("version") or "auto"
    obj["modes"] = modes
    return obj
# ===== [02] low-level helpers — END =====


# ===== [03] LLM call — START =====
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
    # “엄격” 대신 “권장 스키마 + 실패 시 최소형”으로 완화
    sys = (
        "You are a Korean prompt normalizer.\n"
        "- Return **YAML only** (no commentary). If you include fences, still keep valid YAML inside.\n"
        "- Target schema (lenient):\n"
        "  version: auto\n"
        "  modes:\n"
        "    grammar: { persona, system_instructions, guardrails, examples, citations_policy, routing_hints }\n"
        "    sentence: {...}\n"
        "    passage:  {...}\n"
        "- Field synonyms allowed: system_instructions ≈ system.instructions ≈ system.\n"
        "- If unsure, output a **minimal skeleton** with empty strings and defaults.\n"
        "- Korean output only."
    )
    user = (
        "입력(문법 한 덩어리):\n" + grammar.strip() + "\n\n"
        "입력(문장 한 덩어리):\n" + sentence.strip() + "\n\n"
        "입력(지문 한 덩어리):\n" + passage.strip() + "\n\n"
        "위 3개 입력을 분석해 위 스키마(관대) 형태의 YAML을 생성해 주세요."
    )
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]
# ===== [03] LLM call — END =====


# ===== [04] public API — START =====
def normalize_to_yaml(
    *,
    grammar_text: str,
    sentence_text: str,
    passage_text: str,
    openai_key: Optional[str],
    openai_model: str = "gpt-4o-mini",
) -> str:
    """
    자연어 3종(문법/문장/지문)을 받아 관대한 스키마로 정규화된 YAML을 반환.
    - 1) LLM 시도(관대 프롬프트) → 2) 코드펜스 제거 → 3) YAML/JSON 파싱
    - 4) 동의어/타입/누락 필드 보정(Repair) → 5) 덤프
    - 실패 시 최소 스켈레톤으로 폴백
    """
    grammar_text = _sanitize_ellipsis(grammar_text)
    sentence_text = _sanitize_ellipsis(sentence_text)
    passage_text = _sanitize_ellipsis(passage_text)

    yaml_text = ""
    if openai_key:
        try:
            msgs = _build_prompt(grammar_text, sentence_text, passage_text)
            out = _post_openai(openai_key, openai_model, msgs, temperature=0.2)
            yaml_text = _strip_code_fences(out).strip()
        except Exception:
            yaml_text = ""

    def _minimal_obj() -> Dict[str, Any]:
        return {
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

    # 1차 파싱 시도 (YAML 우선, 실패 시 JSON도 수용)
    obj: Dict[str, Any] | None = None
    if yaml_text:
        try:
            obj_raw = yaml.safe_load(yaml_text)
            obj = obj_raw if isinstance(obj_raw, dict) else None
        except Exception:
            obj = None
        if obj is None:
            try:
                obj_raw = json.loads(yaml_text)
                obj = obj_raw if isinstance(obj_raw, dict) else None
            except Exception:
                obj = None

    if obj is None:
        obj = _minimal_obj()

    # 관대한 Repair: 동의어/타입 보정 + 누락 채우기
    try:
        obj = _ensure_modes(obj)
    except Exception:
        obj = _ensure_modes(_minimal_obj())

    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)
# ===== [04] public API — END =====
# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — END =====
