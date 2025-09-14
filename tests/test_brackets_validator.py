# [P4-05] START: tests/test_brackets_validator.py (NEW)
from __future__ import annotations

from src.validation.brackets import validate_bracket_analysis


def test_validator_ok() -> None:
    text = "[S I] [V stayed] [M at home]"
    rep = validate_bracket_analysis(text)
    assert rep.ok
    assert rep.counts.get("S", 0) >= 1
    assert rep.counts.get("V", 0) >= 1
    assert rep.groups >= 3


def test_validator_unknown_label() -> None:
    text = "[X foo] [S I] [V go]"
    rep = validate_bracket_analysis(text)
    assert not rep.ok
    assert any("unknown-label" in e for e in rep.errors)


def test_validator_unbalanced() -> None:
    text = "[S I [V go]"
    rep = validate_bracket_analysis(text)
    assert not rep.ok
    assert any("bracket-unbalanced" in e for e in rep.errors)
# [P4-05] END: tests/test_brackets_validator.py
