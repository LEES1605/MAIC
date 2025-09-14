# [10] START: tests/test_rag_engine_bm25.py
from __future__ import annotations

from src.rag.config import get_engine


def test_bm25_retrieves_expected_for_it_that(monkeypatch) -> None:
    monkeypatch.setenv("MAIC_RAG_ENGINE", "bm25")
    eng = get_engine()
    hits = eng.search("It was John that broke the window.", k=1)
    assert hits and hits[0].doc_id == "d2"


def test_bm25_retrieves_expected_for_more_more(monkeypatch) -> None:
    monkeypatch.setenv("MAIC_RAG_ENGINE", "bm25")
    eng = get_engine()
    hits = eng.search("the more we study the more confident", k=1)
    assert hits and hits[0].doc_id == "d1"
# [10] END: tests/test_rag_engine_bm25.py
