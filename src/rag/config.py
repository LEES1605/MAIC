# [03] START: src/rag/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .engine import NoopRagEngine, RagDoc, RagEngine
from .engine_hash import HashRagEngine
from .engine_bm25 import Bm25RagEngine


_ENV_KEY = "MAIC_RAG_ENGINE"  # 'hash' | 'bm25' | 'disabled'
_FIXTURE = Path("tests/fixtures/rag_fixture.jsonl")


def _load_fixture() -> List[RagDoc]:
    if not _FIXTURE.exists():
        return []
    docs: List[RagDoc] = []
    with _FIXTURE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            import json

            d = json.loads(line)
            docs.append(
                RagDoc(
                    doc_id=str(d["id"]),
                    title=str(d["title"]),
                    text=str(d["text"]),
                )
            )
    return docs


def get_engine() -> RagEngine:
    mode = (os.getenv(_ENV_KEY) or "hash").strip().lower()
    if mode == "disabled":
        return NoopRagEngine()
    if mode == "bm25":
        eng: RagEngine = Bm25RagEngine()
    else:
        eng = HashRagEngine()

    docs = _load_fixture()
    if docs:
        eng.index(docs)
    return eng
# [03] END: src/rag/config.py
