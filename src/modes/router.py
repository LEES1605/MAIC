# [01] START: src/modes/router.py (NEW FILE)
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

from .profiles import get_profile
from .types import Mode, PromptBundle, clamp_fragments, sanitize_source_label


class ModeRouter:
    """
    Single entry for:
      mode(enum) -> profile(SSOT or builtin) -> rendered prompt(bundle)
    This keeps UI/Services thin and testable.
    """

    def __init__(self, *, ssot_root: Optional[Path] = None) -> None:
        self._ssot_root = ssot_root

    # ---- Public API -----------------------------------------------------
    def select_profile(self, mode: Mode) -> PromptBundle:
        """
        Return an 'empty' bundle carrying the selected profile.
        Prompt text is not built in this step.
        """
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
        """
        Build a mode-consistent prompt. This method does NOT call any LLM.
        Security/robustness:
          - clamps number/length of context fragments
          - guards/normalizes source label
          - produces deterministic section headers for snapshot testing
        """
        profile = get_profile(mode, ssot_root=self._ssot_root)
        label = sanitize_source_label(source_label)
        frags = clamp_fragments(context_fragments, max_items=5, max_chars_each=500)

        header = profile.header_template.format(
            title=profile.title,
            mode_kr=profile.extras.get("mode_kr", mode.value),
        )

        # Deterministic, mode-stable structure (helps snapshot tests)
        lines = []
        lines.append(f"# {header}")
        lines.append("")
        lines.append(f"**모드**: {mode.value}  |  **라벨**: {label}")
        lines.append("")
        lines.append("## 질의")
        lines.append(question.strip())
        lines.append("")

        if frags:
            lines.append("## 자료 컨텍스트 (최대 5개, 일부 생략 가능)")
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

        if profile.sections:
            lines.append("## 출력 스키마(섹션 순서 고정)")
            for i, sec in enumerate(profile.sections, 1):
                lines.append(f"{i}. {sec}")
            lines.append("")

        # Implementation hint to downstream:
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

    # ---- Introspection (useful for logging/QA) -------------------------
    def debug_dict(self, bundle: PromptBundle) -> dict:
        return {
            "mode": bundle.mode.value,
            "source_label": bundle.source_label,
            "sections": list(bundle.sections),
            "context_count": len(bundle.context_fragments),
            "profile": asdict(bundle.profile),
        }
# [01] END: src/modes/router.py
