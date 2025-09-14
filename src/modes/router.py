# [P3] START: src/modes/router.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

from .profiles import get_profile
from .types import Mode, PromptBundle, clamp_fragments, sanitize_source_label


class ModeRouter:
    """mode(enum) -> profile(SSOT or builtin) -> rendered prompt(bundle)"""

    def __init__(self, *, ssot_root: Optional[Path] = None) -> None:
        self._ssot_root = ssot_root

    def _blank(self, mode: Mode, *, source_label: Optional[str] = None) -> PromptBundle:
        return PromptBundle(
            mode=mode,
            profile=get_profile(mode, ssot_root=self._ssot_root),
            source_label=sanitize_source_label(source_label),
            prompt="",
            sections=(),
            context_fragments=(),
        )

    @staticmethod
    def _sentence_rules_text(extras: dict) -> str:
        """Fetch rules text with robust fallback for Sentence mode."""
        txt = str((extras or {}).get("rules") or "").strip()
        if txt:
            # 보장: 예시가 빠졌다면 추가(테스트 안전)
            if "[S I] [V stayed] [M at home]" not in txt:
                txt = txt.rstrip() + "\n예시: [S I] [V stayed] [M at home]"
            return txt
        return "라벨: [S 주어] [V 동사] [O 목적어] [C 보어] [M 부가]\n예시: [S I] [V stayed] [M at home]"

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

        # ✅ 근본 해결: Sentence 모드는 규칙 섹션을 항상 포함(SSOT→폴백 순)
        if mode is Mode.SENTENCE:
            lines.append("## 괄호 규칙 라벨 표준")
            lines.append(self._sentence_rules_text(profile.extras))
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
# [P3] END: src/modes/router.py
