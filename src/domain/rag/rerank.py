# [01] START: src/rag/rerank.py (NEW FILE)
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from pathlib import Path

Classifier = Callable[[Dict[str, Any]], str]


def _doc_key(hit: Dict[str, Any]) -> str:
    """문서 단위 중복 제거용 고유키."""
    path = str(hit.get("path") or "").strip()
    if path:
        return path
    # fallback 키들
    for k in ("doc_id", "source", "title", "url", "file", "name"):
        v = str(hit.get(k) or "").strip()
        if v:
            return v
    return repr(sorted(hit.keys()))


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _evidence_boost_by_class(hit: Dict[str, Any], classifier: Optional[Classifier]) -> float:
    """
    분류 결과에 따른 가중치.
    - reason(이유문법/깨알문법)   : +0.50
    - book(문법서/grammar 계열)   : +0.20
    - other                       : +0.00
    """
    label = ""
    try:
        if callable(classifier):
            label = classifier(hit)
    except Exception:
        label = ""
    if label == "reason":
        return 0.50
    if label == "book":
        return 0.20
    return 0.0


def evidence_score(
    hit: Dict[str, Any],
    *,
    classifier: Optional[Classifier] = None,
) -> float:
    """
    근거성 점수(0..+∞ 실수, 상대 비교용):
      base = 검색 엔진 score(없으면 0)
      boost = 분류 가중치(이유문법/문법서)
      total = base + boost
    """
    base = _to_float(hit.get("score"), 0.0)
    boost = _evidence_boost_by_class(hit, classifier)
    return base + boost


def dedupe_hits(
    hits: Iterable[Dict[str, Any]],
    *,
    classifier: Optional[Classifier] = None,
) -> List[Dict[str, Any]]:
    """
    문서 단위로 중복 제거.
    - 같은 doc_key 안에서는 evidence_score가 높은 히트를 유지.
    - 원본 히트 dict는 그대로 반환(사본 생성하지 않음).
    """
    best: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    for h in hits or []:
        key = _doc_key(h)
        score = evidence_score(h, classifier=classifier)
        prev = best.get(key)
        if prev is None or score > prev[0]:
            best[key] = (score, h)
    return [v[1] for v in best.values()]


def rerank_hits(
    hits: Iterable[Dict[str, Any]],
    *,
    top_k: int = 5,
    classifier: Optional[Classifier] = None,
) -> List[Dict[str, Any]]:
    """
    재랭킹 파이프라인:
      1) 문서 단위 중복 제거
      2) evidence_score로 내림차순 소팅
      3) 상위 top_k 반환
    """
    cleaned = dedupe_hits(hits, classifier=classifier)
    scored: List[Tuple[float, Dict[str, Any]]] = [
        (evidence_score(h, classifier=classifier), h) for h in cleaned
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [h for _s, h in scored[: max(1, int(top_k))]]
    return out
# [01] END: src/rag/rerank.py
