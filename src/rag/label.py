# ============================== [01] RAG LABELER — START ==============================
"""
src.rag.label — 출처 라벨러(표준화)

정책(표시 문자열의 표준화):
  - [문법책] → [문법서적] (칩 표기 통일)
  - [AI지식], [이유문법] 유지
결정 규칙:
  1) 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  2) 그 외 .pdf → [문법서적]
  3) 히트가 존재(비-PDF 포함) → [문법서적]
  4) 히트가 없으면 → [AI지식]
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

__all__ = ["search_hits", "decide_label", "canonicalize_label"]

# ── 표준 라벨/에일리어스 ───────────────────────────────────────────────────────
_CANON = {
    "AI": "[AI지식]",
    "BOOK": "[문법서적]",
    "REASON": "[이유문법]",
}
_ALIASES = {
    "[문법책]": _CANON["BOOK"],  # 과거 표기 흡수
}

def canonicalize_label(label: str) -> str:
    """과거 표기를 표준 표기로 치환."""
    return _ALIASES.get(label, label)

# ── 데이터셋 경로 해석 ─────────────────────────────────────────────────────────
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


# ── 모듈 레벨 TTL 캐시 ────────────────────────────────────────────────────────
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


# ── Public API ────────────────────────────────────────────────────────────────
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """질의어에 대한 상위 히트 반환: [{"path","title","score","snippet","source"}, ...]"""
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
    라벨 규칙(표준화 적용):
      - 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - 그 외 .pdf → [문법서적]
      - 히트가 있으면(비-PDF 포함) 문법 자료로 간주 → [문법서적]
      - 히트가 없으면 → [AI지식]
    """
    items = list(hits or [])
    if not items:
        return _CANON["AI"]

    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()

    # 파일명 우선
    name = Path(path).name if path else title
    name_lower = name.lower()

    # 1) 이유문법/깨알문법 패턴
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return _CANON["REASON"]
    if name_lower.startswith("iyu") or name_lower.startswith("reason-grammar"):
        return _CANON["REASON"]

    # 2) PDF → 문법서적
    if Path(name).suffix.lower() == ".pdf":
        return _CANON["BOOK"]

    # 3) 나머지(히트가 존재하는 경우) → 문법서적
    return _CANON["BOOK"]
# =============================== [01] RAG LABELER — END ===============================
