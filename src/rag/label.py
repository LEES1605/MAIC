# ========================= [01] module docstring & imports — START =================
"""
RAG 라벨러 (안정 패턴)
- search_hits: src.rag.search(search, get_or_build_index)로 검색(있으면 사용).
- decide_label: 히트의 경로/제목 규칙으로 라벨 결정.

라벨 규칙:
  1) 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  2) 그 외 아래 조건 중 하나라도 참이면 → [문법서적]
     - 확장자 .pdf
     - 경로에 '/book/' 포함
     - 경로·제목에 'grammar' 포함
     - 경로·제목에 '문법서|문법서적|문법책' 포함
  3) 아니면 default_if_none
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
import os
import time
# ========================= [01] module docstring & imports — END ===================


# ============================== [02] search imports — START ========================
# 넉넉한 타입 별칭(시그니처 차이 흡수)
SearchFn = Callable[..., List[Dict[str, Any]]]
GetIdxFn = Callable[..., Dict[str, Any]]

def _search_stub(*_a: Any, **_k: Any) -> List[Dict[str, Any]]:
    return []

_search: SearchFn = _search_stub
_get_or_build_index: Optional[GetIdxFn] = None

try:
    # 성공하면 런타임에 동일 이름 변수에 대입(타입은 상위에서 흡수)
    from src.rag.search import search as _search  # noqa: F401
    from src.rag.search import get_or_build_index as _get_or_build_index  # noqa: F401
except Exception:
    # CI나 특수 환경에서 모듈이 없을 때도 안전 동작
    pass
# ============================== [02] search imports — END ==========================


# ============================== [03] dataset dir resolver — START ==================
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
# ============================== [03] dataset dir resolver — END ====================


# ============================== [04] index TTL cache — START =======================
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30

def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """get_or_build_index가 있으면 캐시/지속 인덱스를 확보(30초 TTL)."""
    global _CACHED_INDEX, _CACHED_DIR, _CACHED_AT
    now = time.time()
    ds = str(base_dir.resolve())

    if _CACHED_INDEX is not None and _CACHED_DIR == ds and (now - _CACHED_AT) < _TTL_SECS:
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
# ============================== [04] index TTL cache — END =========================


# ============================== [05] public: search_hits — START ===================
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """질의어에 대한 상위 히트를 반환."""
    q = (query or "").strip()
    if not q:
        return []

    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []

    idx = _ensure_index(base)

    # search() 시그니처 차이에 대비
    try:
        return _search(q, dataset_dir=str(base), index=idx, top_k=int(top_k))
    except TypeError:
        return _search(q, dataset_dir=str(base), top_k=int(top_k))
# ============================== [05] public: search_hits — END =====================


# ============================== [06] public: decide_label — START ==================
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """히트 메타데이터로 라벨 결정."""
    items = list(hits or [])
    if not items:
        return default_if_none

    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()
    name = Path(path).name if path else title
    name_lower = name.lower()
    path_lower = path.lower()
    title_lower = title.lower()

    # 1) 이유문법/깨알문법
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return "[이유문법]"
    if name_lower.startswith("iyu") or name_lower.startswith("reason-grammar"):
        return "[이유문법]"

    # 2) 문법서적 후보
    if Path(path).suffix.lower() == ".pdf" or name_lower.endswith(".pdf"):
        return "[문법서적]"
    if "/book/" in path_lower:
        return "[문법서적]"
    if ("grammar" in path_lower) or ("grammar" in title_lower):
        return "[문법서적]"
    if any(k in name for k in ("문법서", "문법서적", "문법책")):
        return "[문법서적]"
    if any(k in title for k in ("문법서", "문법서적", "문법책")):
        return "[문법서적]"

    # 3) 그 외
    return default_if_none
# ============================== [06] public: decide_label — END =====================
