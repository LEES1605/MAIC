# [22A] START: src/core/prompt_loader.py (FULL REPLACEMENT)
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, List, TypedDict
import os
import re


# ----------------------------- common utils ---------------------------------
def _read_text(path: Path) -> Optional[str]:
    try:
        if path.exists() and path.is_file():
            s = path.read_text(encoding="utf-8")
            s = (s or "").strip()
            return s or None
    except Exception:
        pass
    return None


def _safe_yaml_load(path: Path) -> Optional[dict]:
    try:
        import yaml
    except Exception:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clamp(text: str, *, max_chars: int = 4000) -> str:
    """Prompt bloat / 주입 방지를 위한 길이 클램프."""
    try:
        # 가능하면 SSOT 유틸 사용
        from modes.types import clamp_fragments
        arr = clamp_fragments([text], max_items=1, max_chars_each=max_chars)
        return (arr[0] if arr else "").strip()
    except Exception:
        return (text or "")[:max_chars].strip()


# -------------------------- bracket rules loader -----------------------------
def _read_yaml_sentence_rules(path: Path) -> Optional[str]:
    """
    기대 구조:
      sentence:
        bracket_rules: |-
          ...여기에 규칙...
    """
    data = _safe_yaml_load(path)
    if not isinstance(data, dict):
        return None
    s1 = data.get("sentence") or {}
    if isinstance(s1, dict):
        s2 = s1.get("bracket_rules")
        if isinstance(s2, str) and s2.strip():
            return s2.strip()
    return None


def get_bracket_rules() -> str:
    """
    우선순위(높→낮):
      1) st.secrets["BRACKET_RULES"|"SENTENCE_BRACKET_PROMPT"]
      2) env BRACKET_RULES | SENTENCE_BRACKET_PROMPT
      3) 파일: env PROMPTS_PATH | GH_PROMPTS_PATH (md/txt/yaml)
               ./prompts/bracket_rules.md, ./bracket_rules.md, ./prompts.yaml
      4) 폴백: 기본 라벨 세트 안내
    """
    # 1) secrets
    try:
        import streamlit as st
        for k in ("BRACKET_RULES", "SENTENCE_BRACKET_PROMPT"):
            v = st.secrets.get(k)
            if isinstance(v, str) and v.strip():
                return _clamp(v)
    except Exception:
        pass

    # 2) env
    for k in ("BRACKET_RULES", "SENTENCE_BRACKET_PROMPT"):
        v = os.getenv(k, "").strip()
        if v:
            return _clamp(v)

    # 3) files
    for env_k in ("PROMPTS_PATH", "GH_PROMPTS_PATH"):
        p = Path(os.getenv(env_k, "").strip())
        if p and p.exists():
            if p.suffix.lower() in (".md", ".txt"):
                t = _read_text(p)
                if t:
                    return _clamp(t)
            if p.suffix.lower() in (".yaml", ".yml"):
                y = _read_yaml_sentence_rules(p)
                if y:
                    return _clamp(y)

    for p in [Path("prompts/bracket_rules.md"), Path("bracket_rules.md")]:
        t = _read_text(p)
        if t:
            return _clamp(t)

    yml = Path("prompts.yaml")
    y = _read_yaml_sentence_rules(yml) if yml.exists() else None
    if y:
        return _clamp(y)

    # 4) fallback
    fallback = (
        "※ 사용자 괄호규칙이 설정되지 않았습니다. 기본 라벨 세트 안내입니다.\n"
        "- 사용 라벨: S(주어), V(동사), O(목적어), C(보어), M(수식어), "
        "Sub(부사절), Rel(관계절), ToInf(to부정사), Ger(동명사), Part(분사), "
        "Appo(동격), Conj(접속)\n"
        "예: [Sub because it rained], [S I] [V stayed] [M at home]"
    )
    return _clamp(fallback)


# --------------------------- modes system/user loader ------------------------
class ModeText(TypedDict, total=False):
    system: str
    user: str


def _norm_mode_key(name: str) -> Optional[str]:
    """
    한국어/영문/별칭 → 내부 키("grammar"|"sentence"|"passage") 정규화.
    """
    k = (name or "").strip().lower()
    # 문장
    if k in {"문장", "문장구조분석", "sentence"}:
        return "sentence"
    # 문법
    if k in {"문법", "문법설명", "grammar"}:
        return "grammar"
    # 지문
    if k in {"지문", "지문분석", "passage"}:
        return "passage"
    return None


def _load_modes_from_yaml(path: Path) -> Dict[str, ModeText]:
    """
    prompts.yaml 의 구조:
      modes:
        문장구조분석:
          system: |-
            ...
          user: |-
            ...
        문법설명: ...
        지문분석: ...
    를 읽어 내부 키로 매핑한다.
    """
    data = _safe_yaml_load(path)
    out: Dict[str, ModeText] = {}
    if not isinstance(data, dict):
        return out
    modes = data.get("modes")
    if not isinstance(modes, dict):
        return out

    for name, blk in modes.items():
        key = _norm_mode_key(str(name))
        if not key:
            continue
        if isinstance(blk, dict):
            sys_txt = blk.get("system")
            usr_txt = blk.get("user")
            entry: ModeText = {}
            if isinstance(sys_txt, str) and sys_txt.strip():
                entry["system"] = _clamp(sys_txt)
            if isinstance(usr_txt, str) and usr_txt.strip():
                entry["user"] = _clamp(usr_txt)
            if entry:
                out[key] = entry
    return out


def get_custom_mode_prompts(mode_key: str) -> ModeText:
    """
    단일 모드에 대한 사용자 정의(system/user) 프롬프트를 반환.
    우선순위(높→낮):
      1) env PROMPTS_PATH | GH_PROMPTS_PATH (yaml)
      2) ./prompts.yaml
    """
    for env_k in ("PROMPTS_PATH", "GH_PROMPTS_PATH"):
        p = Path(os.getenv(env_k, "").strip())
        if p and p.exists() and p.suffix.lower() in (".yaml", ".yml"):
            m = _load_modes_from_yaml(p)
            if m.get(mode_key):
                return m[mode_key]

    yml = Path("prompts.yaml")
    if yml.exists():
        m = _load_modes_from_yaml(yml)
        if m.get(mode_key):
            return m[mode_key]

    return {}
# [22A] END: src/core/prompt_loader.py
