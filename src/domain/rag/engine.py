# [01] START: src/rag/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class RagDoc:
    doc_id: str
    title: str
    text: str


@dataclass(frozen=True)
class RagHit:
    doc_id: str
    score: float
    title: str
    snippet: str


class RagEngine(Protocol):
    """RAG 검색 엔진 프로토콜. 구현체는 순수 파이썬만으로 동작해야 함."""

    def index(self, docs: Iterable[RagDoc]) -> None:
        """메모리 인덱스를 구성한다(덮어쓰기)."""

    def search(self, query: str, k: int = 3) -> List[RagHit]:
        """Top‑k 문서를 점수 내림차순으로 반환한다."""


class NoopRagEngine:
    """엔진 비활성화 상태용: 항상 빈 결과를 반환한다."""

    def index(self, docs: Iterable[RagDoc]) -> None:  # noqa: D401
        return None

    def search(self, query: str, k: int = 3) -> List[RagHit]:  # noqa: D401
        return []
# [01] END: src/rag/engine.py
