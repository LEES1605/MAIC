# ======================= [01] imports & constants — START =======================
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# Py3.11+: tomllib / Py3.10: tomli / 둘 다 없으면 None
try:
    import tomllib  # type: ignore[unused-ignore]  # Py3.11+
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:  # 마지막 폴백
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
    "*.lock",
)

# 파일/디렉터리 제외 글롭을 fnmatch 기준으로 정규화
DEFAULT_EXCLUDES: Tuple[str, ...] = EXCLUDE_FILES + tuple(f"*/{d}/*" for d in EXCLUDE_DIRS)

DEFAULT_MAX_DEPTH = 4
DEFAULT_STALE_DAYS = 120
DEFAULT_TOPN_SIZES = 20
DEFAULT_REPORTS: Tuple[str, ...] = ("stale", "sizes", "orphans")

DOC_ROOTS: Tuple[str, ...] = ("docs", "docs/_gpt")
# ======================= [01] imports & constants — END =========================


# ======================= [02] CLI Compat Shim — START ==========================
def _apply_out_dir_shim(argv: List[str]) -> List[str]:
    """Translate '--out-dir D' to '--out-tree D/TREE.md --out-inv D/INVENTORY.json'."""
    if "--out-dir" not in argv:
        return argv
    try:
        i = argv.index("--out-dir")
        out_dir = argv[i + 1]
    except Exception:
        # 인자가 비정상이면 argparse에게 맡긴다.
        return argv
    base = Path(out_dir)
    newv = argv[:i] + argv[i + 2 :]
    newv += ["--out-tree", str(base / "TREE.md")]
    newv += ["--out-inv", str(base / "INVENTORY.json")]
    return newv


# argparse가 실행되기 전에 argv를 변환
try:
    sys.argv = _apply_out_dir_shim(list(sys.argv))
except Exception:
    pass
# ======================= [02] CLI Compat Shim — END ============================


# ======================= [03] data models — START ==============================
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
# ======================= [03] data models — END ================================


# ======================= [04] loaders & walkers — START ========================
def _load_toml(path: Path) -> Dict:
    """Load TOML on both 3.11+(tomllib) and 3.10(tomli). Return {} on failure."""
    try:
        if tomllib is None:
            return {}
        if not path.exists() or path.stat().st_size == 0:
            return {}
        with path.open("rb") as f:
            return tomllib.load(f)  # type: ignore[misc]
    except Exception:
        return {}


def _norm_patterns(patts: Iterable[str]) -> Tuple[str, ...]:
    """fnmatch에 맞도록 경로 구분자를 '/'로 통일."""
    out: List[str] = []
    for p in patts:
        s = str(p).replace("\\", "/").strip()
        if s:
            out.append(s)
    return tuple(out)


def _depth_of(rel: Path) -> int:
    """root 기준 상대경로의 디렉터리 깊이(루트=0)."""
    return max(len(rel.parts) - 1, 0)


def _match_any(rel_posix: str, patterns: Sequence[str]) -> bool:
    """상대 경로(문자열)가 제외 패턴과 매칭되는지."""
    s_file = rel_posix
    s_dir = rel_posix.rstrip("/") + "/"
    for pat in patterns:
        if fnmatch.fnmatch(s_file, pat) or fnmatch.fnmatch(s_dir, pat):
            return True
    return False


def _iter_files(root: Path, excludes: Sequence[str]) -> Iterator[FileInfo]:
    """exclude 패턴을 적용해 파일을 순회하며 FileInfo를 생성."""
    root = root.resolve()
    exc = _norm_patterns(excludes)
    for dirpath, dirnames, filenames in os.walk(root):
        # 디렉터리 프루닝
        rel_dir = Path(dirpath).resolve().relative_to(root)
        pruned: List[str] = []
        for d in list(dirnames):
            d_rel = (rel_dir / d).as_posix()
            if _match_any(d_rel, exc):
                pruned.append(d)
        if pruned:
            dirnames[:] = [d for d in dirnames if d not in pruned]

        # 파일 처리
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.resolve().relative_to(root).as_posix()
            if _match_any(rel, exc):
                continue
            try:
                st = p.stat()
                yield FileInfo(path=p, size=int(st.st_size), mtime=float(st.st_mtime))
            except Exception:
                continue


def _sort_key(fi: FileInfo, how: str):
    """정렬 키 생성."""
    name_key = str(fi.path).lower()
    if how == "size":
        return (-fi.size, name_key)
    if how == "mtime":
        return (-fi.mtime, name_key)
    return (name_key,)
# ======================= [04] loaders & walkers — END ==========================


# ======================= [05] builders (inventory/tree) — START ================
def build_inventory(files: Sequence[FileInfo], cfg: ScanConfig) -> Dict[str, object]:
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
    except Exception:
        prev = set()

    cur = set(str(fi.path.relative_to(root)) for fi in files)
    added = sorted(list(cur - prev))
    removed = sorted(list(prev - cur))
    return {"added": added, "removed": removed, "paths": sorted(list(cur))}


_SEEN_KEYS: set = set()


def build_tree_md(files: Sequence[FileInfo], cfg: ScanConfig) -> str:
    """Create a simple tree (markdown) up to max_depth, pruned by excludes."""
    rel_files = [fi.path.relative_to(cfg.root) for fi in files]
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
            key = f"D|{i}|{Path(*parts[: i + 1])}"
            if key not in _SEEN_KEYS:
                _SEEN_KEYS.add(key)
                lines.append(f"{indent}📁 {part}")
        indent = "  " * (len(parts) - 1)
        lines.append(f"{indent}📄 {parts[-1]}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
# ======================= [05] builders (inventory/tree) — END ==================


# ======================= [06] argument parsing — START ==========================
def parse_args(argv: Optional[Sequence[str]] = None) -> ScanConfig:
    p = argparse.ArgumentParser(
        prog="gen_tree",
        description=(
            "Generate repository tree (md) and inventory (json) with excludes "
            "and basic reports."
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
        help="comma-joined: stale,sizes,orphans "
        "(default: stale,sizes,orphans)",
    )
    p.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"stale threshold in days for .md "
        f"(default: {DEFAULT_STALE_DAYS})",
    )
    p.add_argument(
        "--topn-sizes",
        type=int,
        default=DEFAULT_TOPN_SIZES,
        help=f"Top-N largest files to report "
        f"(default: {DEFAULT_TOPN_SIZES})",
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
        root_cfg = cfg_toml.get("root", {}) if isinstance(cfg_toml, dict) else {}
        ex = root_cfg.get("exclude", [])
        if isinstance(ex, list):
            excludes.extend([str(x) for x in ex])
        a.max_depth = int(root_cfg.get("max_depth", a.max_depth))

        rep_cfg = cfg_toml.get("reports", {}) if isinstance(cfg_toml, dict) else {}
        reports = rep_cfg.get("enable", [])
        if isinstance(reports, list) and reports:
            a.reports = ",".join([str(x) for x in reports])
        a.stale_days = int(rep_cfg.get("stale_days", a.stale_days))
        a.topn_sizes = int(rep_cfg.get("topn_sizes", a.topn_sizes))

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
# ======================= [06] argument parsing — END ============================


# ======================= [07] main — START =====================================
def main(argv: Optional[Sequence[str]] = None) -> int:
    cfg = parse_args(argv)
    cfg.root = cfg.root.resolve()

    files = list(_iter_files(cfg.root, cfg.excludes))
    files_sorted = sorted(files, key=lambda x: _sort_key(x, cfg.sort))

    cfg.out_tree.parent.mkdir(parents=True, exist_ok=True)
    cfg.out_inv.parent.mkdir(parents=True, exist_ok=True)

    inv = build_inventory(files_sorted, cfg)
    # save paths for future diffs
    try:
        inv["paths"] = [str(fi.path.relative_to(cfg.root)) for fi in files_sorted]
    except Exception:
        pass
    with cfg.out_inv.open("w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)

    global _SEEN_KEYS
    _SEEN_KEYS = set()
    tree_md = build_tree_md(files_sorted, cfg)
    with cfg.out_tree.open("w", encoding="utf-8") as f:
        f.write(tree_md)

    print(f"[gen_tree] root={cfg.root}")
    print(f"[gen_tree] wrote: {cfg.out_tree}")
    print(f"[gen_tree] wrote: {cfg.out_inv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# ======================= [07] main — END =======================================
