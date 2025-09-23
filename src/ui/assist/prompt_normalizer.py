# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — START =====
from __future__ import annotations

import importlib
import json
import re
from typing import Any, Dict, Optional, Tuple

import yaml

# ─────────────────────────────────────────────────────────────────────────────
# 상수/유틸
# ─────────────────────────────────────────────────────────────────────────────
ELLIPSIS_UC = "\u2026"

def _sanitize_ellipsis(text: str) -> str:
    """U+2026 → '...' 로 교체(빌드/CI 경고 회피)."""
    return (text or "").replace(ELLIPSIS_UC, "...")

def _as_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (list, tuple)):
        return "\n".join(str(t) for t in x if t is not None)
    if isinstance(x, (dict,)):
        try:
            return yaml.safe_dump(x, allow_unicode=True, sort_keys=False)
        except Exception:
            return json.dumps(x, ensure_ascii=False)
    return str(x)

# ─────────────────────────────────────────────────────────────────────────────
# LLM 호출 (필요 시)
# ─────────────────────────────────────────────────────────────────────────────
def _post_openai(api_key: str, model: str, messages: list[dict], temperature: float) -> str:
    """단순 REST 호출(요청/의존도를 낮춤). 실패 시 예외 발생."""
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
    """
    느슨한 출력 요구:
      - YAML 또는 JSON 반환 허용
      - 불필요한 추가 텍스트 금지(코드블록 선호)
      - 일부 키가 빠져도 됨(우리가 보정)
    """
    sys = (
        "당신은 한국어 프롬프트 정규화 도우미입니다.\n"
        "- 한 모드당 '자연어 텍스트 한 덩어리'가 주어집니다.\n"
        "- YAML 또는 JSON 중 하나로만 간단히 응답하세요. (코드블록 권장)\n"
        "- 가능한 키: persona, system_instructions, guardrails, examples,\n"
        "  citations_policy, routing_hints\n"
        "- 키가 일부 빠져도 됩니다(소박하게). 길게 늘어놓지 마세요.\n"
        "- 한국어 출력만 허용합니다.\n"
    )
    user = (
        "입력(문법 한 덩어리):\n" + grammar.strip() + "\n\n"
        "입력(문장 한 덩어리):\n" + sentence.strip() + "\n\n"
        "입력(지문 한 덩어리):\n" + passage.strip() + "\n\n"
        "모드 키 이름은 grammar/sentence/passage로 사용해 주세요."
    )
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]

# ─────────────────────────────────────────────────────────────────────────────
# 파싱/자동보정 (Lenient Parse + Coerce)
# ─────────────────────────────────────────────────────────────────────────────
_CODEBLOCK_RE = re.compile(
    r"```(?:\s*(yaml|yml|json))?\s*\n(.*?)\n```",
    re.IGNORECASE | re.DOTALL,
)

def _extract_struct(text: str) -> Optional[Dict[str, Any]]:
    """
    텍스트에서 YAML/JSON 구조를 '느슨하게' 추출:
    1) 코드블록 우선 탐색 → 형식 감안해 파싱
    2) 실패 시 전체 텍스트를 YAML → JSON 순으로 시도
    """
    if not text:
        return None

    m = _CODEBLOCK_RE.search(text)
    cand = text
    flavor = None
    if m:
        flavor = (m.group(1) or "").strip().lower()
        cand = m.group(2) or ""

    # 1) flavor 힌트 우선
    if flavor in ("json",):
        try:
            return json.loads(cand)
        except Exception:
            pass
    if flavor in ("yaml", "yml"):
        try:
            return yaml.safe_load(cand)
        except Exception:
            pass

    # 2) 힌트 없으면 YAML → JSON 순서
    for parser in (lambda s: yaml.safe_load(s), lambda s: json.loads(s)):
        try:
            obj = parser(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    # 3) 마지막으로 전체 텍스트 파싱
    for parser in (lambda s: yaml.safe_load(s), lambda s: json.loads(s)):
        try:
            obj = parser(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None

def _norm_mode_key(k: str) -> str:
    """모드 키 동의어를 표준키로 변환."""
    s = (k or "").strip().lower()
    mapping = {
        "문법": "grammar",
        "문장": "sentence",
        "지문": "passage",
        "grammar": "grammar",
        "sentence": "sentence",
        "passage": "passage",
    }
    return mapping.get(s, s)

def _pick_first(obj: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    return None

def _coerce_mode_block(raw: Any, *, default_text: str, mode: str) -> Dict[str, Any]:
    """
    모드 블록을 표준 형태로 보정.
    - raw가 str/list이면 persona 또는 instructions로 승격
    - dict면 동의어 필드 매핑
    """
    base_persona = _sanitize_ellipsis(_as_str(default_text)).strip()
    base_instr = {
        "grammar": "규칙→근거→예문→요약",
        "sentence": "토큰화→구문(괄호규칙)→어감/의미분석",
        "passage": "요지→예시/비유→주제→제목",
    }.get(mode, "")

    if raw is None:
        raw = {}

    if isinstance(raw, (str, list, tuple)):
        # 사람이 통으로 써 넣은 한 덩어리 → persona에 담고, instructions는 기본값
        persona = _sanitize_ellipsis(_as_str(raw)).strip() or base_persona
        return {
            "persona": persona,
            "system_instructions": base_instr,
            "guardrails": {"pii": True},
            "examples": [],
            "citations_policy": "[이유문법]/[문법서적]/[AI지식]",
            "routing_hints": _default_routing(mode),
        }

    if not isinstance(raw, dict):
        raw = {}

    # 동의어 매핑
    persona = _pick_first(raw, "persona", "tone", "style", "role")
    instr = _pick_first(raw, "system_instructions", "system", "instructions", "rules", "steps", "guidelines")
    guard = _pick_first(raw, "guardrails", "guard", "safety")
    examples = _pick_first(raw, "examples", "shots", "few_shots")
    routes = _pick_first(raw, "routing_hints", "routing")
    citations = _pick_first(raw, "citations_policy", "citations", "sources", "출처정책")

    # 타입 보정
    persona = _sanitize_ellipsis(_as_str(persona or base_persona)).strip()
    instr = _sanitize_ellipsis(_as_str(instr or base_instr)).strip()

    if isinstance(guard, bool):
        guard = {"pii": bool(guard)}
    elif not isinstance(guard, dict):
        guard = {"pii": True}

    if not isinstance(examples, list):
        examples = []

    if not isinstance(routes, dict):
        routes = {}
    routes = _merge_routing_defaults(routes, mode)

    citations = str(citations or "[이유문법]/[문법서적]/[AI지식]")

    return {
        "persona": persona,
        "system_instructions": instr,
        "guardrails": guard,
        "examples": examples,
        "citations_policy": citations,
        "routing_hints": routes,
    }

def _default_routing(mode: str) -> Dict[str, Any]:
    defaults = {
        "grammar": {"model": "gpt-5-pro", "max_tokens": 800, "temperature": 0.2},
        "sentence": {"model": "gemini-pro", "max_tokens": 700, "temperature": 0.3},
        "passage": {"model": "gpt-5-pro", "max_tokens": 900, "temperature": 0.4},
    }
    return dict(defaults.get(mode, {"model": "gpt-5-pro"}))

def _merge_routing_defaults(routes: Dict[str, Any], mode: str) -> Dict[str, Any]:
    out = _default_routing(mode)
    # 허용 키만 반영
    for k in ("model", "temperature", "max_tokens", "provider"):
        if k in routes:
            out[k] = routes[k]
    # 흔한 약칭/동의어
    if "mdl" in routes and "model" not in out:
        out["model"] = routes["mdl"]
    if "temp" in routes and "temperature" not in out:
        out["temperature"] = routes["temp"]
    return out

def _coerce_all(
    raw: Dict[str, Any] | None,
    *,
    grammar_text: str,
    sentence_text: str,
    passage_text: str,
) -> Dict[str, Any]:
    """루트 객체 보정: modes 유무/키 동의어/모드별 보정."""
    raw = raw or {}
    # root가 바로 modes일 수도 있음
    modes = raw.get("modes") if isinstance(raw, dict) else None
    if not isinstance(modes, dict):
        # 루트에 문법/문장/지문 키가 있을 수도
        modes = {}
        for k, v in (raw.items() if isinstance(raw, dict) else []):
            nk = _norm_mode_key(k)
            if nk in ("grammar", "sentence", "passage"):
                modes[nk] = v

    # 최종 데이터 골격
    out: Dict[str, Any] = {"version": "auto", "modes": {}}

    # 각 모드 채우기(없으면 기본+자연어 입력)
    out["modes"]["grammar"] = _coerce_mode_block(
        modes.get("grammar") if isinstance(modes, dict) else None,
        default_text=grammar_text, mode="grammar",
    )
    out["modes"]["sentence"] = _coerce_mode_block(
        modes.get("sentence") if isinstance(modes, dict) else None,
        default_text=sentence_text, mode="sentence",
    )
    out["modes"]["passage"] = _coerce_mode_block(
        modes.get("passage") if isinstance(modes, dict) else None,
        default_text=passage_text, mode="passage",
    )
    return out

# ─────────────────────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────────────────────
def normalize_to_yaml(
    *,
    grammar_text: str,
    sentence_text: str,
    passage_text: str,
    openai_key: Optional[str],
    openai_model: str = "gpt-4o-mini",
) -> str:
    """
    세 모드 입력(각각 자연어 한 덩어리)을 받아 '느슨한 스키마'를 생성.
    - LLM이 내놓은 YAML/JSON이 다소 틀려도 보정(coerce)하여 완전한 YAML을 반환
    - LLM 호출 실패/이상 출력 시에는 기본 템플릿으로 폴백
    """
    grammar_text = _sanitize_ellipsis(grammar_text)
    sentence_text = _sanitize_ellipsis(sentence_text)
    passage_text = _sanitize_ellipsis(passage_text)

    # 1) LLM 시도(있으면)
    obj: Optional[Dict[str, Any]] = None
    if openai_key:
        try:
            msgs = _build_prompt(grammar_text, sentence_text, passage_text)
            raw_out = _post_openai(openai_key, openai_model, msgs, temperature=0.2)
            obj = _extract_struct(raw_out.strip())
        except Exception:
            obj = None  # 그냥 폴백으로

    # 2) 보정/완성
    data = _coerce_all(
        obj,
        grammar_text=grammar_text,
        sentence_text=sentence_text,
        passage_text=passage_text,
    )

    # 3) 최종 YAML
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
# ===== [01] FILE: src/ui/assist/prompt_normalizer.py — END =====
