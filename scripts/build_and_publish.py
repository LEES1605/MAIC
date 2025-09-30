# [01] START: scripts/build_and_publish.py — Build & Publish to GitHub Releases (전체 교체)
from __future__ import annotations

import argparse
import datetime
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Tuple

try:
    from src.runtime.gh_release import from_env as gh_from_env, GHError
except Exception as e:
    print(f"[FATAL] cannot import GH helper: {e}", file=sys.stderr)
    sys.exit(2)

SSOT_DIR = Path("docs/_gpt")  # SSOT 루트 고정  :contentReference[oaicite:6]{index=6}

def _fail(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)

def _info(msg: str) -> None:
    print(f"[INFO] {msg}")

def _ensure_prompts_source() -> Path:
    for name in ("prompts.yaml", "prompts.sample.yaml"):
        p = (SSOT_DIR / name).resolve()
        if p.exists():
            return p
    _fail("No prompts.yaml or prompts.sample.yaml under docs/_gpt/ (SSOT).", 3)
    return Path()  # unreachable

def _pack_index_dir(src_dir: Path, out_tar_gz: Path) -> None:
    with tarfile.open(out_tar_gz, "w:gz") as tf:
        for p in src_dir.rglob("*"):
            tf.add(p, arcname=str(p.relative_to(src_dir)))

def _build_asset(mode: str, explicit_asset: str | None) -> Tuple[Path, str]:
    if explicit_asset:
        p = Path(explicit_asset).expanduser().resolve()
        if not p.exists():
            _fail(f"--asset not found: {p}")
        return p, p.name

    if mode == "prompts":
        src = _ensure_prompts_source()
        return src, "prompts.yaml"

    candidates = [
        Path(os.getenv("MAIC_INDEX_DIR", "")).expanduser(),
        Path("data/index"),
        Path("build/index"),
    ]
    src_dir = next((d for d in candidates if d and d.exists() and d.is_dir()), None)
    if not src_dir:
        _fail("No index directory found (MAIC_INDEX_DIR, data/index, build/index).", 4)

    out = Path(tempfile.gettempdir()) / "maic-index.tar.gz"
    _pack_index_dir(src_dir, out)
    return out, "index.tar.gz"

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build & publish artifact to GitHub Releases")
    ap.add_argument("--mode", choices=("prompts", "index"), required=True)
    ap.add_argument("--tag")
    ap.add_argument("--asset")
    ap.add_argument("--asset-name")
    ap.add_argument("--title")
    ap.add_argument("--notes")
    args = ap.parse_args(argv)

    mode = args.mode

    stamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")

    if mode == "index":
        version_tag = args.tag or f"index-{stamp}"
        pointer_tag = "index-latest"
        pointer_title = "Index Latest"
        pointer_asset_name = "index.tar.gz"
        version_asset_name = args.asset_name or f"{version_tag}.tar.gz"
    else:
        version_tag = args.tag or f"prompts-{stamp}"
        pointer_tag = "prompts-latest"
        pointer_title = "Prompts Latest"
        pointer_asset_name = "prompts.yaml"
        version_asset_name = args.asset_name or f"{version_tag}.yaml"

    title = args.title or ("Prompts Release" if mode == "prompts" else "Index Release")
    notes = args.notes or f"Published at {stamp} UTC"

    try:
        gh = gh_from_env()
    except GHError as e:
        _fail(f"GH env error: {e}", 2)

    asset_path, default_name = _build_asset(mode, args.asset)
    if args.asset_name is None:
        version_asset = version_asset_name
    else:
        version_asset = args.asset_name
    _info(f"asset: {asset_path} (as {version_asset})")
    _info(f"version tag: {version_tag} | title: {title}")

    try:
        gh.ensure_release(version_tag, title=title, notes=notes)
        gh.upload_asset(tag=version_tag, file_path=asset_path, asset_name=version_asset, clobber=True)

        # pointer release update
        gh.ensure_release(pointer_tag, title=pointer_title, notes=f"Tracks {version_tag}")
        gh.upload_asset(tag=pointer_tag, file_path=asset_path, asset_name=pointer_asset_name, clobber=True)
    except GHError as e:
        _fail(f"release publish failed: {e}", 5)

    print(f"::notice ::Published '{version_asset}' to release '{version_tag}'")
    print(f"::notice ::Updated pointer '{pointer_tag}'")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# [01] END: scripts/build_and_publish.py — Build & Publish to GitHub Releases (전체 교체)
