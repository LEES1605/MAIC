# src/prompting/types.py

from dataclasses import dataclass
from typing import Literal

Source = Literal["GitHub", "Drive", "Fallback"]

@dataclass
class PromptParts:
    system: str
    user: str
    source: Source
