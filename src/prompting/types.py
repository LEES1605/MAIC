# [P01] START: src/prompting/types.py (FULL REPLACEMENT)
from __future__ import annotations
# Compatibility shim to avoid confusion with modes.types.
# Prefer importing from 'src.prompting.prompt_parts' going forward.

from dataclasses import dataclass
from typing import Literal

Source = Literal["GitHub", "Drive", "Fallback"]

@dataclass
class PromptParts:
    system: str
    user: str
    source: Source

__all__ = ["PromptParts", "Source"]
# [P01] END
