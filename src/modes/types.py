# [01] START: src/modes/types.py (NEW FILE)
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class Mode(str, Enum):
    """App-wide canonical modes. Keep names stable across UI/Services/LLM."""
    GRAMMAR = "grammar"    # 문법설명
    SENTENCE = "sentence"  # 문장분석
    PASSAGE = "passage"    # 지문설명

    @staticmethod
    def from_str(value: str) -> "Mode":
        if value is None:
            raise ValueError("mode value is required")
        v = value.strip().lower()
        if v in {"문법", "문법설명"}:
            return Mode.GRAMMAR
        if v in {"문장", "문장분석"}:
            return Mode.SENTENCE
        if v in {"지문", "지문설명"}:
            return Mode.PASSAGE
        try:
            return Mode(v)
        except ValueError as e:
            raise ValueError(f"Unsupported mode: {value!r}") from e


ALLOWED_SOURCE_LABELS: Dict[str, str] = {
    "[이유문법]": "Reason-based grammar materials",
    "[문법서적]": "Printed/official grammar books",
    "[AI지식]": "Model-only fallback (no attached index)",
}


@dataclass(frozen=True)
class ModeProfile:
    """Stable prompt contract per mode (default or SSOT-loaded)."""
    id: str
    title: str
    objective: str
    must_do: Sequence[str] = field(default_factory=tuple)
    must_avoid: Sequence[str] = field(default_factory=tuple)
    tone: str = "친절하고 명확하며 단계적인 설명"
    sections: Sequence[str] = field(default_factory=tuple)
    header_template: str = "{title} — {mode_kr}"
    extras: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptBundle:
    """Result of routing+rendering before LLM call."""
    mode: Mode
    profile: ModeProfile
    source_label: str
    prompt: str
    sections: Sequence[str] = field(default_factory=tuple)
    context_fragments: Sequence[str] = field(default_factory=tuple)


def sanitize_source_label(label: Optional[str]) -> str:
    if not label:
        return "[AI지식]"
    l = label.strip()
    return l if l in ALLOWED_SOURCE_LABELS else "[AI지식]"


def clamp_fragments(
    frags: Optional[Sequence[str]],
    *,
    max_items: int = 5,
    max_chars_each: int = 500,
) -> List[str]:
    if not frags:
        return []
    safe: List[str] = []
    for s in list(frags)[:max_items]:
        s = (s or "").strip()
        if max_chars_each > 0 and len(s) > max_chars_each:
            s = s[: max_chars_each] + "…"
        safe.append(s)
    return safe
# [01] END: src/modes/types.py
