# =============================== [01] RAG LABELER — START ==============================
"""
src.rag.label  (라벨 정규화: [문법서적]로 통일)

- search_hits: RAG(search.py) 인덱스를 캐시/지속화(get_or_build_index)로 확보하여 검색.
- decide_label: 히트의 파일명/확장자 규칙으로 라벨을 결정.
  * 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  * PDF → [문법서적]
  * 파일명에 '문법서적'/'문법책'/'문법서' 토큰 → [문법서적]
  * 그 외 히트 존재 → [문법서적]  (레거시와의 호환을 위해 문법 자료로 간주)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import os
import time

# RAG 검색기 (패키지 기준)
try:
    from src.rag.search import (
        search as _search,
        get_or_build_index as _get_or_build_index,
    )
except Exception:  # pragma: no cover
    from search import search as _search  # type: ignore
    try:
        from search import get_or_build_index as _get_or_build_index  # type: ignore
    except Exception:  # pragma: no cover
        _get_or_build_index = None  # type: ignore

__all__ = ["search_hits", "decide_label"]

# =============================== [02] dataset dir resolver =============================
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

# =============================== [03] index caching (TTL) =============================
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """캐시된 인덱스를 반환. TTL 내에는 재검사/재빌드 생략."""
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
            idx = _get_or_build_index(ds, use_cache=True)
    except Exception:
        idx = None

    _CACHED_INDEX = idx
    _CACHED_DIR = ds
    _CACHED_AT = now
    return _CACHED_INDEX

# =============================== [04] Public: search_hits =============================
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    질의어에 대한 상위 히트 목록을 반환합니다.
    반환 예: [{"path","title","score","snippet","source"} ...]
    """
    q = (query or "").strip()
    if not q:
        return []

    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []

    # 인덱스 확보(캐시/지속화)
    idx = _ensure_index(base)

    # search() 시그니처 차이에 대비해 dataset_dir/index 전달을 시도
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

# =============================== [05] label helpers (canonical) =======================
BOOK_LABEL = "[문법서적]"
REASON_LABEL = "[이유문법]"
AI_LABEL = "[AI지식]"

# 파일명/경로 힌트 토큰
_BOOK_NAME_TOKENS = ("문법서적", "문법서", "문법책", "[문법서적]", "[문법책]")
_REASON_PREFIXES = ("이유문법", "[깨알문법")
_REASON_PREFIXES_EN = ("reason-grammar", "iyu")


def _is_reason_grammar(name: str) -> bool:
    n = name.lower()
    return (
        name.startswith(_REASON_PREFIXES)
        or n.startswith(_REASON_PREFIXES_EN)
    )


def _looks_like_book(name: str, path: str) -> bool:
    n = name.lower()
    p = path.lower()
    # PDF는 무조건 문법서적
    if Path(path).suffix.lower() == ".pdf" or n.endswith(".pdf"):
        return True
    # 파일명 토큰 힌트
    if any(tok in name for tok in _BOOK_NAME_TOKENS):
        return True
    # 폴더 힌트(e.g., prepared/book/…)
    if "/book/" in p or p.endswith("/book") or "\\book\\" in p:
        return True
    return False

# =============================== [06] Public: decide_label ============================
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = AI_LABEL,
) -> str:
    """
    정규 라벨 규칙(정본):
      - '이유문법*' 또는 '[깨알문법*' → [이유문법]
      - PDF / '문법서적|문법책|문법서' 토큰 / book 폴더 힌트 → [문법서적]
      - 그 외 히트 존재 → [문법서적]  (레거시 호환: 일반 문법 자료로 간주)
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
        return REASON_LABEL
    if _looks_like_book(name, path):
        return BOOK_LABEL
    # 보수적으로 문법 자료로 간주(과거 기본값 유지)
    return BOOK_LABEL
# =============================== [01] RAG LABELER — END ===============================
