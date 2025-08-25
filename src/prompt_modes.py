# ============================================================
# ============ [PM-01] PROMPT MODES MODULE (NEW) =============
# ============================================================
# 목적:
# - 모드별 프롬프트 규칙을 코드에서 분리하고, 관리자 커스텀을 ~/.maic/prompts.yaml 로 관리
# - build_prompt(mode, question, lang="ko", extras={}) -> PromptParts
# - provider 어댑터 예시(to_openai/to_gemini) 포함
#
# 허용 플레이스홀더(템플릿 내에서 사용 가능):
#   {question}  : 학생이 입력한 질문/문장/지문
#   {mode}      : 선택된 모드(예: 문법설명/문장구조분석/지문분석)
#   {lang}      : 안내/설명 기본 언어(ko/en 등)
#   {today}     : yyyy-mm-dd
#   {level}     : 난이도/학년 등(옵션, extras로 주입)
#   {tone}      : 톤(친절/간결/격려 등, 옵션)
#   {examples}  : 예시문/샘플(옵션)
#   {context}   : 선택 컨텍스트(예: 학습목표/교재 등, 옵션)
#
# YAML 오버라이드 파일 예시(~/.maic/prompts.yaml):
# ------------------------------------------------------------
# version: 1
# global:
#   system: |
#     너는 학생을 격려하는 영어 코치야. {lang}로 답해.
#   provider_kwargs:
#     temperature: 0.2
# modes:
#   문법설명:
#     user: |
#       질문: {question}
#       규칙→예외→예문 3개로 간단히.
#   문장구조분석:
#     user: |
#       문장을 품사/구/절로 분석하고 마지막에 [S:..|V:..|O:..].
#   지문분석:
#     provider_kwargs:
#       temperature: 0.1
# ------------------------------------------------------------

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import os, json

# ---- YAML 지원(없으면 JSON 폴백) --------------------------------------------
try:
    import yaml  # type: ignore
except Exception:  # PyYAML이 없으면 내부 json으로 폴백
    yaml = None  # noqa: N816

# ---- 안전한 format_map ------------------------------------------------------
class _SafeDict(dict):
    def __missing__(self, key):
        # 알 수 없는 플레이스홀더는 그대로 남겨둔다: "{key}"
        return "{" + key + "}"

def _fmt(template: str, values: Dict[str, Any]) -> str:
    try:
        return str(template).format_map(_SafeDict(values))
    except Exception:
        # 템플릿 오류는 원문 반환(앱이 죽지 않도록)
        return str(template)

# ---- 데이터 구조 ------------------------------------------------------------
@dataclass
class PromptParts:
    system: str
    user: str
    tools: Optional[list] = None
    provider_kwargs: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ModeSpec:
    name: str
    version: str
    system_template: str
    user_template: str
    provider_kwargs: Dict[str, Any]

# ---- 기본 템플릿(필요 최소한, 한국어 중심) -----------------------------------
GLOBAL_DEFAULT = ModeSpec(
    name="GLOBAL",
    version="1.0.0",
    system_template=(
        "너는 학생을 돕는 영어 코치야. 답변은 {lang}로 친절하고 간결하게.\n"
        "사실 확인이 필요한 내용은 조심스럽게 다루고, 모르면 솔직히 모른다고 말해.\n"
        "불필요한 장황함은 피하고, 예시는 짧고 명확하게."
    ),
    user_template="",
    provider_kwargs={"temperature": 0.2, "max_tokens": 1024},
)

MODE_DEFAULTS: Dict[str, ModeSpec] = {
    # 문법설명 / Grammar
    "문법설명": ModeSpec(
        name="문법설명", version="1.0.0",
        system_template=(
            "역할: 영문법 튜터. 규칙→예외 순서로 설명하고, 마지막에 간단 체크리스트 제공.\n"
            "설명은 국문, 예문은 영어 {examples}."
        ),
        user_template=(
            "질문(문장/규칙): {question}\n"
            "요구사항:\n"
            "1) 핵심 규칙 3줄 요약\n"
            "2) 자주 틀리는 예외 2가지\n"
            "3) 예문 3개(영어/해석)\n"
            "4) 한 줄 마무리 팁\n"
        ),
        provider_kwargs={"temperature": 0.1},
    ),
    # 문장구조분석 / Sentence
    "문장구조분석": ModeSpec(
        name="문장구조분석", version="1.0.0",
        system_template=(
            "역할: 문장 구조 분석가.\n"
            "품사 태깅, 구/절 분해, 의존관계 핵심만. 과잉 용어 사용 금지."
        ),
        user_template=(
            "분석 대상 문장: {question}\n"
            "출력 형식:\n"
            "- 품사 태깅(핵심 단어 위주)\n"
            "- 구/절 구조 요약(2~4줄)\n"
            "- 핵심 골격: [S: … | V: … | O: … | C: … | M: …]\n"
            "- 오해하기 쉬운 포인트 1개"
        ),
        provider_kwargs={"temperature": 0.1},
    ),
    # 지문분석 / Passage
    "지문분석": ModeSpec(
        name="지문분석", version="1.0.0",
        system_template=(
            "역할: 리딩 코치. 요지와 근거 중심으로 설명하되, 불필요한 요약은 지양."
        ),
        user_template=(
            "지문(또는 질문): {question}\n"
            "원하는 출력:\n"
            "1) 한 줄 요지\n"
            "2) 핵심 논지/전개(3포인트)\n"
            "3) 근거 문장 번호 또는 단서(가능하면)\n"
            "4) 오답유형 주의 1가지"
        ),
        provider_kwargs={"temperature": 0.2},
    ),
}

# 영어 별칭(호환)
MODE_ALIASES = {
    "Grammar": "문법설명",
    "Sentence": "문장구조분석",
    "Passage": "지문분석",
    # 과거 표기 호환
    "문장분석": "문장구조분석",
}

def _normalize_mode(mode: str) -> str:
    m = str(mode or "").strip()
    return MODE_ALIASES.get(m, m) if m else "문법설명"

# ---- 경로/저장소 ------------------------------------------------------------
def get_overrides_path() -> Path:
    base = Path(os.path.expanduser("~")) / ".maic"
    base.mkdir(parents=True, exist_ok=True)
    return base / "prompts.yaml"

def load_overrides() -> Dict[str, Any]:
    p = get_overrides_path()
    if not p.exists():
        return {}
    try:
        if yaml:
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            # yaml이 없으면 json으로 읽어보기
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}

def save_overrides(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    try:
        p = get_overrides_path()
        if yaml:
            with p.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        else:
            with p.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def reset_overrides() -> Tuple[bool, Optional[str]]:
    try:
        p = get_overrides_path()
        if p.exists():
            p.unlink()
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# ---- 머지 유틸 --------------------------------------------------------------
def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def _spec_to_dict(spec: ModeSpec) -> Dict[str, Any]:
    return {
        "name": spec.name,
        "version": spec.version,
        "system": spec.system_template,
        "user": spec.user_template,
        "provider_kwargs": dict(spec.provider_kwargs or {}),
    }

def _build_defaults_dict() -> Dict[str, Any]:
    return {
        "version": 1,
        "global": {
            "system": GLOBAL_DEFAULT.system_template,
            "user": GLOBAL_DEFAULT.user_template,
            "provider_kwargs": dict(GLOBAL_DEFAULT.provider_kwargs),
        },
        "modes": {k: _spec_to_dict(v) for k, v in MODE_DEFAULTS.items()},
    }

# ---- 외부 공개: 모드 스펙과 프롬프트 빌더 -----------------------------------
def list_modes() -> Dict[str, str]:
    """지원 모드 목록(표시명→내부명 동일)"""
    return {k: k for k in MODE_DEFAULTS.keys()}

def get_prompt_spec(mode: str) -> Dict[str, Any]:
    """
    현재 적용되는 (기본+오버라이드) 스펙을 dict로 반환
    """
    defaults = _build_defaults_dict()
    overrides = load_overrides()
    merged = _deep_merge(defaults, overrides)

    mname = _normalize_mode(mode)
    global_spec = merged.get("global", {})
    mode_spec = merged.get("modes", {}).get(mname, {})

    # 별칭 키(Grammar, Sentence, Passage)가 overrides에 있으면 흡수
    alias = MODE_ALIASES.get(mode)
    if alias and alias in (merged.get("modes") or {}):
        mode_spec = _deep_merge(mode_spec, merged["modes"][alias])

    # 최종 dict
    out = {
        "global": global_spec,
        "mode": mode_spec,
    }
    return out

def build_prompt(mode: str, question: str, *, lang: str = "ko", extras: Optional[Dict[str, Any]] = None) -> PromptParts:
    """
    모드/질문 기반의 최종 PromptParts 생성.
    - 기본 템플릿 + ~/.maic/prompts.yaml 오버라이드 병합
    - 플레이스홀더: {question}, {mode}, {lang}, {today}, + extras(dict)
    """
    extras = extras or {}
    values = {
        "question": question or "",
        "mode": _normalize_mode(mode),
        "lang": lang or "ko",
        "today": datetime.now().strftime("%Y-%m-%d"),
        **extras,
    }

    # 스펙 병합
    spec = get_prompt_spec(mode)
    g = spec.get("global", {}) or {}
    m = spec.get("mode", {}) or {}

    # system/user 텍스트 합성: global.system + mode.system / mode.user
    sys_global = str(g.get("system") or GLOBAL_DEFAULT.system_template)
    usr_global = str(g.get("user") or GLOBAL_DEFAULT.user_template)
    sys_mode   = str(m.get("system") or MODE_DEFAULTS[_normalize_mode(mode)].system_template)
    usr_mode   = str(m.get("user")   or MODE_DEFAULTS[_normalize_mode(mode)].user_template)

    system_text = _fmt(sys_global, values).strip()
    if sys_mode.strip():
        system_text = (system_text + "\n\n" + _fmt(sys_mode, values)).strip()

    user_text = _fmt(usr_global, values).strip()
    if usr_mode.strip():
        # user_global → user_mode 순으로 이어붙임(전역 요구 후, 모드 지시)
        user_text = ((user_text + "\n\n") if user_text else "") + _fmt(usr_mode, values)

    # provider kwargs 병합: global < mode < extras.provider_kwargs
    pk_global = dict(g.get("provider_kwargs") or {})
    pk_mode   = dict(m.get("provider_kwargs") or {})
    pk_extra  = dict((extras.get("provider_kwargs") or {}))
    provider_kwargs = _deep_merge(_deep_merge(pk_global, pk_mode), pk_extra) or None

    return PromptParts(
        system=system_text,
        user=user_text,
        tools=None,
        provider_kwargs=provider_kwargs,
        meta={
            "mode": _normalize_mode(mode),
            "lang": lang,
            "placeholders": list(_SafeDict().keys()) if hasattr(_SafeDict, "keys") else None,
        },
    )

# ---- 프로바이더 어댑터(참고용): 실제 LLM 호출부에서 활용 -----------------------
def to_openai(parts: PromptParts) -> Dict[str, Any]:
    """
    OpenAI 스타일 페이로드 예시(messages 기반).
    - 모델 선택은 호출부에서 지정하세요.
    """
    messages = []
    if parts.system.strip():
        messages.append({"role": "system", "content": parts.system})
    if parts.user.strip():
        messages.append({"role": "user", "content": parts.user})
    payload = {"messages": messages}
    if parts.provider_kwargs:
        payload.update(parts.provider_kwargs)
    return payload

def to_gemini(parts: PromptParts) -> Dict[str, Any]:
    """
    Gemini 스타일 페이로드 예시(contents 기반).
    - system을 프롬프트 전문 상단에 접두사로 합쳐 전달(간단 방식)
    """
    full = parts.system.strip()
    if parts.user.strip():
        full = (full + "\n\n" + parts.user.strip()).strip()
    payload = {
        "contents": [{"role": "user", "parts": [{"text": full}]}]
    }
    if parts.provider_kwargs:
        payload.update(parts.provider_kwargs)
    return payload

# ---- 편의: 기본 오버라이드 파일을 만들어주는 헬퍼(선택) ----------------------
def write_default_overrides_if_missing() -> bool:
    """
    ~/.maic/prompts.yaml 이 없으면 기본 템플릿을 써준다.
    이미 있으면 False, 새로 썼으면 True 반환.
    """
    p = get_overrides_path()
    if p.exists():
        return False
    data = _build_defaults_dict()
    ok, _ = save_overrides(data)
    return bool(ok)

# ========================== [PM-01] END ============================
