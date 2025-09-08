# ============================ [01] RAG LABELER — START ============================
"""
src.rag.label  (SSOT for source label)

규칙(우선순위):
  1) 파일명이 '이유문법*' 또는 '[깨알문법]*'  → [이유문법]
  2) 다음은 모두 문법서적으로 간주 → [문법서적]
     - 확장자 .pdf
     - 파일명에 '문법서' / '문법서적' / '문법책'
     - 상위 폴더명에 'book'
     - (문서형) 제목/이름에 'grammar'
  3) 그 외 → default_if_none (예: [AI지식])

비고:
 - search_hits()는 인덱스를 캐시/활용하여 질의 상위 히트를 반환.
 - decide_label()만 UI에서 사용하면 전체 라벨 일관성이 보장됨.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import os
import time

# --------- 내부 검색기(Lazy import; 프로젝트 구조에 따라 보강될 수 있음) ----------
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

# ======================= [02] dataset dir & index cache — START ==================
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
# ======================== [02] dataset dir & index cache — END ===================


# ============================== [03] public search — START ======================
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

    idx = _ensure_index(base)

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
# =============================== [03] public search — END =======================


# =============================== [04] label rules — START =======================
def canonicalize_label(label: str) -> str:
    """라벨 동의어를 정규 라벨로 통일."""
    s = (label or "").strip()
    if s in ("[문법책]", "[GrammarBook]"):
        return "[문법서적]"
    return s


def _is_grammar_book_by_name(name: str) -> bool:
    """파일명 기반 휴리스틱."""
    n = (name or "").lower()
    return ("문법서" in n) or ("문법서적" in n) or ("문법책" in n)


def _is_grammar_book_by_parent(path_str: str) -> bool:
    """상위 폴더명(book) 휴리스틱 (예: prepared/book/...)."""
    try:
        p = Path(path_str)
        return any(part.lower() == "book" for part in p.parts)
    except Exception:
        return False


def _is_pdf(name_or_path: str) -> bool:
    try:
        return Path(name_or_path).suffix.lower() == ".pdf" or name_or_path.lower().endswith(".pdf")
    except Exception:
        return False


def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙:
      - '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - .pdf / 파일명 키워드(문법서/문법서적/문법책) / 상위폴더 'book' / (문서형) 'grammar' → [문법서적]
      - 그 외 → default_if_none
    """
    items = list(hits or [])
    if not items:
        return default_if_none

    top = items[0]
    path = str(top.get("path", "") or "").strip()
    title = str(top.get("title", "") or "").strip()

    # 파일명/제목 파생
    name = Path(path).name if path else title
    name_lower = name.lower()
    title_lower = title.lower()

    # 1) 이유문법/깨알문법
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return "[이유문법]"
    if name_lower.startswith("iyu") or name_lower.startswith("reason-grammar"):
        return "[이유문법]"

    # 2) 문법서적 판정(여러 휴리스틱 종합)
    if (
        _is_pdf(path or name)
        or _is_grammar_book_by_name(name)
        or _is_grammar_book_by_parent(path)
        or ("grammar" in name_lower or ("grammar" in title_lower and len(title_lower) > 0))
    ):
        return "[문법서적]"

    # 3) 그 외
    return default_if_none
# ================================ [04] label rules — END ========================
# ============================ [01] RAG LABELER — END ============================
