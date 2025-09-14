# [07] START: tools/generate_mode_docs.py
# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

# --- Make project modules importable in CI/script contexts -------------------
ROOT = Path(__file__).resolve().parent.parent  # <repo-root>
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from src.modes.profiles import get_profile
    from src.modes.types import Mode
except Exception as e:  # pragma: no cover
    raise RuntimeError(f"Failed to import project modules from ROOT={ROOT}: {e}") from e

OUT = Path("docs/_gpt/_generated/MODES.md")


def _render_mode(mode: Mode) -> str:
    p = get_profile(mode)
    lines: list[str] = []
    lines.append(f"## {p.title} ({mode.value})")
    lines.append("")
    lines.append("### 의도/목표")
    lines.append(p.objective)
    lines.append("")

    # 규칙(문장 모드 등 extras.rules가 있을 때)
    rules = (p.extras or {}).get("rules") if hasattr(p, "extras") else None
    if rules:
        lines.append("### 규칙(해당 시)")
        lines.append(str(rules).strip())
        lines.append("")

    lines.append("### 섹션 순서")
    for i, s in enumerate(p.sections, 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    return "\n".join(lines).strip()


def main() -> int:
    out_dir = OUT.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = ["# MAIC 모드 가이드 (자동 생성)", ""]
    for m in (Mode.GRAMMAR, Mode.SENTENCE, Mode.PASSAGE):
        parts.append(_render_mode(m))
        parts.append("")

    OUT.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
    print(f"[generate_mode_docs] wrote: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [07] END: tools/generate_mode_docs.py
