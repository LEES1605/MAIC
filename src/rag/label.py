# ============================== [01] RAG LABELER — START ==============================
"""
src.rag.label

- search_hits: RAG(search.py) 인덱스를 캐시/지속화(get_or_build_index)로 확보하여 검색.
- decide_label: 히트의 파일명/확장자 규칙으로 라벨을 결정하고, 반드시 SSOT 정규화(canon).
  * 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  * 그 외 .pdf 파일 → [문법책]
  * 히트가 없을 때만 → [AI지식]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import os
import time

# SSOT: 라벨 상수 + 정규화
from src.rag.labels import BOOK_LABEL, REASON_LABEL, AI_LABEL, canon_label

# RAG 검색기 (패키지 기준)
try:
    from src.rag.search import (
        search as _search,
        get_or_build_index as _get_or_build_index,
    )
except Exception:  # pragma: no cover
    # 최소 폴백(프로젝트 구조에 따라 필요 없을 수 있음)
    from search import search as _search  # type: ignore
    try:
        from search import get_or_build_index as _get_or_build_index  # type: ignore
    except Exception:  # pragma: no cover
        _get_or_build_index = None  # type: ignore

__all__ = ["search_hits", "decide_label"]


# ------------------------ dataset dir resolver ---------------------------
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


# ------------------------ module-level TTL cache -------------------------
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
            idx = _get_or_build_index(ds, use_cache=True)
    except Exception:
        idx = None

    _CACHED_INDEX = idx
    _CACHED_DIR = ds
    _CACHED_AT = now
    return _CACHED_INDEX


# ----------------------------- Public API --------------------------------
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
    default_if_none: str = AI_LABEL,
) -> str:
    """
    라벨 규칙:
      - 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - 그 외 .pdf → [문법책]
      - 히트가 없으면 → [AI지식]
    항상 canon_label()로 표준화하여 반환한다.
    """
    items = list(hits or [])
    if not items:
        return canon_label(default_if_none)

    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()

    # 파일명 우선
    name = Path(path).name if path else title
    name_lower = name.lower()

    # 1) 이유문법/깨알문법 패턴
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return canon_label(REASON_LABEL)
    if name_lower.startswith("iyu") or name_lower.startswith("reason-grammar"):
        return canon_label(REASON_LABEL)

    # 2) PDF → 문법책
    if Path(path).suffix.lower() == ".pdf" or name_lower.endswith(".pdf"):
        return canon_label(BOOK_LABEL)

    # 3) 나머지(히트 존재 시)는 문법 자료로 간주 → 문법책
    return canon_label(BOOK_LABEL)
# =============================== [01] RAG LABELER — END ===============================
