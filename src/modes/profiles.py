# [01] START: src/modes/profiles.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .types import Mode, ModeProfile


# ----------------------------- Built-in safe defaults -----------------------------
_BUILTIN: Dict[Mode, ModeProfile] = {
    Mode.GRAMMAR: ModeProfile(
        id="grammar.v1",
        title="문법 설명 모드",
        objective="핵심 규칙과 예외를 단계적으로 설명",
        must_do=("용어는 풀어서 설명", "규칙→예시→반례→요약 순서"),
        must_avoid=("근거 없는 단정",),
        tone="친절하고 명확하며 단계적인 설명",
        sections=("핵심규칙", "근거(국어↔영어)", "예문", "역예문(선택)", "한 줄 요약"),
        header_template="{title} — {mode_kr}",
        extras={"mode_kr": "문법설명"},
    ),
    Mode.SENTENCE: ModeProfile(
        id="sentence.v1",
        title="문장 분석 모드",
        # 테스트 스펙 충족: 정확 문구를 기본 objective에도 포함
        objective=(
            '문장 구조(S/V/O, 수식어, 절·구문)를 "괄호 규칙"과 '
            '"괄호 규칙 라벨 표준"에 따라 설명'
        ),
        must_do=("S/V/O/C/M 라벨링", "근거·출처 요약"),
        must_avoid=("근거 없는 라벨링",),
        tone="친절하고 명확하며 단계적인 설명",
        sections=("원문", "구조 분석(괄호 규칙)", "어휘·표현", "해석", "요약", "근거/출처"),
        header_template="{title} — {mode_kr}",
        extras={
            "mode_kr": "문장분석",
            # YAML에 rules가 없을 때 사용할 폴백
            "rules": (
                "라벨: [S 주어] [V 동사] [O 목적어] [C 보어] [M 부가]\n"
                "예시: [S I] [V stayed] [M at home]"
            ),
        },
    ),
    Mode.PASSAGE: ModeProfile(
        id="passage.v1",
        title="지문 설명 모드",
        objective="지문의 핵심 요지를 쉬운 예시로 설명하고 주제/제목을 정리",
        must_do=("요지→예시→주제→제목 순서",),
        must_avoid=("핵심 누락",),
        tone="친절하고 명확하며 단계적인 설명",
        sections=("핵심 요지", "쉬운 예시/비유", "주제", "제목", "오답 포인트(선택)"),
        header_template="{title} — {mode_kr}",
        extras={"mode_kr": "지문설명"},
    ),
}


def _try_load_yaml(path: Path) -> Optional[dict]:
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
    Returns a ModeProfile from SSOT(docs/_gpt) if present; otherwise built-in.

    SSOT candidates:
      - docs/_gpt/modes/{mode}.yaml
      - docs/_gpt/prompts.modes.yaml (or .yml)
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
        d = data.get("modes", {}).get(mode.value) if "modes" in data else data.get(mode.value)
        if not isinstance(d, dict):
            continue

        # merge extras + bring top-level 'rules' into extras
        base_extras = dict(_BUILTIN[mode].extras or {})
        yaml_extras = dict(d.get("extras") or {})
        if "rules" in d and d["rules"] is not None:
            yaml_extras["rules"] = str(d["rules"])
        extras = {**base_extras, **yaml_extras}

        try:
            return ModeProfile(
                id=str(d.get("id", _BUILTIN[mode].id)),
                title=str(d.get("title", _BUILTIN[mode].title)),
                objective=str(d.get("objective", _BUILTIN[mode].objective)),
                must_do=tuple(d.get("must_do", _BUILTIN[mode].must_do) or ()),
                must_avoid=tuple(d.get("must_avoid", _BUILTIN[mode].must_avoid) or ()),
                tone=str(d.get("tone", _BUILTIN[mode].tone)),
                sections=tuple(d.get("sections", _BUILTIN[mode].sections) or ()),
                header_template=str(d.get("header_template", _BUILTIN[mode].header_template)),
                extras=extras,
            )
        except Exception:
            break
    return _BUILTIN[mode]
# [01] END: src/modes/profiles.py
