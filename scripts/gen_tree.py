# ======================= [01] imports & constants — START =======================
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:  # Python 3.11+
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

EXCLUDE_DIRS: Tuple[str, ...] = (
    ".git",
    ".github",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
)

EXCLUDE_FILES: Tuple[str, ...] = (
    ".DS_Store",
    "*.zip",
    "*.bin",
)

DEFAULT_MAX_DEPTH = 4
DEFAULT_STALE_DAYS = 120
DEFAULT_TOPN_SIZES = 20
DEFAULT_REPORTS: Tuple[str, ...] = ("stale", "sizes", "orphans")

DOC_ROOTS: Tuple[str, ...] = ("docs", "docs/_gpt")

# ======================= [01] imports & constants — END =========================

# ======================= [02] data models — START ===============================
@dataclass
class FileInfo:
    path: Path
    size: int
    mtime: float

    @property
    def ext(self) -> str:
        return self.path.suffix.lower()

    @property
    def mtime_dt(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.mtime)


@dataclass
class ScanConfig:
    root: Path
    excludes: Tuple[str, ...]
    max_depth: int
    sort: str  # "name" | "size" | "mtime"
    reports: Tuple[str, ...]
    stale_days: int
    topn_sizes: int
    out_tree: Path
    out_inv: Path
    snapshot: Optional[Path]


# ======================= [02] data models — END =================================

# ======================= [03] utilities — START =================================
def _load_toml(path: Path) -> Dict:
    """Load TOML using stdlib when available. Return {} if missing/invalid."""
    if not path.exists() or path.stat().st_size == 0:
        return {}
    if tomllib is None:
        return {}
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _norm_patterns(pats: Iterable[str]) -> Tuple[str, ...]:
    out: List[str] = []
    for p in pats:
        p = str(p).strip()
        if not p:
            continue
        out.append(p)
    return tuple(out)


def _is_excluded(rel: Path, patterns: Sequence[str]) -> bool:
    s = str(rel)
    for pat in patterns:
        if fnmatch.fnmatch(s, pat):
            return True
    return False


@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int
    mtime: float


def _iter_files(root: Path, exclude_globs: Sequence[str]) -> Iterator[FileInfo]:
    """Iterate files under root excluding patterns."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _is_excluded(rel, exclude_globs):
            continue
        try:
            st = p.stat()
            yield FileInfo(path=p, size=int(st.st_size), mtime=float(st.st_mtime))
        except FileNotFoundError:
            # raced file remove; ignore
            continue


def _sort_key(fi: FileInfo, mode: str) -> Tuple:
    if mode == "size":
        return (-fi.size, str(fi.path))
    if mode == "mtime":
        return (-fi.mtime, str(fi.path))
    return (str(fi.path).lower(),)

# ======================= [03] utilities — END ===================================

# ======================= [04] inventory & tree builders — START =================
def build_inventory(files: Sequence[FileInfo], cfg: ScanConfig) -> Dict:
    now = dt.datetime.now().isoformat(timespec="seconds")
    counts_by_ext: Dict[str, int] = {}
    for fi in files:
        ext = fi.ext or "<noext>"
        counts_by_ext[ext] = counts_by_ext.get(ext, 0) + 1

    # top sizes
    top_sizes = sorted(files, key=lambda x: (-x.size, str(x.path)))[: cfg.topn_sizes]
    top_sizes_out = [
        {
            "path": str(fi.path.relative_to(cfg.root)),
            "size": fi.size,
            "kb": round(fi.size / 1024, 1),
        }
        for fi in top_sizes
    ]

    # stale docs (md older than threshold)
    stale_cut = dt.datetime.now() - dt.timedelta(days=cfg.stale_days)
    stale_docs: List[Dict[str, str]] = []
    if "stale" in cfg.reports:
        for fi in files:
            if fi.ext == ".md" and fi.mtime_dt < stale_cut:
                stale_docs.append(
                    {
                        "path": str(fi.path.relative_to(cfg.root)),
                        "last_modified": fi.mtime_dt.isoformat(timespec="seconds"),
                    }
                )

    # orphans: markdown outside doc roots
    orphans: List[str] = []
    if "orphans" in cfg.reports:
        for fi in files:
            if fi.ext == ".md":
                rel = fi.path.relative_to(cfg.root)
                s = str(rel).replace("\\", "/")
                if not s.startswith(DOC_ROOTS[0]) and not s.startswith(DOC_ROOTS[1]):
                    orphans.append(s)

    inv: Dict[str, object] = {
        "generated_at": now,
        "root": str(cfg.root),
        "total_files": len(files),
        "total_dirs": _count_dirs(files, cfg.root),
        "counts_by_ext": counts_by_ext,
        "top_sizes": top_sizes_out,
        "stale_docs": stale_docs,
        "orphans": orphans,
        "config": {
            "max_depth": cfg.max_depth,
            "excludes": list(cfg.excludes),
            "sort": cfg.sort,
            "reports": list(cfg.reports),
            "stale_days": cfg.stale_days,
            "topn_sizes": cfg.topn_sizes,
        },
    }

    # diff with snapshot
    if cfg.snapshot and cfg.snapshot.exists():
        try:
            with cfg.snapshot.open("r", encoding="utf-8") as f:
                snap = json.load(f)
            inv["diff"] = _diff_inventory_paths(snap, files, cfg.root)
        except Exception:
            inv["diff"] = {"error": "snapshot_load_failed"}

    return inv


def _count_dirs(files: Sequence[FileInfo], root: Path) -> int:
    dirs = set()
    for fi in files:
        try:
            rel = fi.path.relative_to(root)
        except Exception:
            rel = fi.path
        parent = rel.parent
        while True:
            dirs.add(str(parent))
            if str(parent) in (".", ""):
                break
            parent = parent.parent
    return len([d for d in dirs if d not in (".", "")])


def _diff_inventory_paths(snap: Dict, files: Sequence[FileInfo], root: Path) -> Dict:
    prev = set()
    try:
        prev_top = snap.get("paths", None)
        if isinstance(prev_top, list):
            prev = set(prev_top)
        else:
            # fallback: build from previous inventory content
            pass
    except Exception:
        prev = set()

    cur = set(str(fi.path.relative_to(root)) for fi in files)
    added = sorted(list(cur - prev))
    removed = sorted(list(prev - cur))
    return {"added": added, "removed": removed, "paths": sorted(list(cur))}


def build_tree_md(files: Sequence[FileInfo], cfg: ScanConfig) -> str:
    """Create a simple tree (markdown) up to max_depth, pruned by excludes."""
    # Map dir -> [files]
    rel_files = [fi.path.relative_to(cfg.root) for fi in files]
    # Build directory set present within depth
    max_depth = cfg.max_depth
    items = sorted(rel_files, key=lambda p: str(p).lower())

    lines: List[str] = []
    lines.append("# Repository Tree (generated)")
    lines.append("")
    lines.append(f"- root: `{cfg.root}`")
    lines.append(f"- generated: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(
        f"- rules: depth={cfg.max_depth}, sort={cfg.sort}, "
        f"excludes={', '.join(cfg.excludes)}"
    )
    lines.append("")
    lines.append("```text")
    for rel in items:
        if _depth_of(rel) > max_depth:
            continue
        parts = rel.parts
        # print parent directories and file
        for i, part in enumerate(parts[:-1]):
            indent = "  " * i
            # Only print directories when first time encountered
            key = f"D|{i}|{Path(*parts[: i + 1])}"
            if key not in _SEEN_KEYS:
                _SEEN_KEYS.add(key)
                lines.append(f"{indent}📁 {part}")
        # file line
        indent = "  " * (len(parts) - 1)
        lines.append(f"{indent}📄 {parts[-1]}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


_SEEN_KEYS: set = set()
# ======================= [04] inventory & tree builders — END ===================


# ======================= [05] argument parsing — START ==========================
def parse_args(argv: Optional[Sequence[str]] = None) -> ScanConfig:
    p = argparse.ArgumentParser(
        prog="gen_tree",
        description=(
            "Generate repository tree (md) and inventory (json) with excludes and "
            "basic reports."
        ),
    )
    p.add_argument("--root", default=".", help="scan root directory (default: .)")
    p.add_argument(
        "--out-tree",
        default="docs/_gpt/TREE.md",
        help="output markdown tree path (default: docs/_gpt/TREE.md)",
    )
    p.add_argument(
        "--out-inv",
        default="docs/_gpt/INVENTORY.json",
        help="output inventory json path (default: docs/_gpt/INVENTORY.json)",
    )
    p.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"max directory depth (default: {DEFAULT_MAX_DEPTH})",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="exclude patterns (can repeat). Example: --exclude node_modules",
    )
    p.add_argument(
        "--sort",
        choices=("name", "size", "mtime"),
        default="name",
        help="sorting for internal lists (default: name)",
    )
    p.add_argument(
        "--reports",
        default=",".join(DEFAULT_REPORTS),
        help="comma-joined: stale,sizes,orphans (default: stale,sizes,orphans)",
    )
    p.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"stale threshold in days for .md (default: {DEFAULT_STALE_DAYS})",
    )
    p.add_argument(
        "--topn-sizes",
        type=int,
        default=DEFAULT_TOPN_SIZES,
        help=f"Top-N largest files to report (default: {DEFAULT_TOPN_SIZES})",
    )
    p.add_argument(
        "--snapshot",
        default="",
        help="previous inventory json path to diff (optional)",
    )
    p.add_argument(
        "--config",
        default="scripts/gen_tree.toml",
        help="optional TOML config path (default: scripts/gen_tree.toml)",
    )

    a = p.parse_args(argv)

    # Load overrides from TOML (optional)
    cfg_toml = _load_toml(Path(a.config))
    excludes = list(DEFAULT_EXCLUDES)
    if a.exclude:
        excludes.extend(a.exclude)
    if cfg_toml:
        ex = cfg_toml.get("root", {}).get("exclude", [])
        if isinstance(ex, list):
            excludes.extend([str(x) for x in ex])
        max_depth = int(cfg_toml.get("root", {}).get("max_depth", a.max_depth))
        a.max_depth = max_depth
        reports = cfg_toml.get("reports", {}).get("enable", [])
        if isinstance(reports, list) and reports:
            a.reports = ",".join([str(x) for x in reports])
        stale_days = cfg_toml.get("reports", {}).get("stale_days", a.stale_days)
        a.stale_days = int(stale_days)
        topn_sizes = cfg_toml.get("reports", {}).get("topn_sizes", a.topn_sizes)
        a.topn_sizes = int(topn_sizes)

    reports_tuple = tuple(
        s.strip().lower() for s in str(a.reports).split(",") if s.strip()
    )

    sc = ScanConfig(
        root=Path(a.root),
        excludes=_norm_patterns(excludes),
        max_depth=int(a.max_depth),
        sort=str(a.sort),
        reports=reports_tuple,
        stale_days=int(a.stale_days),
        topn_sizes=int(a.topn_sizes),
        out_tree=Path(a.out_tree),
        out_inv=Path(a.out_inv),
        snapshot=Path(a.snapshot) if a.snapshot else None,
    )
    return sc


# ======================= [05] argument parsing — END ============================


# ======================= [06] main — START =====================================
def main(argv: Optional[Sequence[str]] = None) -> int:
    cfg = parse_args(argv)
    cfg.root = cfg.root.resolve()

    files = list(_iter_files(cfg.root, cfg))
    files_sorted = sorted(files, key=lambda x: _sort_key(x, cfg.sort))

    # ensure out directories
    cfg.out_tree.parent.mkdir(parents=True, exist_ok=True)
    cfg.out_inv.parent.mkdir(parents=True, exist_ok=True)

    # inventory (with diff if snapshot provided)
    inv = build_inventory(files_sorted, cfg)
    # save inventory with current paths to allow future diffs
    try:
        inv["paths"] = [
            str(fi.path.relative_to(cfg.root)) for fi in files_sorted
        ]
    except Exception:
        pass
    with cfg.out_inv.open("w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)

    # tree md
    global _SEEN_KEYS
    _SEEN_KEYS = set()
    tree_md = build_tree_md(files_sorted, cfg)
    with cfg.out_tree.open("w", encoding="utf-8") as f:
        f.write(tree_md)

    # console summary
    print(f"[gen_tree] root={cfg.root}")
    print(f"[gen_tree] wrote: {cfg.out_tree}")
    print(f"[gen_tree] wrote: {cfg.out_inv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# ======================= [06] main — END =======================================
