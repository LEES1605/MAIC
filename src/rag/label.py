# [01] START: src/rag/label.py (FULL REPLACEMENT)
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import importlib
import os
import time

__all__ = [
    "search_hits",
    "decide_label",
    "canonicalize_label",
    "classify_hit",
    "make_source_chip",
]

# -------------------- dataset path resolver --------------------
def _resolve_dataset_dir(dataset_dir: Optional[str]) -> Path:
    """
    Priority:
      1) function arg
      2) env MAIC_DATASET_DIR or RAG_DATASET_DIR
      3) <repo>/prepared (if exists)
      4) <repo>/knowledge (fallback)
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


# -------------------- index TTL cache & handles --------------------
SearchFn = Tuple[Any, ...].__class__  # just for type hint readability
GetIdxFn = Tuple[Any, ...].__class__

_CACHED_INDEX: Optional[Dict[str, Any]] = None
_CACHED_DIR: Optional[str] = None
_CACHED_AT: float = 0.0
_TTL_SECS: int = 30


def _get_search_handles() -> Tuple[Any, Optional[Any]]:
    """Load search/get_or_build_index with safe fallbacks."""
    try:
        mod = importlib.import_module("src.rag.search")
        search = getattr(mod, "search")  # required
        get_idx = getattr(mod, "get_or_build_index", None)
        return search, get_idx
    except Exception:
        def _search_stub(*_a: Any, **_k: Any) -> List[Dict[str, Any]]:
            return []
        return _search_stub, None


def _ensure_index(base_dir: Path) -> Optional[Dict[str, Any]]:
    """Return cached index; within TTL avoid rebuild."""
    global _CACHED_INDEX, _CACHED_DIR, _CACHED_AT
    now = time.time()
    ds = str(base_dir.resolve())
    if _CACHED_INDEX is not None and _CACHED_DIR == ds and (now - _CACHED_AT) < _TTL_SECS:
        return _CACHED_INDEX

    idx: Optional[Dict[str, Any]] = None
    _search, _get_or_build_index = _get_search_handles()
    try:
        if callable(_get_or_build_index):
            idx = _get_or_build_index(ds, use_cache=True)
    except Exception:
        idx = None

    _CACHED_INDEX, _CACHED_DIR, _CACHED_AT = idx, ds, now
    return _CACHED_INDEX


# ------------------------------ search_hits ------------------------------
def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Return top-k hits as list of dicts: path/title/score/snippet/source."""
    q = (query or "").strip()
    if not q:
        return []

    base = _resolve_dataset_dir(dataset_dir)
    if not base.exists():
        return []

    idx = _ensure_index(base)
    _search, _get_or_build_index = _get_search_handles()
    try:
        hits = _search(q, dataset_dir=str(base), index=idx, top_k=int(top_k))
    except TypeError:
        hits = _search(q, dataset_dir=str(base), top_k=int(top_k))

    out: List[Dict[str, Any]] = []
    for h in hits or []:
        out.append(
            {
                "path": h.get("path"),
                "title": h.get("title"),
                "score": h.get("score"),
                "snippet": h.get("snippet"),
                "source": h.get("source", ""),
                "meta": h.get("meta") or h.get("metadata") or {},
            }
        )
    return out


# ------------------------------ labeling helpers ------------------------------
_KO_BOOK_HINTS = ("문법서", "문법서적", "문법책")
_EN_BOOK_HINTS = (
    "grammar",
    "cambridge",
    "oxford",
    "longman",
    "macmillan",
    "pearson",
    "ets",
    "toefl",
    "ielts",
)
_REASON_KEYS = ("이유문법", "깨알문법")


def canonicalize_label(raw: str) -> str:
    """Normalize synonyms to the project’s standard tag."""
    s = (raw or "").strip()
    if s in ("[문법서적]", "[문법책]", "[문법서]"):
        return "[문법서적]"
    return s or "[AI지식]"


def _gather_text_fields(hit: Dict[str, Any]) -> str:
    buf: List[str] = []
    for k in ("title", "source", "path", "doc_id", "url", "file", "name"):
        v = hit.get(k)
        if isinstance(v, str) and v:
            buf.append(v)
    meta = hit.get("meta") or hit.get("metadata") or {}
    if isinstance(meta, dict):
        for k in ("title", "source", "path"):
            v = meta.get(k)
            if isinstance(v, str) and v:
                buf.append(v)
    return " ".join(buf).lower()


def _is_reason_grammar(name: str) -> bool:
    n = (name or "").strip()
    return n.startswith("이유문법") or n.startswith("[깨알문법") or n.lower().startswith(
        ("reason-grammar", "iyu")
    )


def _is_book_material(path: str, title: str) -> bool:
    """
    Heuristics:
      - .pdf
      - any 'book' segment in path
      - 'grammar' hint in path/title
      - KO hints: 문법서/문법서적/문법책
      - EN hints: Cambridge/Oxford/Longman/Macmillan/Pearson/ETS/TOEFL/IELTS
    """
    file_name = Path(path).name if path else title
    ext = Path(path).suffix.lower() if path else Path(title).suffix.lower()
    if ext == ".pdf":
        return True
    low_path = path.lower()
    low_title = title.lower()
    if "/book/" in low_path or low_path.endswith("/book") or low_path.startswith("book/"):
        return True
    if "grammar" in low_path or "grammar" in low_title:
        return True
    if any(k in file_name for k in _KO_BOOK_HINTS):
        return True
    if any(k in low_path for k in _EN_BOOK_HINTS) or any(k in low_title for k in _EN_BOOK_HINTS):
        return True
    return False


def classify_hit(hit: Dict[str, Any]) -> str:
    """
    Classify one hit: 'reason' | 'book' | 'other'
    Priority:
      1) 이유문법/깨알문법
      2) 문법서적
    """
    path = str(hit.get("path", "")).strip()
    title = str(hit.get("title", "")).strip()
    name = Path(path).name if path else title
    text = _gather_text_fields(hit)

    # strong rule: filename/title prefix
    if _is_reason_grammar(name):
        return "reason"

    # prepared path + reason hints (mild boost)
    if "/prepared/" in text and any(k in text for k in _REASON_KEYS):
        return "reason"

    if _is_book_material(path, title):
        return "book"

    # KO/EN hints in other fields
    if any(k in text for k in _KO_BOOK_HINTS) or any(k in text for k in _EN_BOOK_HINTS):
        return "book"

    return "other"


# ------------------------------ label decision ------------------------------
def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    Hard-guarded priority:
      1) [이유문법] — reason/깨알문법 단서가 1개라도 있으면 최우선
      2) [문법서적] — pdf/book/grammar/출판사·시험기관 힌트
      3) [AI지식]  — 히트 없음/판단 불가
    """
    items = list(hits or [])
    if not items:
        return default_if_none

    for h in items:
        if classify_hit(h) == "reason":
            return "[이유문법]"

    for h in items:
        if classify_hit(h) == "book":
            return "[문법서적]"

    return default_if_none


def make_source_chip(hits: Iterable[Dict[str, Any]] | None, label: str) -> str:
    """
    UI chip text: keep concise. For now, return only the label.
    (Can be extended to append a single representative title.)
    """
    return canonicalize_label(label)
# [01] END: src/rag/label.py
