# =================== [01] Module docstring — START ===================
"""
RAG 라벨러

- search_hits(): 인덱스 확보(캐시/지속화) 후 검색
- decide_label(): 파일명/확장자/경로 힌트로 라벨 결정

라벨 규칙(운영 최소 규칙):
  * 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  * 그 외(히트 존재 시) → [문법서적]   # 운영 일관성 유지
  * 히트가 없으면 → default_if_none
"""
# ==================== [01] Module docstring — END ====================

from __future__ import annotations

# ===================== [02] Imports & exports — START =====================
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

__all__ = ["search_hits", "decide_label"]
# ====================== [02] Imports & exports — END ======================


# =================== [03] RAG search handles — START =====================
try:
    # 표준 경로(프로젝트 내부)
    from src.rag.search import (  # type: ignore
        search as _search,
        get_or_build_index as _get_or_build_index,
    )
except Exception:
    # 런타임 폴백(테스트/임시 환경)
    def _search(*_a: Any, **_k: Any) -> List[Dict[str, Any]]:
        return []

    _get_or_build_index = None  # type: ignore
# ==================== [03] RAG search handles — END ======================


# =================== [04] Dataset resolver — START ======================
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
# ==================== [04] Dataset resolver — END =======================


# =================== [05] Index TTL cache — START =======================
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
# ==================== [05] Index TTL cache — END ========================


# ===================== [06] search_hits — START =========================
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
# ====================== [06] search_hits — END ==========================


# ===================== [07] decide_label — START ========================
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙:
      - '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - 그 외(히트 존재 시) → [문법서적]
      - 히트가 없으면 → default_if_none
    """
    items = list(hits or [])
    if not items:
        return default_if_none

    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()
    name = Path(path).name if path else title

    # 1) 이유문법/깨알문법 패턴
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return "[이유문법]"

    # 2) 그 외는 운영 규칙에 따라 문법서적으로 통일
    return "[문법서적]"
# ====================== [07] decide_label — END =========================
