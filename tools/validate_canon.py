# [02] START: tools/validate_canon.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"[validate_canon] ERROR: pyyaml not installed: {e}", file=sys.stderr)
    sys.exit(2)

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
    for x in xs:
        if not isinstance(x, str):
            raise TypeError(f"list item must be string, got: {type(x).__name__}")
        s = x.strip()
        if not s:
            raise ValueError("empty string is not allowed")
        out.append(s)
    return out


def validate_canon(root: Path) -> Tuple[bool, List[str]]:
    """
    Validate docs/_gpt/modes/_canon.yaml:
      - presence and structure
      - per-mode order/required lists (strings, unique)
      - synonyms sanity (no empties/self loops)
      - warn if required not in order (code will append later)
    """
    problems: List[str] = []
    p = root / "modes" / "_canon.yaml"
    try:
        data = _load_yaml(p)
    except Exception as e:
        return False, [f"{p}: {e}"]

    modes = data.get("modes")
    if not isinstance(modes, dict):
        problems.append("modes: required mapping not found")

    synonyms = data.get("synonyms", {})
    if synonyms and not isinstance(synonyms, dict):
        problems.append("synonyms: must be a mapping if present")

    # per-mode blocks
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

        for r in req_l:
            if r not in order_l:
                problems.append(
                    f"modes.{m}: required '{r}' not in order (will be appended by code)"
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
