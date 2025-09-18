#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.runtime.gh_release import GHConfig, GHReleases, GHError


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore latest index bundle from GitHub Releases")
    ap.add_argument("--repo", required=False, help="OWNER/REPO (default from GITHUB_REPO)")
    ap.add_argument("--token", required=False, help="GitHub token (default from GITHUB_TOKEN)")
    ap.add_argument("--dest", required=False, default=str(Path.home() / ".maic" / "persist"))
    ap.add_argument("--tags", nargs="*", default=["indices-latest", "index-latest"])
    ap.add_argument("--assets", nargs="*", default=["indices.zip", "persist.zip", "hq_index.zip", "prepared.zip"])
    args = ap.parse_args()

    repo_full = args.repo or os.getenv("GITHUB_REPO", "")
    if "/" not in repo_full:
        print("GITHUB_REPO is missing; use --repo OWNER/REPO")
        return 2
    owner, repo = repo_full.split("/", 1)
    token = args.token or os.getenv("GITHUB_TOKEN")

    client = GHReleases(GHConfig(owner=owner, repo=repo, token=token))
    try:
        log = client.restore_latest_index(
            tag_candidates=args.tags,
            asset_candidates=args.assets,
            dest=Path(args.dest),
        )
        print(log)
        return 0
    except GHError as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
