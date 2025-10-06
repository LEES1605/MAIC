# [02] START: src/modes/__init__.py (FULL REPLACEMENT)
from __future__ import annotations

from .types import (
    Mode,
    ModeProfile,
    PromptBundle,
    ALLOWED_SOURCE_LABELS,
    sanitize_source_label,
    clamp_fragments,
)
from .profiles import get_profile
from .router import ModeRouter

__all__ = [
    "Mode",
    "ModeProfile",
    "PromptBundle",
    "ALLOWED_SOURCE_LABELS",
    "sanitize_source_label",
    "clamp_fragments",
    "get_profile",
    "ModeRouter",
]
# [02] END: src/modes/__init__.py (FULL REPLACEMENT)
