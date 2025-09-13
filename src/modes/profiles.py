# [P1] START: src/modes/profiles.py (FULL REPLACEMENT)
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .types import Mode, ModeProfile

# Built-in safe defaults (SSOT 부재 시 사용)
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
        extras={"mode_kr": "문장분석"},
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
    """YAML 파일을 안전하게 읽어 dict로 반환(실패 시 None)."""
    if not path.exists():
        return None
    try:
        import yaml  # optional dependency
    except Exception:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_profile(mode: Mode, *, ssot_root: Optional[Path] = None) -> ModeProfile:
    """
    SSOT(docs/_gpt)에서 프로필을 로드하고, 없으면 내장 기본값을 반환한다.

    SSOT 후보(우선순위):
      1) docs/_gpt/modes/{mode}.yaml
      2) docs/_gpt/prompts.modes.yaml (또는 .yml)
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
            # 두 가지 포맷 지원:
            #  (a) { "modes": { "<mode>": {...} } }
            #  (b) { "<mode>": {...} }
            outer = data.get("modes")
            d = (
                outer.get(mode.value)
                if isinstance(outer, dict)
                else data.get(mode.value)
            )
            if not d:
                continue
            return ModeProfile(
                id=str(d.get("id", f"{mode.value}.ssot")),
                title=str(d.get("title", _BUILTIN[mode].title)),
                objective=str(d.get("objective", _BUILTIN[mode].objective)),
                must_do=tuple(d.get("must_do", _BUILTIN[mode].must_do) or ()),
                must_avoid=tuple(
                    d.get("must_avoid", _BUILTIN[mode].must_avoid) or ()
                ),
                tone=str(d.get("tone", _BUILTIN[mode].tone)),
                sections=tuple(
                    d.get("sections", _BUILTIN[mode].sections) or ()
                ),
                header_template=str(
                    d.get("header_template", "{title} — {mode_kr}")
                ),
                extras=dict(d.get("extras", {})),
            )
        except Exception:
            # 이 후보가 깨져 있으면 다음 후보를 계속 시도한다.
            continue
    return _BUILTIN[mode]
# [P1] END: src/modes/profiles.py
