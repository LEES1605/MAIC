# [R1] START: src/modes/router.py (FULL REPLACEMENT)
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .profiles import get_profile
from .types import Mode, PromptBundle, clamp_fragments, sanitize_source_label


class ModeRouter:
    """mode(enum) -> profile(SSOT or builtin) -> rendered prompt(bundle)."""

    def __init__(self, *, ssot_root: Optional[Path] = None) -> None:
        self._ssot_root = ssot_root

    def select_profile(self, mode: Mode) -> PromptBundle:
        """SSOT 또는 내장 프로필을 선택만 한 빈 번들을 반환."""
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
        """질문/컨텍스트/프로필을 조합해 LLM 프롬프트 번들을 생성."""
        profile = get_profile(mode, ssot_root=self._ssot_root)
        label = sanitize_source_label(source_label)
        frags = clamp_fragments(context_fragments, max_items=5, max_chars_each=500)

        header = profile.header_template.format(
            title=profile.title,
            mode_kr=profile.extras.get("mode_kr", mode.value),
        )

        lines: List[str] = []
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

        if profile.sections:
            lines.append("## 출력 스키마(섹션 순서 고정)")
            for i, sec in enumerate(profile.sections, 1):
                lines.append(f"{i}. {sec}")
            lines.append("")

        lines.append(
            "> 위 스키마를 **순서대로** 준수하고, "
            "각 섹션은 간결한 소제목으로 시작하세요."
        )
        prompt = "\n".join(lines).strip()

        return PromptBundle(
            mode=mode,
            profile=profile,
            source_label=label,
            prompt=prompt,
            sections=profile.sections,
            context_fragments=tuple(frags),
        )

    def debug_dict(self, bundle: PromptBundle) -> Dict[str, Any]:
        """프롬프트 번들을 디버그/테스트 친화 JSON으로 직렬화."""
        return {
            "mode": bundle.mode.value,
            "source_label": bundle.source_label,
            "sections": list(bundle.sections),
            "context_count": len(bundle.context_fragments),
            "profile": asdict(bundle.profile),
        }
# [R1] END: src/modes/router.py
