# [P4-01] START: src/modes/profiles.py (FULL REPLACEMENT)
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .types import Mode, ModeProfile

# Built-in safe defaults (SSOT 없을 때 사용)
_BUILTIN: Dict[Mode, ModeProfile] = {
    Mode.GRAMMAR: ModeProfile(
        id="grammar.v1",
        title="문법 설명 모드",
        objective="핵심 규칙과 예외를 단계적으로 설명",
        must_do=("용어는 풀어서 설명", "규칙→예시→반례→요약 순서"),
        must_avoid=("근거 없는 단정",),
        sections=("핵심 규칙", "예문", "자주 하는 실수", "간단 요약", "근거/출처"),
        extras={"mode_kr": "문법설명"},
    ),
    Mode.SENTENCE: ModeProfile(
        id="sentence.v1",
        title="문장 분석 모드",
        objective="문장 구조(S/V/O, 수식, 절·구문)를 시각적으로 분해",
        must_do=("역할 태깅(S/V/O/C/M)", "핵심 동사와 수식 관계를 단계별 설명"),
        must_avoid=("번역만 제시하고 구조 분석 누락",),
        sections=("원문", "구조 분석(괄호 규칙)", "어휘·표현", "해석", "요약", "근거/출처"),
        extras={
            "mode_kr": "문장분석",
            # ✅ 괄호 라벨 표준(프롬프트 및 validator에서 사용)
            "allowed_bracket_labels": [
                "S", "V", "O", "C", "M", "Sub", "Rel", "ToInf", "Ger", "Part", "Appo", "Conj"
            ],
        },
    ),
    Mode.PASSAGE: ModeProfile(
        id="passage.v1",
        title="지문 설명 모드",
        objective="주제·논지·문단 관계 파악과 핵심 문장 요약",
        must_do=("문단별 요지 도출", "핵심 문장 인용 후 의미 설명", "어휘·표현 주석"),
        must_avoid=("근거 없는 추정",),
        sections=("요지/주제", "문단별 핵심", "어휘·표현", "한줄 요약", "근거/출처"),
        extras={"mode_kr": "지문설명"},
    ),
}


def _try_load_yaml(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        import yaml  # optional dep
    except Exception:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_profile(mode: Mode, *, ssot_root: Optional[Path] = None) -> ModeProfile:
    """
    Returns a ModeProfile from SSOT(docs/_gpt) if present; otherwise built-in.
    SSOT candidates:
      - docs/_gpt/modes/{mode}.yaml
      - docs/_gpt/prompts.modes.yaml
    """
    root = ssot_root or Path("docs/_gpt")
    candidates = [
        root / "modes" / f"{mode.value}.yaml",
        root / "prompts.modes.yaml",
        root / "prompts.modes.yml",
    ]
    for p in candidates:
        data = _try_load_yaml(p)
        if not data:
            continue
        try:
            d = data.get("modes", {}).get(mode.value) if "modes" in data else data.get(mode.value)
            if not d:
                continue
            return ModeProfile(
                id=str(d.get("id", f"{mode.value}.ssot")),
                title=str(d.get("title", _BUILTIN[mode].title)),
                objective=str(d.get("objective", _BUILTIN[mode].objective)),
                must_do=tuple(d.get("must_do", _BUILTIN[mode].must_do) or ()),
                must_avoid=tuple(d.get("must_avoid", _BUILTIN[mode].must_avoid) or ()),
                tone=str(d.get("tone", _BUILTIN[mode].tone)),
                sections=tuple(d.get("sections", _BUILTIN[mode].sections) or ()),
                header_template=str(d.get("header_template", "{title} — {mode_kr}")),
                extras=dict(d.get("extras", _BUILTIN[mode].extras or {})),
            )
        except Exception:
            break
    return _BUILTIN[mode]
# [P4-01] END: src/modes/profiles.py
