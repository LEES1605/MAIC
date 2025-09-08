# ============================== [01] RAG LABELER — START ==============================
"""
src.rag.label — Label resolver (SSOT + aliases)

규칙 요약:
  - 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
  - 파일명에 '문법서적' 있으면 → [문법서적]
  - 파일명에 '문법책'  있으면 → [문법책]
  - 그 외 .pdf → 기본 라벨(환경변수 MAIC_GRAMMAR_BOOK_LABEL, 기본 "[문법서적]")
  - 그 외 전부   → 기본 라벨(동일)

테스트가 파일명 힌트로 '문법서적_*'을 사용하더라도 일관 통과.
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

# ── 상수/헬퍼(SSOT) ───────────────────────────────────────────────────────────────
LABEL_REASON_GRAMMAR = "[이유문법]"
LABEL_GRAMMAR_BOOK_DEFAULT = "[문법서적]"  # 환경변수 미설정 시 기본

# 파일명 동의어 토큰(영문형 포함)
_BOOK_ALIAS_TOKENS = ("문법서적", "문법책", "grammarbook", "grammar-book", "grammar_book")


def _canonical_book_label() -> str:
    """환경변수로 지정 가능: MAIC_GRAMMAR_BOOK_LABEL (기본 [문법서적])."""
    lab = (os.getenv("MAIC_GRAMMAR_BOOK_LABEL") or "").strip()
    return lab or LABEL_GRAMMAR_BOOK_DEFAULT


def _book_label_from_name(name: str) -> Optional[str]:
    """파일명/제목에서 문법서적 계열 힌트를 감지하여 라벨을 결정."""
    n = (name or "").lower()
    if not n:
        return None
    # 한글 동의어는 '있는 그대로' 반환 → 테스트와 사용자 기대를 모두 충족
    if "문법서적" in n:
        return "[문법서적]"
    if "문법책" in n:
        return "[문법책]"
    # 영문형/하이픈형 등은 기본 라벨로 통일
    if any(tok in n for tok in ("grammarbook", "grammar-book", "grammar_book")):
        return _canonical_book_label()
    return None


# ── 데이터셋 경로 해석 ────────────────────────────────────────────────────────────
def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    """
    우선순위:
      1) 인자 dataset_dir
      2) ENV: MAIC_DATASET_DIR 또는 RAG_DATASET_DIR
      3) <repo>/prepared (있으면) → 없으면 <repo>/knowledge
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


# ── 모듈 레벨 TTL 캐시 ───────────────────────────────────────────────────────────
_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """get_or_build_index가 있으면 디스크 캐시를 활용하고 TTL 동안 재빌드 생략."""
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
    default_if_none: str = "[AI지식]",
) -> str:
    """
    라벨 규칙(동의어/기본값 포함):
      - 파일명이 '이유문법*' 또는 '[깨알문법]*' → [이유문법]
      - 파일명에 '문법서적'/'문법책'이 있으면 해당 표기를 그대로 반환
      - 그 외 .pdf → 기본 라벨(환경변수/기본값)
      - 그 외 전부 → 기본 라벨(환경변수/기본값)
      - 히트가 없으면 default_if_none
    """
    items = list(hits or [])
    if not items:
        return default_if_none

    top = items[0]
    path = str(top.get("path", "")).strip()
    title = str(top.get("title", "")).strip()

    # 파일명/타이틀 파생
    name = Path(path).name if path else title
    nlow = name.lower()

    # 1) 이유문법/깨알문법 패턴
    if name.startswith("이유문법") or name.startswith("[깨알문법"):
        return LABEL_REASON_GRAMMAR
    if nlow.startswith("iyu") or nlow.startswith("reason-grammar"):
        return LABEL_REASON_GRAMMAR

    # 2) 파일명 힌트(동의어 우선)
    lab = _book_label_from_name(name or title)
    if lab:
        return lab

    # 3) PDF → 기본 라벨
    ext = Path(path).suffix.lower()
    if ext == ".pdf" or nlow.endswith(".pdf"):
        return _canonical_book_label()

    # 4) 그 외 전부 기본 라벨
    return _canonical_book_label()
# =============================== [01] RAG LABELER — END ===============================
