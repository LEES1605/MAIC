# ===== [01] FILE: src/backup/packaging.py — START =====
from __future__ import annotations
import os, time, zipfile
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_EXCLUDES = {
    "backups/", ".git/", "__pycache__/", "tmp/", "logs/", "cache/", ".DS_Store",
}

def _is_excluded(root: Path, p: Path, excludes: set[str]) -> bool:
    rel = str(p.relative_to(root)).replace("\\", "/")
    for ex in excludes:
        if rel == ex or rel.startswith(ex):
            return True
    return False

def make_index_zip(
    persist_dir: Path,
    *,
    out_dir: Optional[Path] = None,
    filename: Optional[str] = None,
    compression: int = zipfile.ZIP_DEFLATED,
    compresslevel: int = 6,
    extra_excludes: Optional[Iterable[str]] = None,
) -> Path:
    """
    Persist 전체를 ZIP으로 만든다. (기본 제외: backups/, .git/, __pycache__/, tmp/, logs/, cache/, .DS_Store)
    - 업로드/백업에 재사용.
    """
    out_dir = out_dir or (persist_dir / "backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"index_{int(time.time())}.zip"
    zpath = out_dir / filename

    excludes = set(DEFAULT_EXCLUDES)
    if extra_excludes:
        excludes.update({str(x).rstrip("/") + "/" if not str(x).endswith("/") else str(x) for x in extra_excludes})

    with zipfile.ZipFile(zpath, "w", compression=compression, compresslevel=compresslevel) as zf:
        for root, dirs, files in os.walk(str(persist_dir)):
            root_path = Path(root)
            # 디렉토리 필터링(깊이 우선 제외 최적화)
            dirs[:] = [d for d in dirs if not _is_excluded(persist_dir, root_path / d, excludes)]
            for fn in files:
                p = root_path / fn
                if _is_excluded(persist_dir, p, excludes):
                    continue
                # 자기 자신(zip) 또는 다른 zip 재포장 방지
                if p.suffix.lower() == ".zip":
                    continue
                # 심볼릭 링크는 건너뛴다(보안/일관성)
                try:
                    if p.is_symlink():
                        continue
                except Exception:
                    pass
                zf.write(str(p), arcname=str(p.relative_to(persist_dir)))
    return zpath
# ===== [01] FILE: src/backup/packaging.py — END =====
