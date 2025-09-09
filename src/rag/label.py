# [01] docs & imports — START
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol
import os
import time

__all__ = ["search_hits", "decide_label"]

"""
RAG 라벨러

- search_hits: 인덱스를 확보(get_or_build_index)하고 검색 결과를 정규화해 반환.
- decide_label: 파일명/확장자/경로 힌트로 라벨을 결정.

라벨 규칙:
  - 이름이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  - .pdf 또는 경로에 book/grammar 힌트 또는 파일명에 문법서|문법서적|문법책 → [문법서적]
  - 그 외 → 기본값(default_if_none, 예: [AI지식])
"""
# [01] docs & imports — END


# [02] search API typing & safe imports — START
class SearchFn(Protocol):
    def __call__(self, query: str, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        ...


class GetIdxFn(Protocol):
    def __call__(self, dataset_dir: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        ...


_search: Optional[SearchFn]
_get_or_build_index: Optional[GetIdxFn]

try:
    from src.rag.search import (  # type: ignore[no-redef]
        search as _search,  # mypy: 구조적 타이핑(Protocol)로 호환
        get_or_build_index as _get_or_build_index,
    )
except Exception:  # pragma: no cover
    _search = None
    _get_or_build_index = None


def _search_stub(query: str, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    """런타임 안전 폴백: 인덱서 부재 시 빈 결과."""
    return []
# [02] search API typing & safe imports — END


# [03] dataset path resolver — START
def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    """
    우선순위:
      1) 인자 dataset_dir
      2) ENV: MAIC_DATASET_DIR 또는 RAG_DATASET_DIR
      3) <repo>/prepared (있으면)
      4) <repo>/knowledge (폴백)
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
# [03] dataset path resolver — END


# [04] index TTL cache — START
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """
    캐시된 인덱스를 반환. TTL 내에는 재빌드/재검사 생략.
    _get_or_build_index가 있으면 디스크 캐시도 활용.
    """
    global _CACHED_INDEX, _CACHED_DIR, _CACHED_AT
    now = time.time()
    ds = str(base_dir.resolve())

    if _CACHED_INDEX is not None and _CACHED_DIR == ds and (now - _CACHED_AT) < _TTL_SECS:
        return _CACHED_INDEX

    idx: Optional[Dict[str, Any]] = None
    if _get_or_build_index is not None:
        try:
            idx = _get_or_build_index(ds, use_cache=True)
        except Exception:
            idx = None

    _CACHED_INDEX = idx
    _CACHED_DIR = ds
    _CACHED_AT = now
    return _CACHED_INDEX
# [04] index TTL cache — END


# [05] public: search_hits — START
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    질의어에 대한 상위 히트를 반환.
    반환 예: [{"path","title","score","snippet","source"} ...]
    """
    q = (query or "").strip()
    if not q:
        return []

    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []

    idx = _ensure_index(base)
    search_fn: SearchFn = _search if _search is not None else _search_stub

    try:
        hits = search_fn(q, dataset_dir=str(base), index=idx, top_k=int(top_k))
    except TypeError:
        hits = search_fn(q, dataset_dir=str(base), top_k=int(top_k))

    out: List[Dict[str, Any]] = []
    for h in hits:
        out.append(
            {
                "path": str(h.get("path", "")),
                "title": str(h.get("title", "")),
                "score": h.get("score"),
                "snippet": h.get("snippet"),
                "source": str(h.get("source", "")),
            }
        )
    return out
# [05] public: search_hits — END


# [06] labeling helpers — START
def _is_reason_grammar(name: str) -> bool:
    """'이유문법' 계열 라벨 탐지."""
    if not name:
        return False
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return True
    low = name.lower()
    return low.startswith("reason-grammar") or low.startswith("iyu")


def _is_book_material(path: str, title: str) -> bool:
    """
    문법서적 후보 판별:
      - .pdf
      - 경로 힌트: 'book' 또는 'grammar'
      - 파일명 키워드: '문법서'|'문법서적'|'문법책'
    """
    # 확장자
    ext = Path(path).suffix.lower() if path else Path(title).suffix.lower()
    if ext == ".pdf":
        return True

    # 경로 힌트
    low_path = path.lower()
    if "book/" in low_path or "/book/" in low_path or "grammar" in low_path:
        return True

    # 파일명 키워드
    name = Path(path).name if path else title
    if any(k in name for k in ("문법서", "문법서적", "문법책")):
        return True

    return False
# [06] labeling helpers — END


# [07] public: decide_label — START
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙(요약):
      - '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - .pdf / 'book'·'grammar' 힌트 / '문법서|문법서적|문법책' → [문법서적]
      - 그 외 → default_if_none
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
# [07] public: decide_label — END
