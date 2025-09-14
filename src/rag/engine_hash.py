# [02] START: src/rag/engine_hash.py
from __future__ import annotations

import math
from dataclasses import dataclass
from hashlib import blake2b
from typing import Dict, Iterable, List, Tuple

from .engine import RagDoc, RagEngine, RagHit


_DIM = 256  # 고정 차원(결정적)
_SNIPPET_LEN = 160


def _tokenize(text: str) -> List[str]:
    return [t for t in text.lower().split() if t]


def _hash_token(tok: str) -> int:
    # blake2b로 안정적 해시 → 64bit 정수
    h = blake2b(tok.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "little", signed=False)


def _embed(text: str) -> List[float]:
    vec = [0.0] * _DIM
    toks = _tokenize(text)
    if not toks:
        return vec
    for t in toks:
        h = _hash_token(t)
        idx = h % _DIM
        sign = 1.0 if (h >> 63) == 0 else -1.0  # 부호 플립으로 충돌 완화
        vec[idx] += sign
    # L2 정규화
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cos(a: List[float], b: List[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


@dataclass
class _DocVec:
    doc: RagDoc
    vec: List[float]


class HashRagEngine(RagEngine):
    """외부 의존성 없는 경량 임베딩 기반 검색 엔진(결정적)."""

    def __init__(self) -> None:
        self._vecs: List[_DocVec] = []

    def index(self, docs: Iterable[RagDoc]) -> None:
        self._vecs = []
        for d in docs:
            self._vecs.append(_DocVec(doc=d, vec=_embed(d.text)))

    def search(self, query: str, k: int = 3) -> List[RagHit]:
        qv = _embed(query)
        scored: List[Tuple[float, _DocVec]] = []
        for dv in self._vecs:
            s = _cos(qv, dv.vec)
            scored.append((s, dv))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits: List[RagHit] = []
        for s, dv in scored[: max(1, k)]:
            snip = (dv.doc.text[:_SNIPPET_LEN] + "...") if len(dv.doc.text) > _SNIPPET_LEN else dv.doc.text
            hits.append(RagHit(doc_id=dv.doc.doc_id, score=float(s), title=dv.doc.title, snippet=snip))
        return hits
# [02] END: src/rag/engine_hash.py
