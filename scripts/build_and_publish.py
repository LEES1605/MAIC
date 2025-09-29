# [01] START: scripts/build_and_publish.py — Build & Publish to GitHub Releases (전체 교체)
from __future__ import annotations

import argparse
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Tuple

# 내부 헬퍼
try:
    from src.runtime.gh_release import from_env as gh_from_env, GHError
except Exception as e:
    print(f"[FATAL] cannot import GH helper: {e}", file=sys.stderr)
    sys.exit(2)

SSOT_DIR = Path("docs/_gpt")  # SSOT 루트 고정  :contentReference[oaicite:3]{index=3}

def _fail(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)

def _info(msg: str) -> None:
    print(f"[INFO] {msg}")

def _ensure_prompts_source() -> Path:
    # 우선순위: prompts.yaml > prompts.sample.yaml
    for name in ("prompts.yaml", "prompts.sample.yaml"):
        p = (SSOT_DIR / name).resolve()
        if p.exists():
            return p
    _fail("No prompts.yaml or prompts.sample.yaml under docs/_gpt/ (SSOT).", 3)
    return Path()  # unreachable

def _pack_index_dir(src_dir: Path, out_tar_gz: Path) -> None:
    with tarfile.open(out_tar_gz, "w:gz") as tf:
        # src_dir 내부를 상대경로로 넣는다.
        for p in src_dir.rglob("*"):
            tf.add(p, arcname=str(p.relative_to(src_dir)))

def _build_asset(mode: str, explicit_asset: str | None) -> Tuple[Path, str]:
    """
    빌드 결과 파일 경로와 자산명(name)을 반환한다.
    - mode=prompts: SSOT의 prompts(.yaml|.sample.yaml)를 그대로 올린다.
    - mode=index: MAIC_INDEX_DIR(또는 data/index, build/index)에서 tar.gz를 만든다.
    - --asset이 주어지면 그대로 사용한다.
    """
    if explicit_asset:
        p = Path(explicit_asset).expanduser().resolve()
        if not p.exists():
            _fail(f"--asset not found: {p}")
        return p, p.name

    if mode == "prompts":
        src = _ensure_prompts_source()
        return src, "prompts.yaml"

    # index
    src_candidates = [
        Path(os.getenv("MAIC_INDEX_DIR", "")).expanduser(),
        Path("data/index"),
        Path("build/index"),
    ]
    src_dir = next((d for d in src_candidates if d and d.exists() and d.is_dir()), None)
    if not src_dir:
        _fail("No index directory found (MAIC_INDEX_DIR, data/index, build/index).", 4)

    out = Path(tempfile.gettempdir()) / "maic-index.tar.gz"
    _pack_index_dir(src_dir, out)
    return out, "index.tar.gz"

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build & publish artifact to GitHub Releases")
    ap.add_argument("--mode", choices=("prompts", "index"), required=True, help="Which asset to publish")
    ap.add_argument("--tag", help="Release tag (default: prompts-latest/index-latest)")
    ap.add_argument("--asset", help="Path to asset file to upload (override builder)")
    ap.add_argument("--asset-name", help="Asset name shown in release")
    ap.add_argument("--title", help="Release title (default: Prompts Latest / Index Latest)")
    ap.add_argument("--notes", help="Release notes (optional)")
    args = ap.parse_args(argv)

    mode = args.mode
    tag = args.tag or ("prompts-latest" if mode == "prompts" else "index-latest")
    title = args.title or ("Prompts Latest" if mode == "prompts" else "Index Latest")
    notes = args.notes or ""

    try:
        gh = gh_from_env()
    except GHError as e:
        _fail(f"GH env error: {e}", 2)

    # 1) 빌드 or 자산 파악
    asset_path, default_name = _build_asset(mode, args.asset)
    name = args.asset_name or default_name
    _info(f"asset: {asset_path} (as {name})")
    _info(f"tag: {tag} | title: {title}")

    # 2) 릴리스 보장 + 업로드(clobber)
    try:
        gh.ensure_release(tag, title=title, notes=notes)
        res = gh.upload_asset(tag=tag, file_path=asset_path, asset_name=name, clobber=True)
    except GHError as e:
        _fail(f"release publish failed: {e}", 5)

    # 3) 서머리
    print(f"::notice ::Published '{name}' to release '{tag}'")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# [01] END: scripts/build_and_publish.py — Build & Publish to GitHub Releases (전체 교체)
