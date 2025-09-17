#!/usr/bin/env python3
"""Validate prompts YAML against the SSOT JSON Schema.

Usage:
    python scripts/validate_prompts.py [PATH_TO_PROMPTS_YAML]

If no path is provided, it validates docs/_gpt/prompts.sample.yaml by default.
Exit code 0 on success; non-zero on failure.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception as exc:  # noqa: BLE001
    print("[prompts] PyYAML not installed. run: pip install pyyaml", file=sys.stderr)
    raise

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception as exc:  # noqa: BLE001
    print("[prompts] jsonschema not installed. run: pip install jsonschema", file=sys.stderr)
    raise


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_prompts(prompts: Any, schema: Any) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(prompts), key=lambda e: e.path)
    msgs: list[str] = []
    for e in errors:
        loc = "/".join(map(str, e.path)) or "<root>"
        msgs.append(f"[schema] {loc}: {e.message}")
    return msgs


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    default_yaml = repo_root / "docs" / "_gpt" / "prompts.sample.yaml"
    schema_path = repo_root / "schemas" / "prompts.schema.json"

    yaml_path = Path(argv[1]).resolve() if len(argv) > 1 else default_yaml

    if not yaml_path.exists():
        print(f"[prompts] YAML not found: {yaml_path}", file=sys.stderr)
        return 2
    if not schema_path.exists():
        print(f"[prompts] Schema not found: {schema_path}", file=sys.stderr)
        return 2

    prompts = load_yaml(yaml_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    msgs = validate_prompts(prompts, schema)
    if msgs:
        print("\n".join(msgs), file=sys.stderr)
        return 1

    print(f"[prompts] OK — {yaml_path.name} conforms to schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
