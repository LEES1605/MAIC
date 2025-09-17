from __future__ import annotations

import pytest

from src.core.modes import (
    MODE_GRAMMAR,
    MODE_SENTENCE,
    MODE_PASSAGE,
    canon_mode,
)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("Grammar", MODE_GRAMMAR),
        ("gram", MODE_GRAMMAR),
        ("g", MODE_GRAMMAR),
        ("문법", MODE_GRAMMAR),
        ("Sentence", MODE_SENTENCE),
        ("sent", MODE_SENTENCE),
        ("s", MODE_SENTENCE),
        ("문장", MODE_SENTENCE),
        ("reading", MODE_PASSAGE),
        ("passage", MODE_PASSAGE),
        ("p", MODE_PASSAGE),
        ("지문", MODE_PASSAGE),
    ],
)
def test_canon_mode_variants(token: str, expected: str) -> None:
    assert canon_mode(token) == expected


def test_canon_mode_idempotent() -> None:
    assert canon_mode(MODE_GRAMMAR) == MODE_GRAMMAR
    assert canon_mode(MODE_SENTENCE) == MODE_SENTENCE
    assert canon_mode(MODE_PASSAGE) == MODE_PASSAGE


def test_canon_mode_invalid() -> None:
    with pytest.raises(ValueError):
        canon_mode("unknown-mode")
    with pytest.raises(ValueError):
        canon_mode("  ")
