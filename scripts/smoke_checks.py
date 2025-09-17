#!/usr/bin/env python3
"""Simple smoke checks for MAIC project.

Ensures key invariants hold without requiring a full test suite.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

# Make sure 'src' package is importable regardless of current working dir
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _run_check(name: str, check: Callable[[], None]) -> bool:
    """Run an individual smoke check and report the outcome.

    Returns True when the check succeeds, False otherwise.
    """
    label = f"[smoke] {name}"
    try:
        check()
    except Exception as exc:  # noqa: BLE001 - surface original exception
        print(f"{label}: FAIL — {name.replace('-', ' ').title()} failed: {exc!r}")
        return False
    else:
        print(f"{label}: OK")
        return True


def _check_label_ssot() -> None:
    from src.rag.labels import canon_label

    # Aliases must normalize to the canonical label
    assert canon_label("[문법책]") == "[문법서적]"
    assert canon_label("[문법서]") == "[문법서적]"
    # Canonical label must be idempotent
    assert canon_label("[문법서적]") == "[문법서적]"


def _check_mode_ssot() -> None:
    from src.core.modes import (
        MODE_GRAMMAR,
        MODE_SENTENCE,
        MODE_PASSAGE,
        canon_mode,  # may be added in later patch; if missing, adjust tests accordingly
    )

    # English / Korean / short-hands must converge to canonical labels
    assert canon_mode("Grammar") == MODE_GRAMMAR
    assert canon_mode("문장") == MODE_SENTENCE
    assert canon_mode("reading") == MODE_PASSAGE
    # Canonical labels are idempotent
    assert canon_mode(MODE_GRAMMAR) == MODE_GRAMMAR
    assert canon_mode(MODE_SENTENCE) == MODE_SENTENCE
    assert canon_mode(MODE_PASSAGE) == MODE_PASSAGE


def _check_prompts_schema_offline() -> None:
    """Load prompts from local sample via runtime loader (no network)."""
    from src.runtime.prompts_loader import load_prompts

    repo_root = Path(__file__).resolve().parents[1]
    sample = repo_root / "docs" / "_gpt" / "prompts.sample.yaml"
    data = load_prompts(
        owner="dummy",  # not used in offline mode
        repo="dummy",
        local_path=sample,  # force offline
    )
    assert isinstance(data, dict), "prompts must be a dict"
    assert "version" in data, "prompts must contain version"


CHECKS: dict[str, Callable[[], None]] = {
    "label-ssot": _check_label_ssot,
    "mode-ssot": _check_mode_ssot,
    "prompts-schema-offline": _check_prompts_schema_offline,
}


def main() -> int:
    """Execute all smoke checks."""
    results = [_run_check(name, check) for name, check in CHECKS.items()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
