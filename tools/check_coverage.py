# [11] START: tools/check_coverage.py
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _read_threshold() -> float:
    v = os.getenv("COVERAGE_MIN", "").strip()
    if not v:
        return 0.70
    try:
        f = float(v)
    except Exception:
        return 0.70
    return max(0.0, min(1.0, f))


def _parse_rate(xml_path: Path) -> float:
    if not xml_path.exists():
        raise FileNotFoundError(f"coverage xml not found: {xml_path}")
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    # coverage.py XML format
    rate = root.attrib.get("line-rate")
    if rate is not None:
        return float(rate)

    # Cobertura-like: lines-covered / lines-valid
    lines_covered = root.attrib.get("lines-covered")
    lines_valid = root.attrib.get("lines-valid")
    if lines_covered is not None and lines_valid is not None:
        covered = float(lines_covered)
        valid = max(1.0, float(lines_valid))
        return covered / valid

    raise ValueError("line coverage rate not found in coverage XML")


def main() -> int:
    thresh = _read_threshold()
    xml_path = Path("coverage.xml")
    try:
        rate = _parse_rate(xml_path)
    except Exception as e:
        print(f"[coverage-gate] ERROR: {e}", file=sys.stderr)
        return 2

    pct = round(rate * 100.0, 2)
    need = round(thresh * 100.0, 2)
    if rate + 1e-9 < thresh:
        print(
            f"[coverage-gate] FAIL: {pct}% < required {need}% "
            f"(COVERAGE_MIN={thresh})",
            file=sys.stderr,
        )
        return 1

    print(f"[coverage-gate] OK: {pct}% >= required {need}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [11] END: tools/check_coverage.py
