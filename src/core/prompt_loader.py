# [30A] START: src/core/prompt_loader.py (FULL REPLACEMENT)
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import importlib
import os
import re

# mtime 캐시: (mtime, data)
_PROMPTS_CACHE: Tuple[float, Dict[str, Any]] | None = None


def _resolve_path() -> Path:
    """
    prompts.yaml 경로 우선순위:
      1) env MAIC_PROMPTS_PATH
      2) streamlit.secrets["PROMPTS_PATH"]
      3) ./prompts.yaml
    """
    p = (os.getenv("MAIC_PROMPTS_PATH") or "").strip()
    if p:
        return Path(p).expanduser()

    # streamlit이 없는 환경도 있으므로 동적 import
    try:
        st = importlib.import_module("streamlit")
        secrets_obj = getattr(st, "secrets", {})
        sp = (secrets_obj.get("PROMPTS_PATH") or "").strip()
        if sp:
            return Path(sp).expanduser()
    except Exception:
        pass

    return Path("prompts.yaml").expanduser()


def _read_text(fp: Path) -> Optional[str]:
    try:
        if not fp.exists() or not fp.is_file():
            return None
        return fp.read_text(encoding="utf-8")
    except Exception:
        return None


def _parse_yaml(txt: str) -> Dict[str, Any]:
    """PyYAML이 있으면 파싱, 없으면 {} 반환(폴백 유도)."""
    try:
        yaml = importlib.import_module("yaml")
    except Exception:
        return {}
    try:
        data = yaml.safe_load(txt)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_prompts() -> Dict[str, Any]:
    """prompts.yaml을 mtime 캐시로 로드. 실패 시 {}."""
    global _PROMPTS_CACHE
    fp = _resolve_path()
    txt = _read_text(fp)
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


# ----------------- 모드 라벨/키 정규화 -----------------
_MODEKEY_TO_LABEL = {
    "grammar": "문법설명",
    "sentence": "문장구조분석",
    "passage": "지문분석",
}
# responder 폴백 힌트
_FALLBACK_HINT = {
    "문법설명": "핵심 규칙 → 간단 예시 → 흔한 오해 순서로 쉽게 설명하세요.",
    "문장구조분석": "품사/구문 역할을 표처럼 정리하고 핵심 포인트 3개를 요약하세요.",
    "지문분석": "주제/요지/세부정보를 구분하고 근거 문장을 제시하세요.",
}


def _label_for(mode: str) -> str:
    """
    내부키 또는 라벨 입력을 받아 한국어 라벨로 통일.
    미지정/알 수 없는 경우 '문법설명' 반환.
    """
    v = (mode or "").strip()
    if not v:
        return "문법설명"
    if v in _MODEKEY_TO_LABEL:
        return _MODEKEY_TO_LABEL[v]
    if v in _FALLBACK_HINT:
        return v
    return "문법설명"


def system_prompt_for(mode: str) -> str:
    """
    모드별 system 프롬프트를 로드.
    - 성공: prompts.yaml의 modes.<라벨>.system
    - 실패: 짧은 힌트 기반 폴백
    """
    label = _label_for(mode)
    data = load_prompts()
    try:
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            node = modes.get(label)
            if isinstance(node, dict):
                sys_txt = node.get("system")
                if isinstance(sys_txt, str) and sys_txt.strip():
                    return sys_txt.strip()
    except Exception:
        pass

    # 안전 폴백(라이브러리/파일 미존재/형식 오류 등)
    hint = _FALLBACK_HINT.get(label, "학생 눈높이에 맞춰 핵심→예시→한 줄 정리로 설명하세요.")
    return (
        "당신은 학생을 돕는 영어 선생님입니다. 불필요한 말은 줄이고, "
        "짧은 문장과 단계적 설명을 사용하세요. " + hint
    )


# ----------------- 괄호 규칙 로더(문장구조분석용) -----------------
_DEFAULT_BRACKET_RULE = (
    "괄호/기호 표기 규칙(요약)\n"
    "* [ ]: 명사적 용법(명사절/To부정사/Gerund 등)\n"
    "* { }: 형용사적 용법(관계절/분사/형용사 수식)\n"
    "* < >: 부사적 용법(부사절/부사구)\n"
    "* ( ): 전치사구\n"
    "* It-cleft: [[중심]] {that/관계절}, 부사 강조는 << >>\n"
    "* 생략 복원: (*생략항목) 표기로 그 자리 표시\n"
    "* the 비교급…, the 비교급…: 앞절은 < >, 뒷절은 일반 표기\n"
)


def get_bracket_rules() -> str:
    """
    문장구조분석용 괄호 규칙 문자열을 반환.
    우선순위:
      1) prompts.yaml: modes.문장구조분석.bracket_rules
      2) prompts.yaml: modes.문장구조분석.system 안의
         '[괄호/기호 표기 규칙' 섹션 자동 추출
      3) _DEFAULT_BRACKET_RULE 폴백
    """
    label = _label_for("sentence")
    data = load_prompts()

    try:
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            node = modes.get(label)
            if isinstance(node, dict):
                # 1) 명시 키가 있으면 최우선
                br = node.get("bracket_rules")
                if isinstance(br, str) and br.strip():
                    return br.strip()

                # 2) system 안에서 섹션 자동 추출
                sys_txt = node.get("system")
                if isinstance(sys_txt, str) and sys_txt.strip():
                    # 헤더 줄부터 끝까지를 보수적으로 취함
                    # 예: "[괄호/기호 표기 규칙 — 엄수]" 같은 패턴
                    pat = r"(?ms)^\s*\[(?:괄호|괄호/기호)[^\]]*\]\s*(.*?)\Z"
                    m = re.search(pat, sys_txt)
                    if m:
                        return m.group(1).strip()
    except Exception:
        pass

    return _DEFAULT_BRACKET_RULE
# [30A] END: src/core/prompt_loader.py
