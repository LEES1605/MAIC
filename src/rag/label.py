# ============== [01] imports & docstring — START ==============
"""
RAG Labeler

- search_hits(): TF/semantic 검색 모듈을 안전하게 래핑.
- decide_label(): 파일명/확장자/경로 힌트로 라벨 결정.
  * '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  * PDF / 상위폴더 'book' / 'grammar' 힌트 / 파일명에 문법서 키워드
    → [문법서적]
  * 그 외 히트 없으면 → default_if_none
"""
from __future__ import annotations

import importlib
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

__all__ = ["search_hits", "decide_label", "canonicalize_label"]
# ============== [01] imports & docstring — END ==============


# ============== [02] dataset path resolver — START ==============
def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    """
    Priority:
      1) function arg
      2) env MAIC_DATASET_DIR or RAG_DATASET_DIR
      3) <repo>/prepared (if exists)
      4) <repo>/knowledge (fallback)
    """
    if dataset_dir:
        return Path(dataset_dir).expanduser()

    env = os.environ.get("MAIC_DATASET_DIR") or os.environ.get("RAG_DATASET_DIR")
    if env:
        return Path(env).expanduser()

    repo_root = Path(__file__).resolve().parents[2]
    prepared = (repo_root / "prepared").resolve()
    if prepared.exists():
        return prepared
    return (repo_root / "knowledge").resolve()
# ============== [02] dataset path resolver — END ==============


# ============== [03] index TTL cache — START ==============
SearchFn = Callable[..., List[Dict[str, Any]]]
GetIdxFn = Callable[..., Dict[str, Any]]

_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _get_search_handles() -> Tuple[SearchFn, Optional[GetIdxFn]]:
    """Load search/get_or_build_index with safe fallbacks."""
    try:
        mod = importlib.import_module("src.rag.search")
        search: SearchFn = getattr(mod, "search")  # required
        get_idx: Optional[GetIdxFn] = getattr(mod, "get_or_build_index", None)
        return search, get_idx
    except Exception:
        def _search_stub(*_a: Any, **_k: Any) -> List[Dict[str, Any]]:
            return []
        return _search_stub, None


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Return cached index; within TTL avoid rebuild.
    If get_or_build_index exists, reuse its cache on disk.
    """
    global _CACHED_INDEX, _CACHED_DIR, _CACHED_AT
    now = time.time()
    ds = str(base_dir.resolve())

    if _CACHED_INDEX is not None and _CACHED_DIR == ds and (now - _CACHED_AT) < _TTL_SECS:
        return _CACHED_INDEX

    idx: Optional[Dict[str, Any]] = None
    _search, _get_or_build_index = _get_search_handles()
    try:
        if callable(_get_or_build_index):
            idx = _get_or_build_index(ds, use_cache=True)
    except Exception:
        idx = None

    _CACHED_INDEX, _CACHED_DIR, _CACHED_AT = idx, ds, now
    return _CACHED_INDEX
# ============== [03] index TTL cache — END ==============


# ============== [04] search_hits — START ==============
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Return top-k hits as list of dicts: path/title/score/snippet/source."""
    q = (query or "").strip()
    if not q:
        return []

    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []

    idx = _ensure_index(base)
    _search, _get_or_build_index = _get_search_handles()
    try:
        hits = _search(q, dataset_dir=str(base), index=idx, top_k=int(top_k))
    except TypeError:
        hits = _search(q, dataset_dir=str(base), top_k=int(top_k))

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
# ============== [04] search_hits — END ==============


# ============== [05] labeling helpers — START ==============
_KO_BOOK_HINTS = ("문법서", "문법서적", "문법책")


def _is_reason_grammar(name: str) -> bool:
    return name.startswith("이유문법") or name.startswith("[깨알문법") or \
        name.lower().startswith(("reason-grammar", "iyu"))


def _is_book_material(path: str, title: str) -> bool:
    """
    Book/grammar material heuristics:
      - .pdf
      - any 'book' segment in path
      - 'grammar' hint in path/title
      - Korean hints: 문법서/문법서적/문법책
    """
    file_name = Path(path).name if path else title
    ext = Path(path).suffix.lower() if path else Path(title).suffix.lower()
    if ext == ".pdf":
        return True
    low_path = path.lower()
    low_title = title.lower()
    if "/book/" in low_path or low_path.endswith("/book") or low_path.startswith("book/"):
        return True
    if "grammar" in low_path or "grammar" in low_title:
        return True
    if any(k in file_name for k in _KO_BOOK_HINTS):
        return True
    return False


def canonicalize_label(raw: str) -> str:
    """Normalize synonyms to the project’s standard tag."""
    s = (raw or "").strip()
    if s in ("[문법서적]", "[문법책]", "[문법서]"):
        return "[문법서적]"
    return s
# ============== [05] labeling helpers — END ==============


# ============== [06] decide_label — START ==============
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    Rules:
      - name startswith '이유문법*' or '[깨알문법]*' → [이유문법]
      - .pdf / 'book' folder / 'grammar' hint / KO book keywords → [문법서적]
      - otherwise → default_if_none
    """
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
# ============== [06] decide_label — END ==============
