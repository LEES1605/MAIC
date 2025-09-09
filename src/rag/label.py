# [01] doc & imports START
from __future__ import annotations
"""
RAG 라벨러(표준): [문법서적] / [이유문법] / [AI지식]
- search_hits(): 인덱스 확보 후 검색
- decide_label(): 파일명/확장자/경로 힌트로 라벨 결정
"""
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Callable, Tuple
import importlib
import os
import time

__all__ = ["search_hits", "decide_label"]
# [01] END


# [02] dataset path resolver START
def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    if dataset_dir:
        return Path(dataset_dir).expanduser()
    env = os.getenv("MAIC_DATASET_DIR") or os.getenv("RAG_DATASET_DIR")
    if env:
        return Path(env).expanduser()
    repo_root = Path(__file__).resolve().parents[2]
    prepared = (repo_root / "prepared").resolve()
    return prepared if prepared.exists() else (repo_root / "knowledge").resolve()
# [02] END


# [03] index TTL cache START
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30

SearchFn = Callable[..., List[Dict[str, Any]]]
GetIdxFn = Callable[..., Optional[Dict[str, Any]]]


def _get_search_handles() -> Tuple[SearchFn, Optional[GetIdxFn]]:
    mod = importlib.import_module("src.rag.search")
    search: SearchFn = getattr(mod, "search")
    get_idx: Optional[GetIdxFn] = getattr(mod, "get_or_build_index", None)
    return search, get_idx


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    global _CACHED_INDEX, _CACHED_DIR, _CACHED_AT
    now = time.time()
    ds = str(base_dir.resolve())
    if _CACHED_INDEX is not None and _CACHED_DIR == ds and (now - _CACHED_AT) < _TTL_SECS:
        return _CACHED_INDEX
    index: Optional[Dict[str, Any]] = None
    try:
        _, get_idx = _get_search_handles()
        if callable(get_idx):
            index = get_idx(ds, use_cache=True)
    except Exception:
        index = None
    _CACHED_INDEX = index
    _CACHED_DIR = ds
    _CACHED_AT = now
    return _CACHED_INDEX
# [03] END


# [04] search_hits START
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []
    search, _ = _get_search_handles()
    idx = _ensure_index(base)
    try:
        hits = search(q, dataset_dir=str(base), index=idx, top_k=int(top_k))
    except TypeError:
        hits = search(q, dataset_dir=str(base), top_k=int(top_k))
    out: List[Dict[str, Any]] = []
    for h in hits:
        out.append(
            {
                "path": h.get("path"),
                "title": h.get("title"),
                "score": h.get("score"),
                "snippet": h.get("snippet"),
                "source": h.get("source", ""),
            }
        )
    return out
# [04] END


# [05] helpers START
_BOOK_HINTS = ("문법서", "문법서적", "문법책")
_DIR_HINTS = ("book", "grammar")


def _is_reason_grammar(name: str) -> bool:
    n = name.strip()
    low = n.lower()
    return (
        n.startswith("이유문법")
        or n.startswith("[깨알문법")
        or low.startswith("iyu")
        or low.startswith("reason-grammar")
    )


def _is_book_material(path: str, title: str) -> bool:
    file_name = Path(path).name if path else title
    low_path = str(path).lower()
    low_title = title.lower()
    ext = Path(file_name).suffix.lower()
    if ext == ".pdf":
        return True
    if any(tok in file_name for tok in _BOOK_HINTS):
        return True
    if any(tok in low_path for tok in _DIR_HINTS):
        return True
    if any(tok in low_title for tok in _BOOK_HINTS):
        return True
    return False
# [05] END


# [06] decide_label START
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    items = list(hits or [])
    if not items:
        return default_if_none
    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()
    name = Path(path).name if path else title
    if _is_reason_grammar(name):
        return "[이유문법]"
    if _is_book_material(path, title):
        return "[문법서적]"
    return default_if_none
# [06] END
