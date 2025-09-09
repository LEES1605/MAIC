# [01] doc & imports - START
"""
RAG 라벨러

규칙 요약:
- 파일명이 '이유문법*' 또는 '[깨알문법]*'이면 [이유문법]
- 아래 중 하나라도 맞으면 [문법서적]
  * 확장자 .pdf
  * 상위 경로에 'book'
  * 파일명 키워드: '문법서' / '문법서적' / '문법책'
  * 경로·제목에 'grammar' 힌트
- 히트가 없으면 default_if_none 반환
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# RAG 검색기 (패키지 기준, 실패 시 폴백)
try:
    from src.rag.search import (
        search as _search,
        get_or_build_index as _get_or_build_index,
    )
except Exception:  # pragma: no cover
    try:
        from search import search as _search  # type: ignore
    except Exception:  # pragma: no cover
        _search = None  # type: ignore
    try:
        from search import get_or_build_index as _get_or_build_index  # type: ignore
    except Exception:  # pragma: no cover
        _get_or_build_index = None  # type: ignore

__all__ = ["search_hits", "decide_label"]
# [01] doc & imports - END


# [02] dataset path resolver - START
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
# [02] dataset path resolver - END


# [03] index TTL cache - START
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """
    캐시된 인덱스를 반환. TTL 내에는 재검사/재빌드 생략.
    get_or_build_index가 있으면 디스크 캐시도 활용.
    """
    global _CACHED_INDEX, _CACHED_DIR, _CACHED_AT
    now = time.time()
    ds = str(base_dir.resolve())

    if (
        _CACHED_INDEX is not None
        and _CACHED_DIR == ds
        and (now - _CACHED_AT) < _TTL_SECS
    ):
        return _CACHED_INDEX

    idx: Optional[Dict[str, Any]] = None
    try:
        if callable(_get_or_build_index):
            idx = _get_or_build_index(ds, use_cache=True)  # type: ignore[call-arg]
    except Exception:
        idx = None

    _CACHED_INDEX = idx
    _CACHED_DIR = ds
    _CACHED_AT = now
    return _CACHED_INDEX
# [03] index TTL cache - END


# [04] search_hits - START
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    질의어에 대한 상위 히트를 반환합니다.
    반환 예: [{"path","title","score","snippet","source"} ...]
    """
    q = (query or "").strip()
    if not q:
        return []

    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []

    idx = _ensure_index(base)

    # search() 시그니처 차이에 대비해 dataset_dir/index 전달을 시도
    try:
        if _search is None:
            return []
        hits = _search(q, dataset_dir=str(base), index=idx, top_k=int(top_k))  # type: ignore[misc]
    except TypeError:
        hits = _search(q, dataset_dir=str(base), top_k=int(top_k))  # type: ignore[misc]

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
# [04] search_hits - END


# [05] labeling helpers - START
def _is_reason_grammar(name: str) -> bool:
    """'이유문법' 계열 라벨 감지."""
    if not name:
        return False
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return True
    low = name.lower()
    if low.startswith("reason-grammar") or low.startswith("iyu"):
        return True
    return False


def _is_book_material(path: str, title: str) -> bool:
    """
    문법서적 후보 판별:
    - .pdf 이거나
    - 상위 경로에 'book' 포함이거나
    - 파일명 키워드(문법서|문법서적|문법책) 포함이거나
    - 경로·제목에 'grammar' 힌트가 있으면 True
    """
    # 경로/제목 기초 정보
    file_name = Path(path).name if path else title
    low_name = file_name.lower()
    low_path = str(path).lower()
    low_title = title.lower()

    # 1) 확장자 .pdf
    ext = Path(path).suffix.lower() if path else Path(title).suffix.lower()
    if ext == ".pdf":
        return True

    # 2) 상위 경로 'book'
    if "book" in low_path.split("/"):
        return True

    # 3) 파일명 키워드
    if ("문법서" in file_name) or ("문법서적" in file_name) or ("문법책" in file_name):
        return True

    # 4) 경로·제목의 grammar 힌트
    if ("grammar" in low_path) or ("grammar" in low_title):
        return True

    return False
# [05] labeling helpers - END


# [06] decide_label - START
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙:
      - '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - .pdf / 'book' / 파일명 키워드 / 'grammar' 힌트 → [문법서적]
      - 그 외(히트 존재) → [문법서적]
      - 히트 없음 → default_if_none
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

    # 히트가 있는데 위 조건을 못 맞추면, 운영상 문법 자료로 간주
    return "[문법서적]"
# [06] decide_label - END
