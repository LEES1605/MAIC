# [32A] START: src/core/prompt_loader.py (FULL REPLACEMENT)
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
    "* the 비교급..., the 비교급...: 앞절은 < >, 뒷절은 일반 표기\n"
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
                br = node.get("bracket_rules")
                if isinstance(br, str) and br.strip():
                    return br.strip()

                sys_txt = node.get("system")
                if isinstance(sys_txt, str) and sys_txt.strip():
                    pat = r"(?ms)^\s*\[(?:괄호|괄호/기호)[^\]]*\]\s*(.*?)\Z"
                    m = re.search(pat, sys_txt)
                    if m:
                        return m.group(1).strip()
    except Exception:
        pass

    return _DEFAULT_BRACKET_RULE


# ----------------- user 템플릿 로더 -----------------
def _fill_placeholders(tpl: str, values: Dict[str, str]) -> str:
    """
    단순 치환: values의 키에 대해 '{KEY}'만 치환.
    알 수 없는 플레이스홀더나 다른 중괄호는 그대로 둔다.
    """
    out = str(tpl)
    for k, v in values.items():
        out = out.replace("{" + str(k) + "}", str(v))
    return out


def user_prompt_for(mode: str, question: str, ctx: Optional[Dict[str, str]] = None) -> str:
    """
    모드별 user 템플릿을 로드해 질문을 감쌈.
    - 성공: prompts.yaml의 modes.<라벨>.user 에 플레이스홀더 삽입
    - 실패: 질문 원문(question) 반환
    기본 플레이스홀더:
      * {QUESTION}: 필수
      * 그 외 ctx의 키들: 예) EVIDENCE_CLASS_NOTES, EVIDENCE_GRAMMAR_BOOKS
    """
    label = _label_for(mode)
    data = load_prompts()
    try:
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            node = modes.get(label)
            if isinstance(node, dict):
                uv = node.get("user")
                if isinstance(uv, str) and uv.strip():
                    values: Dict[str, str] = {"QUESTION": question}
                    if isinstance(ctx, dict):
                        for k, v in ctx.items():
                            values[str(k)] = str(v)
                    return _fill_placeholders(uv, values).strip()
    except Exception:
        pass
    return question


# ----------------- evaluator 템플릿 로더 -----------------
def _eval_fallback_instructions(mode_label: str) -> str:
    """평가 지침 폴백 텍스트(모드별)."""
    if mode_label == "문장구조분석":
        return (
            "너는 '미나쌤' 평가자다. 공정하고 구체적으로, 간결하게 피드백한다.\n"
            "- 초점: 괄호 규칙 준수, 성분 식별 정확도, 일관성, 과잉 단정 금지\n"
            "- 출력 형식:\n"
            "  1) 한 줄 총평\n"
            "  2) 잘한 점 2가지\n"
            "  3) 보완점 2가지(왜/어떻게)\n"
            "  4) 결론: 등급(A/B/C) + 한 문장 이유"
        )
    if mode_label == "지문분석":
        return (
            "너는 '미나쌤' 평가자다. 핵심 보존과 평이화를 중시한다.\n"
            "- 초점: 요지 정확도, 구조 요약의 충실성, 핵심어 선정의 타당성\n"
            "- 출력 형식:\n"
            "  1) 한 줄 총평\n"
            "  2) 강점 2가지\n"
            "  3) 보완점 2가지\n"
            "  4) 결론: 등급(A/B/C) + 한 문장 이유"
        )
    # 문법설명
    return (
        "너는 '미나쌤' 평가자다. 이유문법을 우선 근거로 평가한다.\n"
        "- 초점: 규칙의 정확도, 근거 제시(이유문법/문법서), 설명의 간결성\n"
        "- 출력 형식:\n"
        "  1) 한 줄 총평\n"
        "  2) 강점 2가지\n"
        "  3) 보완점 2가지\n"
        "  4) 결론: 등급(A/B/C) + 한 문장 이유"
    )


def eval_instructions_for(mode: str) -> str:
    """
    평가자(system) 프롬프트를 로드.
    - 성공: prompts.yaml의 modes.<라벨>.eval
    - 실패: _eval_fallback_instructions()
    """
    label = _label_for(mode)
    data = load_prompts()
    try:
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            node = modes.get(label)
            if isinstance(node, dict):
                ev = node.get("eval")
                if isinstance(ev, str) and ev.strip():
                    return ev.strip()
    except Exception:
        pass
    return _eval_fallback_instructions(label)


def eval_user_prompt_for(
    mode: str,
    question: str,
    answer: str,
    ctx: Optional[Dict[str, str]] = None,
) -> str:
    """
    평가자(user) 템플릿을 로드해 '{QUESTION}/{ANSWER}/ctx'를 삽입.
    - 성공: prompts.yaml의 modes.<라벨>.eval_user
    - 실패: 기본 템플릿으로 폴백
    """
    label = _label_for(mode)
    data = load_prompts()

    tpl: Optional[str] = None
    try:
        modes = data.get("modes") if isinstance(data, dict) else None
        if isinstance(modes, dict):
            node = modes.get(label)
            if isinstance(node, dict):
                cand = node.get("eval_user")
                if isinstance(cand, str) and cand.strip():
                    tpl = cand.strip()
    except Exception:
        tpl = None

    if not tpl:
        # 코어 SSOT에서 평가 항목을 가져와 보조로 사용
        try:
            from src.core.modes import MODES  # lazy import (순환 방지)
            spec = MODES.get("sentence" if label == "문장구조분석" else
                             "passage" if label == "지문분석" else "grammar")
            focus = "·".join(spec.eval_focus) if spec and spec.eval_focus else ""
        except Exception:
            focus = ""

        tpl = (
            "[질문]\n{QUESTION}\n\n"
            "[피티쌤 답변]\n{ANSWER}\n\n"
            "[평가 지침]\n"
            f"- 평가 초점: {focus}\n"
            "- 출력 형식: 1) 한 줄 총평  2) 강점 2  3) 보완 2  4) 등급(A/B/C)+이유"
        )

    values: Dict[str, str] = {"QUESTION": question, "ANSWER": answer}
    if isinstance(ctx, dict):
        for k, v in ctx.items():
            values[str(k)] = str(v)
    return _fill_placeholders(tpl, values).strip()
# [32A] END: src/core/prompt_loader.py
