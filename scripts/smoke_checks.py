#!/usr/bin/env python3
"""
Lightweight smoke checks to verify core features are activated.

- No network, no secrets required.
- Exit code 0 on success; non-zero on failure.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeResult:
    name: str
    ok: bool
    msg: str = ""


def check_label_ssot() -> SmokeResult:
    """
    Policy: "[문법책]" / "[문법서]" 등은 모두 "[문법서적]"으로 정규화되어야 한다.
    """
    try:
        # Lazy import to avoid module import cost if unused in future.
        from src.rag.labels import canon_label

        assert canon_label("[문법책]") == "[문법서적]"
        assert canon_label("[문법서]") == "[문법서적]"
        assert canon_label("[문법서적]") == "[문법서적]"
        return SmokeResult("label-ssot", True, "Label SSOT OK")
    except Exception as e:  # noqa: BLE001
        return SmokeResult("label-ssot", False, f"Label SSOT failed: {e!r}")


def main() -> int:
    checks = [
        check_label_ssot(),
        # TODO: add more smoke checks as features mature (e.g., mode router, pointer presence)
    ]
    failed = [c for c in checks if not c.ok]
    for c in checks:
        print(f"[smoke] {c.name}: {'OK' if c.ok else 'FAIL'}{(' — '+c.msg) if c.msg else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
