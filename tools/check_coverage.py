# [11] START: tools/check_coverage.py
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# 래칫 모드: 파일에 저장된 기준선(coverage_baseline.txt) 이상을 강제
BASELINE_FILE = Path("tools/coverage_baseline.txt")


def _read_baseline() -> float | None:
    """tools/coverage_baseline.txt에서 기준선을 읽어 0.0~1.0 범위 float로 반환."""
    if not BASELINE_FILE.exists():
        return None
    raw = BASELINE_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        if raw.endswith("%"):
            return max(0.0, min(1.0, float(raw[:-1]) / 100.0))
        val = float(raw)
        return max(0.0, min(1.0, val if val <= 1.0 else val / 100.0))
    except Exception:
        return None


def _parse_rate(xml_path: Path) -> float:
    if not xml_path.exists():
        raise FileNotFoundError(f"coverage xml not found: {xml_path}")
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    # coverage.py XML: line-rate 속성
    rate = root.attrib.get("line-rate")
    if rate is not None:
        return float(rate)

    # 기타 포맷 호환: lines-covered / lines-valid
    lines_covered = root.attrib.get("lines-covered")
    lines_valid = root.attrib.get("lines-valid")
    if lines_covered is not None and lines_valid is not None:
        covered = float(lines_covered)
        valid = max(1.0, float(lines_valid))
        return covered / valid

    raise ValueError("line coverage rate not found in coverage XML")


def _threshold_with_bootstrap(current_rate: float) -> tuple[float, str]:
    """
    우선순위:
    1) baseline 파일이 있으면 → 그 값을 사용 (source='baseline-file')
    2) env COVERAGE_MIN이 있으면 → 그 값을 사용 (source='env:COVERAGE_MIN')
    3) 둘 다 없으면 → 현재 커버리지를 baseline으로 "자동 생성"하고 사용 (source='bootstrap')
       - 파일 기록 실패 시에만 마지막 수단으로 기본 0.70을 사용 (source='default')
    """
    b = _read_baseline()
    if b is not None:
        return b, "baseline-file"

    v = os.getenv("COVERAGE_MIN", "").strip()
    if v:
        try:
            fv = float(v)
            fv = fv if fv <= 1.0 else fv / 100.0
            fv = max(0.0, min(1.0, fv))
            return fv, "env:COVERAGE_MIN"
        except Exception:
            pass

    # 자동 부트스트랩: 현재 커버리지를 기준선으로 파일에 기록
    try:
        BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_FILE.write_text(f"{current_rate:.4f}\n", encoding="utf-8")
        return current_rate, "bootstrap"
    except Exception:
        # 기록 실패 시에만 기본값으로 폴백
        return 0.70, "default"


def main() -> int:
    xml_path = Path("coverage.xml")
    try:
        rate = _parse_rate(xml_path)
    except Exception as e:
        print(f"[coverage-gate] ERROR: {e}", file=sys.stderr)
        return 2

    thresh, src = _threshold_with_bootstrap(rate)

    pct = round(rate * 100.0, 2)
    need = round(thresh * 100.0, 2)

    if rate + 1e-9 < thresh:
        print(
            f"[coverage-gate] FAIL: {pct}% < required {need}% ({src})",
            file=sys.stderr,
        )
        return 1

    # 부트스트랩 시, 기준선 파일 생성 사실을 출력(참고용)
    if src == "bootstrap":
        print(f"[coverage-gate] BOOTSTRAP: baseline created at {need}% -> {BASELINE_FILE}")

    print(f"[coverage-gate] OK: {pct}% >= required {need}% ({src})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [11] END: tools/check_coverage.py
