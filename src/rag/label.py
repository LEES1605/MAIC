# =============================== [01] RAG LABELER — START ==============================
"""
src.rag.label (Stable-Lock)

- search_hits: RAG(search.py) 인덱스를 캐시/지속화(get_or_build_index)로 확보하여 검색.
- decide_label: 히트의 파일명/경로/확장자 규칙으로 라벨을 결정.

고정 규칙(안정성 우선):
  * 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  * 그 외, 아래 중 하나라도 만족하면 → [문법서적]
      - 확장자 .pdf
      - 상위 폴더 이름에 'book' 또는 'grammar'
      - 파일명/경로에 '문법서'|'문법서적'|'문법책' 키워드
  * 히트가 없을 때만 → default_if_none (기본: [AI지식])

표준 태그는 '[문법서적]'로 고정합니다. 필요 시 UI에서 원문 서명(책 제목)을 별도 표기하세요.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import os
import time

# RAG 검색기 (패키지 기준, 시그니처 차이에 유연 대응)
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

# ── 데이터셋 경로 해석 ────────────────────────────────────────────────────────────
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


# ── 모듈 레벨 TTL 캐시 (불필요한 재인덱싱 방지) ───────────────────────────────────
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


# ── Public API ───────────────────────────────────────────────────────────────────
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """질의어에 대한 상위 히트를 반환합니다."""
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


def _is_reason_grammar(name: str) -> bool:
    """'이유문법*' 또는 '[깨알문법]*' 등 패턴 감지."""
    if not name:
        return False
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return True
    lower = name.lower()
    return lower.startswith("iyu") or lower.startswith("reason-grammar")


def _is_book_material(path: str, title: str) -> bool:
    """문법서적 후보 판별(.pdf / book|grammar / 문법서|문법서적|문법책)."""
    name = Path(path).name if path else title
    ext = Path(path).suffix.lower() if path else Path(title).suffix.lower()
    if ext == ".pdf":
        return True

    # 상위 폴더 힌트
    try:
        parents = [p.name.lower() for p in Path(path).parents]
        if any(x in ("book", "books", "grammar") for x in parents):
            return True
    except Exception:
        pass

    s = f"{path} {title}".lower()
    return ("문법서" in s) or ("문법서적" in s) or ("문법책" in s)


def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    안정 라벨 규칙(Stable-Lock):
      - '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - _is_book_material(...) → [문법서적]
      - 그 외 히트 없음 → default_if_none
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

    # 히트가 존재하지만 위 규칙에 해당하지 않으면 보수적으로 책으로 분류
    return "[문법서적]"
# =============================== [01] RAG LABELER — END ===============================
