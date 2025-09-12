# [20A] START: src/core/prompt_loader.py (FULL ADD)
from __future__ import annotations

from typing import Optional, List
from pathlib import Path
import os


def _read_text(path: Path) -> Optional[str]:
    try:
        if path.exists() and path.is_file():
            s = path.read_text(encoding="utf-8")
            s = (s or "").strip()
            return s or None
    except Exception:
        pass
    return None


def _read_yaml_sentence_rules(path: Path) -> Optional[str]:
    """
    가벼운 의존: PyYAML이 있으면 사용하고, 없으면 건너뜁니다.
    기대 경로:
      sentence:
        bracket_rules: |-
          ...여기에 규칙...
    """
    try:
        import yaml  # type: ignore[import-not-found]
    except Exception:
        return None

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            s1 = data.get("sentence") or {}
            s2 = s1.get("bracket_rules")
            if isinstance(s2, str) and s2.strip():
                return s2.strip()
    except Exception:
        return None
    return None


def _clamp(text: str, *, max_chars: int = 4000) -> str:
    # modes.types.clamp_fragments 가 있으면 사용(SSOT), 없으면 단순 절단
    try:
        from modes.types import clamp_fragments  # type: ignore
        clamped = clamp_fragments([text], max_items=1, max_chars_each=max_chars)
        return (clamped[0] if clamped else "") or ""
    except Exception:
        s = (text or "")[: max_chars]
        return s.strip()


def get_bracket_rules() -> str:
    """
    사용자 보유 괄호규칙 로더(우선순위 높은 것부터):
      1) st.secrets["BRACKET_RULES"] 또는 ["SENTENCE_BRACKET_PROMPT"]
      2) env BRACKET_RULES / SENTENCE_BRACKET_PROMPT
      3) 파일:
         - env PROMPTS_PATH / GH_PROMPTS_PATH (md/txt/yaml)
         - ./prompts/bracket_rules.md, ./bracket_rules.md
         - ./prompts.yaml (yaml 키: sentence.bracket_rules)
      4) 폴백: 라벨 세트 안내(간단)
    """
    # 1) secrets
    try:
        import streamlit as st  # type: ignore
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
    # 3-1) env 지정 경로
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

    # 3-2) 기본 후보들
    for p in [
        Path("prompts/bracket_rules.md"),
        Path("bracket_rules.md"),
    ]:
        t = _read_text(p)
        if t:
            return _clamp(t)

    yml = Path("prompts.yaml")
    y = _read_yaml_sentence_rules(yml) if yml.exists() else None
    if y:
        return _clamp(y)

    # 4) fallback: 최소 라벨 세트 안내
    fallback = (
        "※ 사용자 괄호규칙이 설정되지 않았습니다. 기본 라벨 세트 안내입니다.\n"
        "- 사용 라벨: S(주어), V(동사), O(목적어), C(보어), M(수식어), "
        "Sub(부사절), Rel(관계절), ToInf(to부정사), Ger(동명사), Part(분사), "
        "Appo(동격), Conj(접속)\n"
        "예: [Sub because it rained], [S I] [V stayed] [M at home]"
    )
    return _clamp(fallback)
# [20A] END: src/core/prompt_loader.py
