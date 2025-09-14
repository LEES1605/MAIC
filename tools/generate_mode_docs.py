# [07] START: tools/generate_mode_docs.py
from __future__ import annotations

from pathlib import Path

from src.modes.profiles import get_profile
from src.modes.types import Mode


OUT = Path("docs/_gpt/_generated/MODES.md")


def _render_mode(mode: Mode) -> str:
    p = get_profile(mode)
    lines = []
    lines.append(f"## {p.title} ({mode.value})")
    lines.append("")
    lines.append("### 의도/목표")
    lines.append(p.objective)
    lines.append("")
    lines.append("### 섹션 순서")
    for i, s in enumerate(p.sections, 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    md = "\n".join(lines).strip()
    return md


def main() -> int:
    out_dir = OUT.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = []
    parts.append("# MAIC 모드 가이드 (자동 생성)")
    parts.append("")
    for m in (Mode.GRAMMAR, Mode.SENTENCE, Mode.PASSAGE):
        parts.append(_render_mode(m))
        parts.append("")

    OUT.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
    print(f"[generate_mode_docs] wrote: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [07] END: tools/generate_mode_docs.py
