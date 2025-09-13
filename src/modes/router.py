# [P4-02] START: src/modes/router.py (FULL REPLACEMENT)
from __future__ import annotations

from dataclasses import asdict
from typing import Optional, Sequence

from .profiles import get_profile
from .types import Mode, PromptBundle, clamp_fragments, sanitize_source_label


class ModeRouter:
    """mode(enum) -> profile(SSOT or builtin) -> rendered prompt(bundle)"""

    def __init__(self, *, ssot_root: Optional[str] = None) -> None:
        self._ssot_root = None if ssot_root is None else ssot_root  # path-like tolerated

    def select_profile(self, mode: Mode) -> PromptBundle:
        profile = get_profile(mode, ssot_root=self._ssot_root)
        return PromptBundle(
            mode=mode,
            profile=profile,
            source_label="[AI지식]",
            prompt="",
            sections=profile.sections,
            context_fragments=(),
        )

    def render_prompt(
        self,
        *,
        mode: Mode,
        question: str,
        context_fragments: Optional[Sequence[str]] = None,
        source_label: Optional[str] = None,
    ) -> PromptBundle:
        profile = get_profile(mode, ssot_root=self._ssot_root)
        label = sanitize_source_label(source_label)
        frags = clamp_fragments(context_fragments, max_items=5, max_chars_each=500)

        header = profile.header_template.format(
            title=profile.title,
            mode_kr=profile.extras.get("mode_kr", mode.value),
        )

        lines: list[str] = []
        lines.append(f"# {header}")
        lines.append("")
        lines.append(f"**모드**: {mode.value}  |  **라벨**: {label}")
        lines.append("")
        lines.append("## 질의")
        lines.append(question.strip())
        lines.append("")

        if frags:
            lines.append("## 자료 컨텍스트 (최대 5개)")
            for i, s in enumerate(frags, 1):
                lines.append(f"- ({i}) {s}")
            lines.append("")

        lines.append("## 의도/목표")
        lines.append(profile.objective)
        lines.append("")

        if profile.must_do:
            lines.append("## 반드시 할 일")
            for item in profile.must_do:
                lines.append(f"- {item}")
            lines.append("")
        if profile.must_avoid:
            lines.append("## 피할 것")
            for item in profile.must_avoid:
                lines.append(f"- {item}")
            lines.append("")

        # ✅ Sentence 모드면 괄호 라벨 표준을 명시적으로 제공
        if mode is Mode.SENTENCE:
            labels = tuple(profile.extras.get("allowed_bracket_labels", ()))
            if labels:
                lines.append("## 괄호 규칙 라벨 표준")
                lines.append("라벨: " + ", ".join(labels))
                lines.append("예시: [S I] [V stayed] [M at home]")
                lines.append("")

        if profile.sections:
            lines.append("## 출력 스키마(섹션 순서 고정)")
            for i, sec in enumerate(profile.sections, 1):
                lines.append(f"{i}. {sec}")
            lines.append("")

        lines.append("> 위 스키마를 **순서대로** 준수하고, 각 섹션은 간결한 소제목으로 시작하세요.")
        prompt = "\n".join(lines).strip()

        return PromptBundle(
            mode=mode,
            profile=profile,
            source_label=label,
            prompt=prompt,
            sections=profile.sections,
            context_fragments=tuple(frags),
        )

    def debug_dict(self, bundle: PromptBundle) -> dict:
        return {
            "mode": bundle.mode.value,
            "source_label": bundle.source_label,
            "sections": list(bundle.sections),
            "context_count": len(bundle.context_fragments),
            "profile": asdict(bundle.profile),
        }
# [P4-02] END: src/modes/router.py
