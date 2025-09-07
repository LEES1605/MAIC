# =============================== [01] future import ===============================
from __future__ import annotations

# =============================== [02] module imports ==============================
import argparse
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
import datetime as dt

# =============================== [03] constants ==================================
# 트리 깊이/리포트/스테일 판단/Top-N 등 기본값
DEFAULT_MAX_DEPTH: int = 6
DEFAULT_REPORTS: Tuple[str, ...] = ("stale", "sizes", "orphans")
DEFAULT_STALE_DAYS: int = 45
DEFAULT_TOPN_SIZES: int = 20

# 기본 제외 패턴(루트 상대, POSIX 슬래시 기준)
DEFAULT_EXCLUDES: Tuple[str, ...] = (
    ".git/**",
    ".github/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "docs/_gpt/**",  # 생성 산출물은 제외
)

# 문서 루트 후보(orphans 리포트에서 사용)
DOC_ROOTS: Tuple[str, str] = ("docs/", "content/")

# ======================= [03A] TOML loader — START ===============================
def _load_toml(path: Path) -> Dict:
    """py3.11+: tomllib, 그 미만: tomli. 둘 다 없으면 빈 dict."""
    try:
        if not path or not path.exists():
            return {}
        # 함수 내부 import는 ruff E402 회피 및 tomli 미설치 환경 대응
        try:
            import sys as _sys  # noqa: F401
            if _sys.version_info >= (3, 11):
                import tomllib as _tomllib  # type: ignore
            else:
                import tomli as _tomllib  # type: ignore
        except Exception:
            return {}
        with path.open("rb") as f:
            return _tomllib.load(f)
    except Exception:
        return {}
# ======================= [03A] TOML loader — END =================================

# ======================= [03B] utils & walkers — START ===========================
def _norm_patterns(patts: Iterable[str]) -> Tuple[str, ...]:
    """fnmatch에 맞도록 경로 구분자를 '/'로 통일."""
    out: List[str] = []
    for p in patts:
        if not p:
            continue
        out.append(str(p).replace("\\", "/"))
    return tuple(out)


def _is_excluded(root: Path, file_path: Path, patterns: Sequence[str]) -> bool:
    """exclude 패턴과 매칭되는지 검사."""
    rel = file_path.relative_to(root)
    s_file = str(rel).replace("\\", "/")
    s_dir = s_file.rstrip("/") + "/"
    for pat in patterns:
        if fnmatch.fnmatch(s_file, pat) or fnmatch.fnmatch(s_dir, pat):
            return True
    return False


@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int
    mtime: float

    @property
    def mtime_dt(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.mtime)


def _iter_files(root: Path, excludes: Sequence[str]) -> Iterator[FileInfo]:
    """exclude 패턴을 적용해 파일을 순회하며 FileInfo를 생성."""
    root = root.resolve()
    pats = _norm_patterns(excludes)
    for dirpath, _dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        for fn in filenames:
            p = d / fn
            if _is_excluded(root, p, pats):
                continue
            try:
                st = p.stat()
                yield FileInfo(path=p, size=int(st.st_size), mtime=float(st.st_mtime))
            except Exception:
                # 접근 불가 등은 무시
                continue
# ======================= [03B] utils & walkers — END =============================

# ======================= [04] data models =======================================
@dataclass(frozen=True)
class ScanConfig:
    root: Path
    out_tree: Path
    out_inv: Path
    max_depth: int
    excludes: Tuple[str, ...]
    sort: str  # name|size|mtime
    reports: Tuple[str, ...]
    stale_days: int
    topn_sizes: int
    snapshot: Optional[str] = None

# ======================= [05] inventory & tree builders — START ==================
def build_inventory(files: Sequence[FileInfo], cfg: ScanConfig) -> Dict:
    now = dt.datetime.now().isoformat(timespec="seconds")

    counts_by_ext: Dict[str, int] = {}
    for fi in files:
        ext = fi.path.suffix.lower()
        counts_by_ext[ext] = counts_by_ext.get(ext, 0) + 1

    # Top-N sizes
    topn = sorted(files, key=lambda x: x.size, reverse=True)[: cfg.topn_sizes]
    topn_rows = [
        {"path": str(fi.path.relative_to(cfg.root)), "size": fi.size}
        for fi in topn
    ]

    # stale docs (markdown이 기준 날짜보다 오래된 경우)
    stale_cut = dt.datetime.now() - dt.timedelta(days=cfg.stale_days)
    stale_docs: List[Dict[str, str]] = []
    if "stale" in cfg.reports:
        for fi in files:
            if fi.path.suffix.lower() == ".md":
                if fi.mtime_dt < stale_cut:
                    stale_docs.append(
                        {
                            "path": str(fi.path.relative_to(cfg.root)),
                            "mtime": fi.mtime_dt.isoformat(timespec="seconds"),
                        }
                    )

    # orphans (문서 루트 외부의 md)
    orphans: List[str] = []
    if "orphans" in cfg.reports:
        for fi in files:
            if fi.path.suffix.lower() == ".md":
                rel = fi.path.relative_to(cfg.root)
                s = str(rel).replace("\\", "/")
                if not s.startswith(DOC_ROOTS[0]) and not s.startswith(DOC_ROOTS[1]):
                    orphans.append(s)

    inv = {
        "generated_at": now,
        "root": str(cfg.root),
        "counts_by_ext": counts_by_ext,
        "topn_sizes": topn_rows,
        "reports": {
            "stale_md": stale_docs,
            "orphans_md": orphans,
        },
    }
    return inv


def _depth_of(rel: Path) -> int:
    # 파일은 경로 파츠 수 - 1 (루트 기준)
    return max(len(rel.parts) - 1, 0)


def build_tree_markdown(files: Sequence[FileInfo], cfg: ScanConfig) -> str:
    # 정렬
    if cfg.sort == "size":
        items = sorted(files, key=lambda x: (x.path, -x.size))
    elif cfg.sort == "mtime":
        items = sorted(files, key=lambda x: (x.path, -x.mtime))
    else:
        items = sorted(files, key=lambda x: str(x.path).lower())

    lines: List[str] = []
    lines.append("# Workspace Tree")
    lines.append("")
    lines.append(f"- root: `{cfg.root}`")
    lines.append(f"- generated: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(
        f"- rules: depth={cfg.max_depth}, sort={cfg.sort}, excludes={len(cfg.excludes)}"
    )
    lines.append("")
    lines.append("```text")

    for fi in items:
        rel = fi.path.relative_to(cfg.root)
        if _depth_of(rel) > cfg.max_depth:
            continue
        parts = rel.parts
        indent = ""
        for i, part in enumerate(parts[:-1]):
            indent = "  " * i
            lines.append(f"{indent}{part}/")
        indent = "  " * max(len(parts) - 1, 0)
        lines.append(f"{indent}{parts[-1]}")

    lines.append("```")
    return "\n".join(lines)
# ======================= [05] inventory & tree builders — END ====================

# ======================= [06] arg parser ========================================
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="gen_tree")
    p.add_argument(
        "--root",
        default=".",
        help="scan root (default: .)",
    )
    p.add_argument(
        "--out-tree",
        default="docs/_gpt/TREE.md",
        help="output markdown path for tree (default: docs/_gpt/TREE.md)",
    )
    p.add_argument(
        "--out-inv",
        default="docs/_gpt/INVENTORY.json",
        help="output json path for inventory (default: docs/_gpt/INVENTORY.json)",
    )
    # ✅ alias: --out-dir (둘 다 같은 디렉터리로 보냄)
    p.add_argument(
        "--out-dir",
        default=None,
        help="if set, place TREE.md and INVENTORY.json under this directory",
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
        help="glob-style exclude pattern (repeatable)",
    )
    p.add_argument(
        "--sort",
        choices=("name", "size", "mtime"),
        default="name",
        help="sorting key for tree (default: name)",
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
        default=None,
        help=(
            "optional: save a copy of outputs into this directory "
            "(e.g., docs/_gpt/snapshots/yyyymmdd)"
        ),
    )
    p.add_argument(
        "--config",
        default="pyproject.toml",
        help="optional TOML (pyproject.toml) to override settings",
    )
    return p.parse_args(argv)
# ======================= [06] arg parser — END ===================================

# ======================= [07] main ==============================================
def main(argv: Optional[Sequence[str]] = None) -> int:
    a = parse_args(argv)

    root = Path(a.root).resolve()
    out_tree = Path(a.out_tree)
    out_inv = Path(a.out_inv)

    # --out-dir alias 처리
    if a.out_dir:
        base = Path(a.out_dir)
        out_tree = base / "TREE.md"
        out_inv = base / "INVENTORY.json"

    # TOML 오버라이드
    cfg_toml = _load_toml(Path(a.config))
    excludes = list(DEFAULT_EXCLUDES)
    if a.exclude:
        excludes.extend(a.exclude)
    # pyproject.toml → [tool.gen_tree] 섹션 기준
    tool_cfg = {}
    try:
        tool_cfg = (cfg_toml.get("tool") or {}).get("gen_tree") or {}
    except Exception:
        tool_cfg = {}

    # toml overrides
    if tool_cfg:
        excludes.extend(tool_cfg.get("exclude", []))
        max_depth = int(tool_cfg.get("max_depth", a.max_depth))
        reports = tuple(tool_cfg.get("reports", a.reports).split(","))
        stale_days = int(tool_cfg.get("stale_days", a.stale_days))
        topn_sizes = int(tool_cfg.get("topn_sizes", a.topn_sizes))
        sort = str(tool_cfg.get("sort", a.sort))
    else:
        max_depth = int(a.max_depth)
        reports = tuple(str(a.reports).split(","))
        stale_days = int(a.stale_days)
        topn_sizes = int(a.topn_sizes)
        sort = str(a.sort)

    cfg = ScanConfig(
        root=root,
        out_tree=out_tree,
        out_inv=out_inv,
        max_depth=max_depth,
        excludes=tuple(_norm_patterns(excludes)),
        sort=sort,
        reports=tuple(r.strip() for r in reports if r.strip()),
        stale_days=stale_days,
        topn_sizes=topn_sizes,
        snapshot=str(a.snapshot) if a.snapshot else None,
    )

    files = list(_iter_files(cfg.root, cfg.excludes))

    # 출력 디렉터리 보장
    cfg.out_tree.parent.mkdir(parents=True, exist_ok=True)
    cfg.out_inv.parent.mkdir(parents=True, exist_ok=True)

    # INVENTORY.json
    inv = build_inventory(files, cfg)
    cfg.out_inv.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

    # TREE.md
    tree_md = build_tree_markdown(files, cfg)
    cfg.out_tree.write_text(tree_md, encoding="utf-8")

    # 스냅샷(선택)
    if cfg.snapshot:
        snap = Path(cfg.snapshot)
        try:
            snap.mkdir(parents=True, exist_ok=True)
            (snap / "TREE.md").write_text(tree_md, encoding="utf-8")
            (snap / "INVENTORY.json").write_text(
                json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
