# ======================= [01] imports & constants ============================
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import sys
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
)

# toml 로더: 3.11+ 은 tomllib, 3.10 이하는 tomli(동적 임포트, Any)
_TOML: Any = None
try:
    if sys.version_info >= (3, 11):
        _TOML = importlib.import_module("tomllib")
    else:
        _TOML = importlib.import_module("tomli")
except Exception:
    _TOML = None  # TOML 미지원 환경이면 넘어감

# 기본 상수
DEFAULT_MAX_DEPTH = 3
DEFAULT_REPORTS = ("stale", "sizes", "orphans")
DEFAULT_STALE_DAYS = 45
DEFAULT_TOPN_SIZES = 20
DEFAULT_EXCLUDES = (
    ".git/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "node_modules/**",
    "docs/_gpt/**",
)
# 문서/소스 루트(고아 파일 탐지용)
DOC_ROOTS = ("docs/", "src/")


# ======================= [02] dataclass & config =============================
@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int
    mtime: float

    @property
    def mtime_dt(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.mtime)


@dataclass(frozen=True)
class ScanConfig:
    root: Path
    max_depth: int = DEFAULT_MAX_DEPTH
    exclude: Tuple[str, ...] = tuple(DEFAULT_EXCLUDES)
    sort: str = "name"  # name | size | mtime
    reports: Tuple[str, ...] = tuple(DEFAULT_REPORTS)
    stale_days: int = DEFAULT_STALE_DAYS
    topn_sizes: int = DEFAULT_TOPN_SIZES
    out_tree: Path = Path("docs/_gpt/TREE.md")
    out_inv: Path = Path("docs/_gpt/INVENTORY.json")


# ======================= [03] loaders & walkers ==============================
def _load_toml(path: Path) -> Dict[str, Any]:
    """3.11+ tomllib / 3.10 tomli 양쪽 지원. 실패 시 {}."""
    try:
        if _TOML is None or not path.exists() or path.stat().st_size == 0:
            return {}
        with path.open("rb") as f:
            return _TOML.load(f)  # type: ignore[attr-defined]
    except Exception:
        return {}


def _norm_patterns(patts: Iterable[str]) -> Tuple[str, ...]:
    """fnmatch용 경로 구분자를 '/'로 통일."""
    out: List[str] = []
    for p in patts:
        s = str(p).replace("\\", "/").strip()
        if s:
            out.append(s)
    return tuple(out)


def _depth_of(rel: Path) -> int:
    """경로 깊이(루트=0)."""
    parts = rel.as_posix().split("/")
    return max(len([p for p in parts if p]) - 1, 0)


def _match_any(rel_posix: str, patterns: Sequence[str]) -> bool:
    """exclude 패턴 일치 여부."""
    s_file = rel_posix
    s_dir = rel_posix.rstrip("/") + "/"
    for pat in patterns:
        if fnmatch.fnmatch(s_file, pat) or fnmatch.fnmatch(s_dir, pat):
            return True
    return False


def _iter_files(root: Path, excludes: Sequence[str]) -> Iterator[FileInfo]:
    """exclude 패턴을 적용해 파일을 순회하며 FileInfo 생성."""
    root = root.resolve()
    exc = _norm_patterns(excludes)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).resolve().relative_to(root)
        # 디렉터리 프루닝
        pruned: List[str] = []
        for d in list(dirnames):
            rel = (rel_dir / d).as_posix()
            if _match_any(rel, exc):
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


def _sort_key(fi: FileInfo, how: str) -> Tuple[Any, ...]:
    how = how.lower()
    name_key = fi.path.as_posix().lower()
    if how == "size":
        return (-fi.size, name_key)
    if how == "mtime":
        return (-fi.mtime, name_key)
    return (name_key,)


# ======================= [04] builders (inventory/tree) ======================
def build_inventory(files: Sequence[FileInfo], cfg: ScanConfig) -> Dict[str, Any]:
    now = dt.datetime.now().isoformat(timespec="seconds")

    counts_by_ext: Dict[str, int] = {}
    for fi in files:
        ext = fi.path.suffix.lower() or "<noext>"
        counts_by_ext[ext] = counts_by_ext.get(ext, 0) + 1

    # Top-N sizes
    topn = sorted(files, key=lambda x: (-x.size, x.path.as_posix()))[: cfg.topn_sizes]
    topn_payload = [
        {"path": str(fi.path.relative_to(cfg.root)), "size": fi.size} for fi in topn
    ]

    # Stale docs(.md)
    stale_cut = dt.datetime.now() - dt.timedelta(days=cfg.stale_days)
    stale_docs: List[Dict[str, str]] = []
    if "stale" in cfg.reports:
        for fi in files:
            if fi.path.suffix.lower() == ".md" and fi.mtime_dt < stale_cut:
                stale_docs.append(
                    {
                        "path": str(fi.path.relative_to(cfg.root)),
                        "mtime": fi.mtime_dt.isoformat(timespec="seconds"),
                    }
                )
        stale_docs.sort(key=lambda d: d["path"].lower())

    # Orphans: docs/src 바깥
    orphans: List[str] = []
    if "orphans" in cfg.reports:
        for fi in files:
            s = str(fi.path.relative_to(cfg.root)).replace("\\", "/")
            if not s.startswith(DOC_ROOTS[0]) and not s.startswith(DOC_ROOTS[1]):
                orphans.append(s)
        orphans.sort(key=str.lower)

    return {
        "generated": now,
        "root": str(cfg.root),
        "rules": {
            "depth": cfg.max_depth,
            "sort": cfg.sort,
            "stale_days": cfg.stale_days,
            "topn_sizes": cfg.topn_sizes,
            "excludes": list(cfg.exclude),
        },
        "counts_by_ext": counts_by_ext,
        "topn_sizes": topn_payload if "sizes" in cfg.reports else [],
        "stale_docs": stale_docs,
        "orphans": orphans,
        "total_files": len(files),
        "total_bytes": int(sum(fi.size for fi in files)),
    }


def build_tree(files: Sequence[FileInfo], cfg: ScanConfig) -> str:
    """간단한 마크다운 트리 생성."""
    by_dir: Dict[str, List[Path]] = {}
    for fi in files:
        rel = fi.path.relative_to(cfg.root)
        if _depth_of(rel) > cfg.max_depth:
            continue
        key = str(rel.parent).replace("\\", "/")
        by_dir.setdefault(key, []).append(rel)

    # 정렬
    for k in list(by_dir.keys()):
        if cfg.sort == "size":
            by_dir[k].sort(
                key=lambda r: (
                    -next(f.size for f in files if f.path.relative_to(cfg.root) == r),
                    r.as_posix().lower(),
                )
            )
        elif cfg.sort == "mtime":
            by_dir[k].sort(
                key=lambda r: (
                    -next(
                        f.mtime for f in files if f.path.relative_to(cfg.root) == r
                    ),
                    r.as_posix().lower(),
                )
            )
        else:
            by_dir[k].sort(key=lambda r: r.as_posix().lower())

    lines: List[str] = []
    lines.append("# Project Tree")
    lines.append("")
    lines.append(f"- root: `{cfg.root}`")
    lines.append(f"- generated: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(
        f"- rules: depth={cfg.max_depth}, sort={cfg.sort}, "
        f"stale_days={cfg.stale_days}, excludes={len(cfg.exclude)}"
    )
    lines.append("")
    for d in sorted(by_dir.keys()):
        title = "/" if d == "." else f"/{d}"
        lines.append(f"## `{title}`")
        for r in by_dir[d]:
            lines.append(f"- `{r.as_posix()}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ======================= [05] argparse & I/O =================================
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="gen_tree")
    p.add_argument("--root", default=".", help="scan root directory")
    p.add_argument("--out-tree", default="docs/_gpt/TREE.md", help="tree md path")
    p.add_argument("--out-inv", default="docs/_gpt/INVENTORY.json", help="inv json path")
    p.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"max depth (default {DEFAULT_MAX_DEPTH})",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="glob exclude, repeatable (e.g., 'docs/_gpt/**')",
    )
    p.add_argument(
        "--sort",
        choices=("name", "size", "mtime"),
        default="name",
        help="sort order",
    )
    p.add_argument(
        "--reports",
        default=",".join(DEFAULT_REPORTS),
        help="comma list: stale,sizes,orphans",
    )
    p.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"stale md threshold (default {DEFAULT_STALE_DAYS})",
    )
    p.add_argument(
        "--topn-sizes",
        type=int,
        default=DEFAULT_TOPN_SIZES,
        help=f"Top-N sizes (default {DEFAULT_TOPN_SIZES})",
    )
    p.add_argument(
        "--snapshot",
        default=None,
        help=(
            "optional dir to save a copy of outputs "
            "(e.g., docs/_gpt/snapshots/yyyymmdd)"
        ),
    )
    p.add_argument(
        "--config",
        default="pyproject.toml",
        help="optional TOML to override defaults",
    )
    # 호환 파라미터: --out-dir (TREE/INV 를 그 안에 저장)
    p.add_argument(
        "--out-dir",
        default=None,
        help="compat: write TREE.md and INVENTORY.json under this directory",
    )
    return p.parse_args(argv)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _dump_text(path: Path, text: str) -> None:
    _ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def _dump_json(path: Path, obj: Any) -> None:
    _ensure_parent(path)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ======================= [06] main ===========================================
def main(argv: Optional[Sequence[str]] = None) -> int:
    a = parse_args(argv)

    # TOML 로 오버라이드(있으면)
    tool_cfg: Dict[str, Any] = {}
    try:
        cfg_toml = _load_toml(Path(a.config))
        tool_cfg = cfg_toml.get("tool", {}).get("gen_tree", {})
    except Exception:
        tool_cfg = {}

    # excludes 구성
    excludes = list(DEFAULT_EXCLUDES)
    excludes.extend(a.exclude or [])
    excludes.extend(tool_cfg.get("exclude", []))
    excludes = list(dict.fromkeys(excludes))  # uniq, 순서유지

    # out 경로 계산
    out_tree = Path(a.out_tree)
    out_inv = Path(a.out_inv)
    if a.out_dir:
        base = Path(a.out_dir)
        out_tree = base / "TREE.md"
        out_inv = base / "INVENTORY.json"

    cfg = ScanConfig(
        root=Path(a.root).resolve(),
        max_depth=int(tool_cfg.get("max_depth", a.max_depth)),
        exclude=tuple(_norm_patterns(excludes)),
        sort=str(tool_cfg.get("sort", a.sort)),
        reports=tuple(str(tool_cfg.get("reports", a.reports)).split(",")),
        stale_days=int(tool_cfg.get("stale_days", a.stale_days)),
        topn_sizes=int(tool_cfg.get("topn_sizes", a.topn_sizes)),
        out_tree=out_tree,
        out_inv=out_inv,
    )

    files = list(_iter_files(cfg.root, cfg.exclude))
    files.sort(key=lambda fi: _sort_key(fi, cfg.sort))

    inv = build_inventory(files, cfg)
    tree_md = build_tree(files, cfg)

    _dump_json(cfg.out_inv, inv)
    _dump_text(cfg.out_tree, tree_md)

    # snapshot 옵션
    if a.snapshot:
        snap_dir = Path(a.snapshot)
        _dump_json(snap_dir / cfg.out_inv.name, inv)
        _dump_text(snap_dir / cfg.out_tree.name, tree_md)

    print(f"Wrote: {cfg.out_tree} / {cfg.out_inv}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
