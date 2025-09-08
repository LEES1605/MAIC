# ===================== [01] module docstring — START =====================
"""
Label constants & normalization (SSOT).

- 표준 라벨: [문법책], [이유문법], [AI지식]
- 별칭은 canon_label()로 항상 표준 라벨로 정규화한다.
"""
# ===================== [01] module docstring — END =======================

# ========================= [02] imports & consts — START =================
from __future__ import annotations

from typing import Final

__all__ = ["BOOK_LABEL", "REASON_LABEL", "AI_LABEL", "canon_label"]

BOOK_LABEL: Final = "[문법책]"
REASON_LABEL: Final = "[이유문법]"
AI_LABEL: Final = "[AI지식]"

# 과거/외부 표기 alias → 표준 라벨
_ALIASES: dict[str, str] = {
    "[문법서적]": BOOK_LABEL,
    "[문법책]": BOOK_LABEL,
    "[이유문법]": REASON_LABEL,
    "[AI지식]": AI_LABEL,
}
# ========================= [02] imports & consts — END ===================


# ======================== [03] public: canon_label — START ===============
def canon_label(label: str | None) -> str:
    """
    들어온 라벨을 표준 라벨로 정규화한다.
    None/공백 → [AI지식] 폴백.
    """
    s = (label or "").strip()
    if not s:
        return AI_LABEL
    return _ALIASES.get(s, s)
# ======================== [03] public: canon_label — END =================
