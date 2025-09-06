# ===== [FILE: src/rag/index_status.py] START =====
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


@dataclass
class IndexSummary:
    ready: bool
    index_dir: str
    total_files: int
    total_chunks: int
    sample_files: List[str]
    last_built_at: Optional[float]
    details: Dict[str, Any]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_lines(path: Path, limit: Optional[int] = None) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as fh:
        for n, _ in enumerate(fh, start=1):
            if limit is not None and n >= limit:
                break
    return n


def get_index_summary(index_dir: str | Path, sample_n: int = 3) -> IndexSummary:
    """
    인덱스 디렉터리를 스캔하여 요약 정보를 생성한다.
    - 지원 파일: chunks.jsonl, manifest.json/files.json/filelist.json, index.meta.json
    """
    p = Path(index_dir)
    if not p.exists():
        return IndexSummary(
            ready=False,
            index_dir=str(p),
            total_files=0,
            total_chunks=0,
            sample_files=[],
            last_built_at=None,
            details={"reason": "index_dir_missing"},
        )

    details: Dict[str, Any] = {}

    # 1) manifest 후보 탐색
    manifest = None
    manifest_name = None
    for name in ("manifest.json", "files.json", "filelist.json"):
        fp = p / name
        if fp.exists():
            manifest = _read_json(fp)
            if manifest is not None:
                manifest_name = name
                details["manifest_file"] = name
                break

    # 2) 파일 목록 추출
    files_list: List[str] = []
    if isinstance(manifest, dict) and isinstance(manifest.get("files"), list):
        for item in manifest["files"]:
            if isinstance(item, dict):
                cand = item.get("name") or item.get("path") or item.get("file")
                if cand:
                    files_list.append(str(cand))
            else:
                files_list.append(str(item))
    elif isinstance(manifest, list):
        for item in manifest:
            files_list.append(str(item))

    # 3) 청크 개수(chunks.jsonl)
    chunks_path = p / "chunks.jsonl"
    total_chunks = _count_lines(chunks_path) if chunks_path.exists() else 0
    if chunks_path.exists():
        details["chunks_file"] = "chunks.jsonl"

    # 4) manifest 부재 시, chunks 일부에서 샘플 파일 유추
    sample_files: List[str] = []
    if not files_list and total_chunks and chunks_path.exists():
        try:
            with chunks_path.open("r", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if i >= sample_n:
                        break
                    try:
                        row = json.loads(line)
                        src = row.get("source") or row.get("path") or row.get("file")
                        if src:
                            sample_files.append(str(src))
                    except Exception:
                        pass
            files_list = sample_files[:]
        except Exception:
            pass

    # 5) 파일 총계 및 샘플
    if files_list:
        seen = set()
        deduped = []
        for name in files_list:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        files_list = deduped
    total_files = len(files_list)
    if not sample_files:
        sample_files = files_list[:sample_n]

    # 6) 빌드 시각(meta 또는 mtime)
    last_built_at: Optional[float] = None
    meta_path = p / "index.meta.json"
    if meta_path.exists():
        meta = _read_json(meta_path)
        if isinstance(meta, dict):
            last_built_at = meta.get("built_at") or meta.get("timestamp")
            details["meta_file"] = "index.meta.json"
    if last_built_at is None:
        target = chunks_path if chunks_path.exists() else p
        try:
            last_built_at = target.stat().st_mtime
        except Exception:
            last_built_at = None

    ready = (total_chunks > 0) or (total_files > 0)

    return IndexSummary(
        ready=ready,
        index_dir=str(p),
        total_files=total_files,
        total_chunks=total_chunks,
        sample_files=sample_files,
        last_built_at=last_built_at,
        details=details,
    )


def summary_as_dict(summary: IndexSummary) -> Dict[str, Any]:
    """dataclass를 dict로 변환."""
    return asdict(summary)
# ===== [FILE: src/rag/index_status.py] END =====
