# [02] START: tools/validate_canon.py
from __future__ import annotations

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
    jsonschema = None  # CI가 아닌 환경에서도 동작하도록 관용 처리

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


def _validate_with_schema(root: Path, data: dict) -> List[str]:
    """jsonschema가 있으면 스키마로 1차 검증을 수행하고 문제를 리스트로 반환."""
    problems: List[str] = []
    if jsonschema is None:
        return problems  # 스키마 검증 생략(후속 수동 검증 수행)
    schema_path = root / "modes" / "_canon.schema.json"
    try:
        schema = _load_yaml(schema_path) if schema_path.suffix in {".yaml", ".yml"} else None
        if schema is None:
            import json

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=schema)  # type: ignore
    except Exception as e:
        problems.append(f"schema validation failed: {e}")
    return problems


def validate_canon(root: Path) -> Tuple[bool, List[str]]:
    """
    Validate docs/_gpt/modes/_canon.yaml:
      1) (있다면) JSON Schema로 구조 검증
      2) 수동 규칙 검증:
         - modes.{mode}.order/required: 문자열 리스트
         - required는 기사단(필수) 섹션 포함 여부(미포함 시 '보강됨' 경고)
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

        # 권장: '근거/출처'는 필수 섹션(정책상의 표준)
        if "근거/출처" not in set(order_l + req_l):
            problems.append(f"modes.{m}: missing recommended required section '근거/출처'")

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
