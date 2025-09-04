# ============================== [01] RAG LABELER — START ==============================
"""
src.rag.label

- search_hits: RAG(search.py) 인덱스를 캐시/지속화(get_or_build_index)로 확보하여 검색.
- decide_label: 히트의 경로/제목/소스 키워드로 라벨을 결정.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import os
import time

# RAG 검색기 (패키지 기준)
try:
    from src.rag.search import (  # type: ignore
        search as _search,
        get_or_build_index as _get_or_build_index,
        SUPPORTED_EXTS as _EXTS,
    )
except Exception:  # pragma: no cover
    # 최소 폴백(테스트/패키징 변동에 대비). 프로젝트 구조에 따라 필요 없을 수 있음.
    from search import search as _search  # type: ignore
    try:
        from search import get_or_build_index as _get_or_build_index  # type: ignore
    except Exception:  # pragma: no cover
        _get_or_build_index = None  # type: ignore
    try:
        from search import SUPPORTED_EXTS as _EXTS  # type: ignore
    except Exception:  # pragma: no cover
        _EXTS = {".md", ".txt", ".pdf", ".html", ".json"}

__all__ = ["search_hits", "decide_label"]

# ── 데이터셋 경로 해석 ────────────────────────────────────────────────────────────
def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    """
    우선순위:
      1) 인자 dataset_dir
      2) ENV: MAIC_DATASET_DIR 또는 RAG_DATASET_DIR
      3) 기본: 프로젝트 내 'knowledge' 폴더
    """
    if dataset_dir:
        p = Path(dataset_dir).expanduser()
        return p

    env = os.environ.get("MAIC_DATASET_DIR") or os.environ.get("RAG_DATASET_DIR")
    if env:
        return Path(env).expanduser()

    return Path("knowledge").resolve()


# ── 모듈 레벨 TTL 캐시 (불필요한 재인덱싱 방지) ───────────────────────────────────
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


# ── Public API ───────────────────────────────────────────────────────────────────
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    질의어에 대한 상위 히트를 반환합니다.
    반환 형식 예: [{"path","title","score","snippet","source"} ...]
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
        hits = _search(  # type: ignore[call-arg]
            q, dataset_dir=str(base), index=idx, top_k=int(top_k)
        )
    except TypeError:
        # 일부 구현은 index 파라미터가 없을 수 있음
        hits = _search(q, dataset_dir=str(base), top_k=int(top_k))  # type: ignore[call-arg]

    out: List[Dict[str, Any]] = []
    for h in hits:
        # 표준화
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
    히트가 존재하면 경로/제목/소스 키워드로 판단하여 라벨을 반환합니다.
      - 'iyu', '이유문법' 등 → [이유문법]
      - 'book', '문법책', '교과서', 'textbook' 등 → [문법책]
      - 그 외 히트 존재 → [학습자료]
      - 히트 없으면 default_if_none 반환
    """
    items = list(hits or [])
    if not items:
        return default_if_none

    top = items[0]
    path = str(top.get("path", "")).lower()
    title = str(top.get("title", "")).lower()
    src = str(top.get("source", "")).lower()
    hay = f"{path} {title} {src}"

    if any(k in hay for k in ("iyu", "이유문법", "reason-grammar", "iyu-grammar")):
        return "[이유문법]"
    if any(k in hay for k in ("book", "문법책", "교과서", "textbook")):
        return "[문법책]"
    return "[학습자료]"
# =============================== [01] RAG LABELER — END ===============================
