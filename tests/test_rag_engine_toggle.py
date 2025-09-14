# [05] START: tests/test_rag_engine_toggle.py
from __future__ import annotations

import os

from src.rag.config import get_engine


def test_rag_disabled_returns_empty(monkeypatch) -> None:
    monkeypatch.setenv("MAIC_RAG_ENGINE", "disabled")
    eng = get_engine()
    assert eng.search("any query", k=3) == []


def test_rag_hash_retrieves_expected(monkeypatch) -> None:
    monkeypatch.setenv("MAIC_RAG_ENGINE", "hash")
    eng = get_engine()
    # 'It~that 강조' 문장 질의 → d2가 가장 먼저 나와야 함
    hits = eng.search("It was John that broke the window.", k=1)
    assert hits and hits[0].doc_id == "d2"
# [05] END: tests/test_rag_engine_toggle.py
