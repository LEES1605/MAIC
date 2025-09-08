# ============================== [01] RAG LABELER — START ==============================
"""
src.rag.label — 라벨러(단일 규칙)

규칙(우선순위):
  1) 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  2) 책류(확장자 .pdf, 또는 파일명에 '문법서적'/'문법책' 포함) → [문법책]
  3) 히트가 없으면 → [AI지식]
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

_BOOK_LABEL = "[문법책]"
_BOOK_HINTS = ("문법서적", "문법책")


def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    """dataset_dir → ENV(MAIC_DATASET_DIR/RAG_DATASET_DIR) → prepared → knowledge"""
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


# ── TTL 캐시 (불필요 재인덱싱 방지) ─────────────────────────────────────────
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """get_or_build_index가 있으면 디스크 캐시도 활용."""
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


# ── Public API ─────────────────────────────────────────────────────────────────
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """질의어에 대한 상위 히트 반환."""
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


def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙:
      - 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - .pdf 또는 파일명에 '문법서적'/'문법책' 포함 → [문법책]
      - 히트가 없으면 → [AI지식]
    """
    items = list(hits or [])
    if not items:
        return default_if_none

    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()

    # 파일명 우선
    name = Path(path).name if path else title
    name_lower = name.lower()

    # 1) 이유문법/깨알문법 패턴
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return "[이유문법]"
    if name_lower.startswith("iyu") or name_lower.startswith("reason-grammar"):
        return "[이유문법]"

    # 2) 책류 판단
    if Path(path).suffix.lower() == ".pdf" or name_lower.endswith(".pdf"):
        return _BOOK_LABEL
    if any(hint in name for hint in _BOOK_HINTS):
        return _BOOK_LABEL

    # 3) 기본
    return _BOOK_LABEL
# =============================== [01] RAG LABELER — END ===============================
