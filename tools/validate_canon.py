# [02] START: tools/validate_canon.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"[validate_canon] ERROR: pyyaml not installed: {e}", file=sys.stderr)
    raise

# jsonschema는 선택 사항이지만, CI에서는 설치해 사용합니다.
try:
    import jsonschema  # type: ignore
except Exception:
    jsonschema = None  # CI 외 환경에서도 관용 처리

MODES = ("grammar", "sentence", "passage")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("root must be a mapping")
    return data


def _ensure_list_str(xs: Iterable) -> List[str]:
    out: List[str] = []
    for x in xs or []:
        if not isinstance(x, str):
            raise TypeError(f"list item must be string, got: {type(x).__name__}")
        s = x.strip()
        if not s:
            raise ValueError("empty string is not allowed")
        out.append(s)
    return out


def _load_schema(root: Path) -> dict:
    """
    스키마 파일 탐색(우선순위): .yaml → .yml → .json
    - YAML: 주석 허용(숫자구획 정책과 호환)
    - JSON: 주석 불가(파일에 START/END 주석이 있으면 파싱 실패)
    """
    candidates = [
        root / "modes" / "_canon.schema.yaml",
        root / "modes" / "_canon.schema.yml",
        root / "modes" / "_canon.schema.json",
    ]
    for sp in candidates:
        if sp.exists():
            if sp.suffix in {".yaml", ".yml"}:
                return _load_yaml(sp)
            # JSON의 경우 주석이 있으면 실패하므로 레포에서는 비권장
            return json.loads(sp.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "schema file not found: _canon.schema.yaml|yml|json under docs/_gpt/modes"
    )


def _validate_with_schema(root: Path, data: dict) -> List[str]:
    """jsonschema가 있으면 스키마로 1차 검증을 수행하고 문제를 리스트로 반환."""
    problems: List[str] = []
    if jsonschema is None:
        return problems  # 스키마 검증 생략(후속 수동 검증 수행)
    try:
        schema = _load_schema(root)
        jsonschema.validate(instance=data, schema=schema)  # type: ignore
    except Exception as e:
        problems.append(f"schema validation failed: {e}")
    return problems


def validate_canon(root: Path) -> Tuple[bool, List[str]]:
    """
    Validate docs/_gpt/modes/_canon.yaml:
      1) (가능하면) JSON Schema로 구조 검증
      2) 수동 규칙 검증:
         - modes.{mode}.order/required: 문자열 리스트
         - required 미포함 섹션은 코드에서 보강되지만, 경고 표기
         - synonyms: 키/값 문자열, 공백/자기참조 금지
    """
    p = root / "modes" / "_canon.yaml"
    problems: List[str] = []
    try:
        data = _load_yaml(p)
    except Exception as e:
        return False, [f"{p}: {e}"]

    # 1) 스키마 검증(가능하면)
    problems.extend(_validate_with_schema(root, data))

    modes = data.get("modes")
    if not isinstance(modes, dict):
        problems.append("modes: required mapping not found")

    synonyms = data.get("synonyms", {})
    if synonyms and not isinstance(synonyms, dict):
        problems.append("synonyms: must be a mapping if present")

    # 2) 수동 검증
    for m in MODES:
        block = (modes or {}).get(m)
        if block is None:
            problems.append(f"modes.{m}: missing block")
            continue
        if not isinstance(block, dict):
            problems.append(f"modes.{m}: must be a mapping")
            continue

        order = block.get("order", [])
        required = block.get("required", [])
        try:
            order_l = _ensure_list_str(order)
            req_l = _ensure_list_str(required)
        except Exception as e:
            problems.append(f"modes.{m}: {e}")
            continue

        if len(set(order_l)) != len(order_l):
            problems.append(f"modes.{m}.order: duplicated entries")

        # 정책 권장: '근거/출처' 존재(필수 혹은 order 내)
        if "근거/출처" not in set(order_l + req_l):
            problems.append(
                f"modes.{m}: missing recommended section '근거/출처'"
            )

    for k, v in (synonyms or {}).items():
        if not isinstance(k, str) or not isinstance(v, str):
            problems.append("synonyms: keys/values must be strings")
            continue
        if not k.strip() or not v.strip():
            problems.append("synonyms: empty key/value not allowed")
        if k == v:
            problems.append(f"synonyms: self mapping '{k}'")

    ok = not problems
    return ok, problems


def main() -> int:
    root = Path("docs/_gpt")
    ok, problems = validate_canon(root)
    if not ok:
        print("[validate_canon] FAIL")
        for m in problems:
            print(" -", m)
        return 1
    print("[validate_canon] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# [02] END: tools/validate_canon.py
