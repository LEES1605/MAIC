# [09] START: src/rag/engine_bm25.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .engine import RagDoc, RagEngine, RagHit


_SNIPPET_LEN = 160
_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> List[str]:
    return [t for t in text.lower().split() if t]


def _snippet(text: str) -> str:
    return text[:_SNIPPET_LEN] + "..." if len(text) > _SNIPPET_LEN else text


@dataclass
class _InvPost:
    doc_id: str
    tf: int


class Bm25RagEngine(RagEngine):
    """
    순수 파이썬 BM25 검색 엔진(결정적·무의존).
    - 인덱스: 토큰 → [문서 posting], 각 문서 길이, 문서수 N, 토큰 df
    - 검색: 표준 BM25(k1, b) 합산 점수
    """

    def __init__(self) -> None:
        self._N: int = 0
        self._avg_len: float = 0.0
        self._doc_len: Dict[str, int] = {}
        self._postings: Dict[str, List[_InvPost]] = {}
        self._df: Dict[str, int] = {}
        self._docs: Dict[str, RagDoc] = {}

    def index(self, docs: Iterable[RagDoc]) -> None:
        self._N = 0
        self._avg_len = 0.0
        self._doc_len.clear()
        self._postings.clear()
        self._df.clear()
        self._docs.clear()

        total_len = 0
        for d in docs:
            toks = _tokenize(d.text)
            self._docs[d.doc_id] = d
            self._doc_len[d.doc_id] = len(toks)
            total_len += len(toks)
            tf_map: Dict[str, int] = {}
            for t in toks:
                tf_map[t] = tf_map.get(t, 0) + 1
            for t, tf in tf_map.items():
                self._postings.setdefault(t, []).append(_InvPost(doc_id=d.doc_id, tf=tf))
            self._N += 1

        if self._N > 0:
            self._avg_len = total_len / self._N
        for t, posts in self._postings.items():
            self._df[t] = len(posts)

    def _bm25(self, tf: int, df: int, dl: int) -> float:
        # Robertson/Sparck Jones BM25
        idf = math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)
        denom = tf + _K1 * (1.0 - _B + _B * (dl / (self._avg_len or 1.0)))
        return idf * (tf * (_K1 + 1.0)) / (denom or 1.0)

    def search(self, query: str, k: int = 3) -> List[RagHit]:
        q_toks = _tokenize(query)
        scores: Dict[str, float] = {}

        for t in q_toks:
            posts = self._postings.get(t)
            if not posts:
                continue
            df = self._df.get(t, 0)
            for p in posts:
                dl = self._doc_len.get(p.doc_id, 0)
                scores[p.doc_id] = scores.get(p.doc_id, 0.0) + self._bm25(p.tf, df, dl)

        ranked: List[Tuple[str, float]] = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )
        hits: List[RagHit] = []
        for doc_id, s in ranked[: max(1, k)]:
            d = self._docs[doc_id]
            hits.append(
                RagHit(
                    doc_id=doc_id,
                    score=float(s),
                    title=d.title,
                    snippet=_snippet(d.text),
                )
            )
        return hits
# [09] END: src/rag/engine_bm25.py
