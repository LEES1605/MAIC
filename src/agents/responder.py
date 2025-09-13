# [28A] START: src/agents/responder.py (FULL REPLACEMENT)
from __future__ import annotations

from typing import Iterator, Optional, Dict, Any, Tuple
from pathlib import Path
import importlib
import os
import time

from src.agents._common import stream_llm


# --------------------------- prompts.yaml loader ----------------------------
_PROMPTS_CACHE: Tuple[float, Dict[str, Any]] | None = None  # (mtime, data)


def _prompts_path() -> Path:
    """
    Resolve prompts.yaml path with precedence:
      1) env MAIC_PROMPTS_PATH
      2) st.secrets["PROMPTS_PATH"]
      3) ./prompts.yaml
    """
    # 1) env
    p = (os.getenv("MAIC_PROMPTS_PATH") or "").strip()
    if p:
        return Path(p).expanduser()

    # 2) streamlit secrets (optional)
    try:
        st = importlib.import_module("streamlit")
        secrets_obj = getattr(st, "secrets", {})
        sp = (secrets_obj.get("PROMPTS_PATH") or "").strip()
        if sp:
            return Path(sp).expanduser()
    except Exception:
        pass

    # 3) default
    return Path("prompts.yaml").expanduser()


def _load_yaml_text(fp: Path) -> Optional[str]:
    try:
        if not fp.exists() or not fp.is_file():
            return None
        return fp.read_text(encoding="utf-8")
    except Exception:
        return None


def _parse_yaml(txt: str) -> Dict[str, Any]:
    """
    Parse YAML if PyYAML is available; else return {} to trigger fallback.
    """
    try:
        yaml = importlib.import_module("yaml")
    except Exception:
        return {}
    try:
        data = yaml.safe_load(txt)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_prompts_yaml() -> Dict[str, Any]:
    """
    Load prompts.yaml with simple mtime-based cache.
    Returns {} on any failure (so caller will fallback).
    """
    global _PROMPTS_CACHE
    fp = _prompts_path()
    txt = _load_yaml_text(fp)
    if txt is None:
        _PROMPTS_CACHE = None
        return {}

    try:
        mtime = fp.stat().st_mtime
    except Exception:
        mtime = 0.0

    if _PROMPTS_CACHE and _PROMPTS_CACHE[0] == mtime:
        return _PROMPTS_CACHE[1]

    data = _parse_yaml(txt)
    _PROMPTS_CACHE = (mtime, data)
    return data


# ----------------------------- system prompt -------------------------------
_HINTS_BY_MODE: Dict[str, str] = {
    "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 쉽게 설명하세요.",
    "문장구조분석": "품사/구문 역할을 표처럼 정리하고 핵심 포인트 3개를 요약하세요.",
    "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 제시하세요.",
}

# 내부키 → YAML 한글 라벨 매핑
_MODEKEY_TO_LABEL: Dict[str, str] = {
    "grammar": "문법설명",
    "sentence": "문장구조분석",
    "passage": "지문분석",
}


def _normalize_mode_label(mode_in: str) -> str:
    """
    Accepts internal key or Korean label; returns Korean label.
    Unknown input → '문법설명'.
    """
    v = (mode_in or "").strip()
    if not v:
        return "문법설명"
    # 내부키 매핑
    if v in _MODEKEY_TO_LABEL:
        return _MODEKEY_TO_LABEL[v]
    # 한글 라벨로 들어온 경우(정확 일치만)
    if v in _HINTS_BY_MODE:
        return v
    # 기타 → 기본
    return "문법설명"


def _system_prompt(mode: str) -> str:
    """
    Build system prompt from prompts.yaml if available; else fallback hints.
    """
    label = _normalize_mode_label(mode)
    data = _load_prompts_yaml()

    # YAML 경로: modes.<라벨>.system
    sys_txt = None
    try:
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            node = modes.get(label)
            if isinstance(node, dict):
                val = node.get("system")
                if isinstance(val, str) and val.strip():
                    sys_txt = val.strip()
    except Exception:
        sys_txt = None

    if not sys_txt:
        # 안전 폴백: 기존 하드코딩 힌트 기반
        hint = _HINTS_BY_MODE.get(label, "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명하세요.")
        return (
            "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
            "짧은 문장과 단계적 설명을 사용하세요. " + hint
        )

    return sys_txt


# ------------------------------ answer stream ------------------------------
def answer_stream(
    *,
    question: str,
    mode: str,
    ctx: Optional[Dict[str, str]] = None,
) -> Iterator[str]:
    """
    주답변(피티쌤) 스트리밍 제너레이터.
    - prompts.yaml → system 프롬프트 선택(핫리로드)
    - 공통 SSOT(stream_llm)만 호출하여 중복 제거
    - split_fallback=True: 콜백 미지원 provider에서 문장단위 의사 스트리밍
    """
    sys_p = _system_prompt(mode)
    yield from stream_llm(
        system_prompt=sys_p,
        user_prompt=question,
        split_fallback=True,
    )
# [28A] END: src/agents/responder.py
