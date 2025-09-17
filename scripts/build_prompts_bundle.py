#!/usr/bin/env python3
"""
Build a distributable prompts bundle from a YAML source.

Outputs:
  - prompts.yaml   : source YAML (normalized copy)
  - prompts.json   : JSON conversion (UTF-8, ensure_ascii=False)
  - sha256.txt     : sha256 of prompts.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception as exc:  # noqa: BLE001
    raise SystemExit("PyYAML required. pip install pyyaml") from exc


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(obj: Any, path: Path) -> None:
    # Safe round-trip: dump with explicit UTF-8
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False)


def write_json(obj: Any, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="source prompts YAML")
    ap.add_argument("--out", dest="outdir", required=True, help="output directory")
    args = ap.parse_args()

    src = Path(args.infile).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # Load & re-dump to normalize formatting
    data = read_yaml(src)
    yaml_out = outdir / "prompts.yaml"
    json_out = outdir / "prompts.json"
    sha_out = outdir / "sha256.txt"

    write_yaml(data, yaml_out)
    write_json(data, json_out)

    digest = sha256_bytes(yaml_out.read_bytes())
    sha_out.write_text(f"sha256:{digest}\n", encoding="utf-8")

    print(f"[bundle] wrote: {yaml_out}")
    print(f"[bundle] wrote: {json_out}")
    print(f"[bundle] wrote: {sha_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
