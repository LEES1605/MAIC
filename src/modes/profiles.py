# [02] START: src/modes/profiles.py

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from .types import Mode, ModeProfile


# ----------------------------- Fallback canonical schema -----------------------------
# SSOT(_canon.yaml)이 없거나 파싱 실패 시 사용할 "내장 표준"
_FALLBACK_ORDER: Dict[Mode, Tuple[str, ...]] = {
    Mode.GRAMMAR: ("핵심 규칙", "근거/출처", "예문", "역예문(선택)", "한 줄 요약"),
    Mode.SENTENCE: ("원문", "구조 분석(괄호 규칙)", "어휘·표현", "해석", "요약", "근거/출처"),
    Mode.PASSAGE: ("요지/주제", "쉬운 예시/비유", "제목", "오답 포인트(선택)", "근거/출처"),
}
_FALLBACK_REQUIRED: Dict[Mode, Tuple[str, ...]] = {
    Mode.GRAMMAR: ("근거/출처",),
    Mode.SENTENCE: ("근거/출처",),
    Mode.PASSAGE: ("근거/출처",),
}
_FALLBACK_SYNONYMS: Dict[str, str] = {
    # Grammar
    "핵심규칙": "핵심 규칙",
    "근거(국어↔영어)": "근거/출처",
    "근거 (국어↔영어)": "근거/출처",
    "근거": "근거/출처",
    "출처": "근거/출처",
    # Passage
    "핵심 요지": "요지/주제",
    "요지": "요지/주제",
}


# ----------------------------- Built-in safe defaults (profiles) -----------------------------
_BUILTIN: Dict[Mode, ModeProfile] = {
    Mode.GRAMMAR: ModeProfile(
        id="grammar.v1",
        title="문법 설명 모드",
        objective="핵심 규칙과 예외를 단계적으로 설명",
        must_do=("용어는 풀어서 설명", "규칙→예시→반례→요약 순서"),
        must_avoid=("근거 없는 단정",),
        tone="친절하고 명확하며 단계적인 설명",
        sections=("핵심 규칙", "근거/출처", "예문", "역예문(선택)", "한 줄 요약"),
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
        sections=("요지/주제", "쉬운 예시/비유", "제목", "오답 포인트(선택)", "근거/출처"),
        header_template="{title} — {mode_kr}",
        extras={"mode_kr": "지문설명"},
    ),
}

# ----------------------------- SSOT loaders -----------------------------
def _safe_load_yaml(path: Path) -> Optional[dict]:
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


@lru_cache(maxsize=1)
def _load_canon(root_str: str) -> dict:
    """
    SSOT _canon.yaml 로딩(1회 캐시).
    반환 스키마:
    {
      "order": {mode_str: [..]},
      "required": {mode_str: [..]},
      "synonyms": {from: to}
    }
    """
    root = Path(root_str)
    data = _safe_load_yaml(root / "modes" / "_canon.yaml") or {}
    modes = data.get("modes") or {}
    syns = data.get("synonyms") or {}

    def _mode_key(m: Mode) -> str:
        return m.value if hasattr(m, "value") else str(m)

    order = {}
    required = {}
    for m in (Mode.GRAMMAR, Mode.SENTENCE, Mode.PASSAGE):
        key = _mode_key(m)
        mconf = modes.get(key) or {}
        order[key] = tuple(map(str, (mconf.get("order") or ())))
        required[key] = tuple(map(str, (mconf.get("required") or ())))

    return {
        "order": order,
        "required": {k: tuple(v) for k, v in required.items()},
        "synonyms": {str(k): str(v) for k, v in (syns.items() if isinstance(syns, dict) else {})},
    }


def _canon_sections(
    mode: Mode,
    sections: Iterable[str],
    *,
    root: Path,
) -> Tuple[str, ...]:
    """
    동의어를 표준명으로 치환하고, 필수 섹션 보강 + 표준 순서로 정렬.
    설정파일(_canon.yaml)을 우선 사용하고, 부재 시 내장 표준으로 폴백합니다.
    """
    conf = _load_canon(str(root))
    syn = conf.get("synonyms") or _FALLBACK_SYNONYMS
    order_map = conf.get("order") or {}
    req_map = conf.get("required") or {}

    mode_key = mode.value if hasattr(mode, "value") else str(mode)
    want_order = tuple(order_map.get(mode_key) or _FALLBACK_ORDER.get(mode, ()))
    must_have = set(req_map.get(mode_key) or _FALLBACK_REQUIRED.get(mode, ()))

    # 1) 동의어 치환 + strip
    mapped: list[str] = []
    for s in sections or ():
        s2 = (s or "").strip()
        mapped.append(syn.get(s2, s2))

    # 2) 필수 섹션 보강
    for req in must_have:
        if req not in mapped:
            mapped.append(req)

    # 3) 표준 순서 정렬 + 중복 제거
    seen: set[str] = set()
    result: list[str] = []
    if want_order:
        for name in want_order:
            if name in mapped and name not in seen:
                result.append(name)
                seen.add(name)
        for name in mapped:
            if name not in seen:
                result.append(name)
                seen.add(name)
    else:
        for name in mapped:
            if name not in seen:
                result.append(name)
                seen.add(name)
    return tuple(result)


# ----------------------------- Public API -----------------------------
def get_profile(mode: Mode, *, ssot_root: Optional[Path] = None) -> ModeProfile:
    """
    Returns a ModeProfile from SSOT(docs/_gpt) if present; otherwise built-in.

    SSOT candidates:
      - docs/_gpt/modes/{mode}.yaml
      - docs/_gpt/prompts.modes.yaml (or .yml)
      - docs/_gpt/modes/_canon.yaml (정규화 규칙)
    """
    root = ssot_root or Path("docs/_gpt")

    # 1) SSOT 템플릿 로딩(선택)
    candidates = [
        root / "modes" / f"{mode.value}.yaml",
        root / "prompts.modes.yaml",
        root / "prompts.modes.yml",
    ]
    for p in candidates:
        data = _safe_load_yaml(p)
        if not data:
            continue
        d = data.get("modes", {}).get(mode.value) if "modes" in data else data.get(mode.value)
        if not isinstance(d, dict):
            continue

        # extras 병합 (+ rules 상향)
        base_extras = dict(_BUILTIN[mode].extras or {})
        yaml_extras = dict(d.get("extras") or {})
        if "rules" in d and d["rules"] is not None:
            yaml_extras["rules"] = str(d["rules"])
        extras = {**base_extras, **yaml_extras}

        # 섹션 정규화
        raw_sections = tuple(d.get("sections", _BUILTIN[mode].sections) or ())
        norm_sections = _canon_sections(mode, raw_sections, root=root)
        try:
            return ModeProfile(
                id=str(d.get("id", _BUILTIN[mode].id)),
                title=str(d.get("title", _BUILTIN[mode].title)),
                objective=str(d.get("objective", _BUILTIN[mode].objective)),
                must_do=tuple(d.get("must_do", _BUILTIN[mode].must_do) or ()),
                must_avoid=tuple(d.get("must_avoid", _BUILTIN[mode].must_avoid) or ()),
                tone=str(d.get("tone", _BUILTIN[mode].tone)),
                sections=norm_sections,
                header_template=str(d.get("header_template", _BUILTIN[mode].header_template)),
                extras=extras,
            )
        except Exception:
            break

    # 2) 폴백: 내장 프로필 + 정규화 적용
    b = _BUILTIN[mode]
    return ModeProfile(
        id=b.id,
        title=b.title,
        objective=b.objective,
        must_do=b.must_do,
        must_avoid=b.must_avoid,
        tone=b.tone,
        sections=_canon_sections(mode, b.sections, root=root),
        header_template=b.header_template,
        extras=b.extras,
    )
# [02] END: src/modes/profiles.py