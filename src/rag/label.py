# ========================= [01] module docstring & imports — START =========================
"""
RAG 라벨러

- search_hits: RAG(search.py) 인덱스를 캐시/지속화로 확보하여 검색.
- decide_label: 파일명/경로/확장자 규칙으로 라벨 결정.
  * '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  * .pdf / 'book' / 'grammar' / ('문법서'|'문법서적'|'문법책') → [문법서적]
  * 히트가 없으면 → 기본 라벨
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
import os
import time

# 검색기 타입 (시그니처 차이가 있어 가변 파라미터로 표기)
SearchFn = Callable[..., List[Dict[str, Any]]]
GetIndexFn = Callable[..., Optional[Dict[str, Any]]]

# RAG 검색기 (패키지 우선, 로컬 폴백)
_search: Optional[SearchFn] = None
_get_or_build_index: Optional[GetIndexFn] = None
try:
    from src.rag.search import (
        search as _search,  # type: ignore[assignment]
        get_or_build_index as _get_or_build_index,  # type: ignore[assignment]
    )
except Exception:  # pragma: no cover
    try:
        from search import search as _search  # type: ignore[assignment]
    except Exception:
        _search = None
    try:
        from search import get_or_build_index as _get_or_build_index  # type: ignore[assignment]
    except Exception:
        _get_or_build_index = None

__all__ = ["search_hits", "decide_label"]
# ========================== [01] module docstring & imports — END ==========================


# =========================== [02] dataset path resolver — START ===========================
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
# ============================ [02] dataset path resolver — END ============================


# ============================== [03] index TTL cache — START ==============================
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

    if _CACHED_INDEX is not None and _CACHED_DIR == ds and (now - _CACHED_AT) < _TTL_SECS:
        return _CACHED_INDEX

    idx: Optional[Dict[str, Any]] = None
    if callable(_get_or_build_index):
        try:
            # 다양한 구현 시그니처를 허용하기 위해 가변 인자 호출
            idx = _get_or_build_index(ds, use_cache=True)
        except TypeError:
            try:
                idx = _get_or_build_index(ds)
            except Exception:
                idx = None
        except Exception:
            idx = None

    _CACHED_INDEX = idx
    _CACHED_DIR = ds
    _CACHED_AT = now
    return _CACHED_INDEX
# =============================== [03] index TTL cache — END ===============================


# ================================ [04] search_hits — START ================================
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

    # 인덱스 확보(캐시/지속화)
    idx = _ensure_index(base)

    # search() 시그니처 차이에 대비해 dataset_dir/index 전달을 시도
    if not callable(_search):
        return []
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
# ================================= [04] search_hits — END =================================


# ============================ [05] labeling helpers — START ===============================
def _is_reason_grammar(name: str) -> bool:
    """'이유문법' 계열 라벨 감지."""
    low = name.lower()
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return True
    if low.startswith("reason-grammar") or low.startswith("iyu"):
        return True
    return False


def _is_book_material(path: str, title: str) -> bool:
    """
    문법서적 후보 판별:
      - .pdf 이거나
      - 경로/이름/제목에 book | grammar | 문법서|문법서적|문법책 포함
    """
    ext = Path(path).suffix.lower() if path else Path(title).suffix.lower()
    if ext == ".pdf":
        return True

    low_path = str(path).lower()
    low_title = title.lower()
    tokens = ("book", "grammar", "문법서", "문법서적", "문법책")
    if any(t in low_path for t in tokens):
        return True
    if any(t in low_title for t in tokens):
        return True
    return False
# ============================= [05] labeling helpers — END ================================


# ================================= [06] decide_label — START ==============================
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙:
      - '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - .pdf / book|grammar / 문법서|문법서적|문법책 → [문법서적]
      - 히트가 없으면 → default_if_none
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
# ================================== [06] decide_label — END ===============================
