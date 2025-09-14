# [05] START: tools/print_profiles.py
from __future__ import annotations

from pathlib import Path

from src.modes.profiles import get_profile
from src.modes.types import Mode


def main() -> None:
    root = Path("docs/_gpt")
    for m in (Mode.GRAMMAR, Mode.SENTENCE, Mode.PASSAGE):
        prof = get_profile(m, ssot_root=root)
        print(f"[{m.value}] {prof.title}")
        print(" sections:")
        for i, s in enumerate(prof.sections, 1):
            print(f"  {i}. {s}")
        obj = (prof.objective or "").strip()
        if len(obj) > 100:
            obj = obj[:100] + " ..."
        print(" objective:", obj)
        print("-" * 40)


if __name__ == "__main__":
    main()
# [05] END: tools/print_profiles.py
