# [01] START: src/modes/profiles.py (NEW FILE)
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .types import Mode, ModeProfile

# --- Built-in safe defaults (used if SSOT files are unavailable) ---
# These are intentionally concise; A2에서 SSOT 템플릿을 강제하도록 확장합니다.
_BUILTIN: Dict[Mode, ModeProfile] = {
    Mode.GRAMMAR: ModeProfile(
        id="grammar.v1",
        title="문법 설명 모드",
        objective="중학생도 이해할 수 있게 핵심 규칙과 예외를 단계적으로 설명",
        must_do=(
            "용어는 풀어서 말하고, 규칙→예시→반례→요약 순서를 지킬 것",
            "필요 시 한국어/영어 대비표로 오해 포인트를 정리",
        ),
        must_avoid=("과도한 이론 전개", "근거 없는 단정"),
        sections=("핵심 규칙", "예문", "자주 하는 실수", "간단 요약"),
        extras={"mode_kr": "문법설명"},
    ),
    Mode.SENTENCE: ModeProfile(
        id="sentence.v1",
        title="문장 분석 모드",
        objective="문장 구조(S/V/O, 수식어, 절·구문)를 시각적으로 분해해 이해를 돕기",
        must_do=(
            "역할 태깅(S/V/O/C/M)으로 구조를 명시",
            "핵심 동사와 수식 관계를 단계별로 설명",
        ),
        must_avoid=("문장 전체를 번역으로 대체", "형식만 유지하고 내용이 빈약함"),
        sections=("원문", "구조 분석", "핵심 포인트", "자주 헷갈리는 부분"),
        extras={"mode_kr": "문장분석"},
    ),
    Mode.PASSAGE: ModeProfile(
        id="passage.v1",
        title="지문 설명 모드",
        objective="지문의 주제·논지·문단 관계를 파악하고 핵심 문장을 뽑아 요약",
        must_do=("문단별 요지 도출", "핵심 문장 인용 후 의미 설명", "어휘/관용표현 주석"),
        must_avoid=("지나친 해석 주입", "근거 없는 주장"),
        sections=("요지/주제", "문단별 핵심", "어휘·표현", "한줄 요약"),
        extras={"mode_kr": "지문설명"},
    ),
}


def _try_load_yaml(path: Path) -> Optional[dict]:
    """Best-effort YAML loader. Avoids hard dependency on PyYAML."""
    if not path.exists():
        return None
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)  # type: ignore
    except Exception:
        return None


def get_profile(mode: Mode, *, ssot_root: Optional[Path] = None) -> ModeProfile:
    """
    Returns a ModeProfile. If SSOT templates exist under docs/_gpt/, prefer them.
    Expected SSOT candidates (to be formalized in PR-A2):
      - docs/_gpt/modes/{mode}.yaml
      - docs/_gpt/prompts.modes.yaml
    """
    # 1) Attempt SSOT files (optional)
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
        # Flexible schema: either full dict by mode, or a single-file profile
        try:
            if "modes" in data:
                d = data["modes"].get(mode.value)
            else:
                d = data.get(mode.value) if isinstance(data, dict) else None
            if not d:
                continue
            # Minimal mapping; unknown keys go to extras
            return ModeProfile(
                id=str(d.get("id", f"{mode.value}.ssot")),
                title=str(d.get("title", _BUILTIN[mode].title)),
                objective=str(d.get("objective", _BUILTIN[mode].objective)),
                must_do=tuple(d.get("must_do", _BUILTIN[mode].must_do) or ()),
                must_avoid=tuple(d.get("must_avoid", _BUILTIN[mode].must_avoid) or ()),
                tone=str(d.get("tone", _BUILTIN[mode].tone)),
                sections=tuple(d.get("sections", _BUILTIN[mode].sections) or ()),
                header_template=str(
                    d.get("header_template", "{title} — {mode_kr}")
                ),
                extras=dict(d.get("extras", {})),
            )
        except Exception:
            # Fall back to builtin if malformed
            break

    # 2) Built-in safe default
    return _BUILTIN[mode]
# [01] END: src/modes/profiles.py
