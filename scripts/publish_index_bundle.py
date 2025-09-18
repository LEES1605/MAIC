#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from src.runtime.gh_release import GHConfig, GHReleases, GHError


def _zip_dir(src: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out_zip, "w", compression=ZIP_DEFLATED) as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src))


def main() -> int:
    ap = argparse.ArgumentParser(description="Zip a directory and upload to GitHub Releases")
    ap.add_argument("--repo", required=False, help="OWNER/REPO (default from GITHUB_REPO)")
    ap.add_argument("--token", required=False, help="GitHub token (default from GITHUB_TOKEN)")
    ap.add_argument("--src", required=False, default=str(Path.home() / ".maic" / "persist"))
    ap.add_argument("--zip", required=False, default="dist-index/indices.zip")
    ap.add_argument("--tag", required=False, default="indices-latest")
    ap.add_argument("--name", required=False, default="Indices Latest")
    args = ap.parse_args()

    repo_full = args.repo or os.getenv("GITHUB_REPO", "")
    if "/" not in repo_full:
        print("GITHUB_REPO is missing; use --repo OWNER/REPO")
        return 2
    owner, repo = repo_full.split("/", 1)
    token = args.token or os.getenv("GITHUB_TOKEN")

    src_dir = Path(args.src).expanduser().resolve()
    zip_path = Path(args.zip)

    if not src_dir.exists():
        print(f"source dir not found: {src_dir}")
        return 2

    _zip_dir(src_dir, zip_path)

    client = GHReleases(GHConfig(owner=owner, repo=repo, token=token))
    try:
        log = client.upload_index_zip(tag=args.tag, name=args.name, zip_path=zip_path)
        print(log)
        return 0
    except GHError as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
