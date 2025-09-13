# [P4-03] START: src/validation/brackets.py (NEW)
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple

_DEFAULT_LABELS: Set[str] = {
    "S", "V", "O", "C", "M", "Sub", "Rel", "ToInf", "Ger", "Part", "Appo", "Conj"
}

_BRACKET_RE = re.compile(r"\[(?P<label>[A-Za-z]+)\s+.+?\]")

@dataclass(frozen=True)
class BracketReport:
    ok: bool
    errors: Tuple[str, ...]
    counts: Dict[str, int]
    groups: int

def _count_brackets(text: str) -> Tuple[int, int]:
    return text.count("["), text.count("]")

def validate_bracket_analysis(
    text: str,
    *,
    allowed_labels: Iterable[str] | None = None,
    require_sv: bool = True,
) -> BracketReport:
    """
    괄호규칙 점검(경량):
      - 대괄호 수 균형
      - 라벨이 허용 목록 내인지
      - (선택) S/V 최소 1개씩 존재
    """
    labels = set(allowed_labels or _DEFAULT_LABELS)
    left, right = _count_brackets(text or "")
    errors: List[str] = []
    if left != right:
        errors.append(f"bracket-unbalanced: left={left}, right={right}")

    counts: Dict[str, int] = {}
    groups = 0
    for m in _BRACKET_RE.finditer(text or ""):
        groups += 1
        lab = m.group("label")
        counts[lab] = counts.get(lab, 0) + 1
        if lab not in labels:
            errors.append(f"unknown-label: {lab}")

    if require_sv:
        if counts.get("S", 0) < 1:
            errors.append("missing-label: S")
        if counts.get("V", 0) < 1:
            errors.append("missing-label: V")

    return BracketReport(
        ok=(len(errors) == 0),
        errors=tuple(errors),
        counts=counts,
        groups=groups,
    )
# [P4-03] END: src/validation/brackets.py
