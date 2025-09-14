# [03] START: src/rag/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from .engine import NoopRagEngine, RagDoc, RagEngine
from .engine_hash import HashRagEngine


_ENV_KEY = "MAIC_RAG_ENGINE"  # 'hash' | 'disabled'
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
            # {"id": "...", "title": "...", "text": "..."}
            import json

            d = json.loads(line)
            docs.append(RagDoc(doc_id=str(d["id"]), title=str(d["title"]), text=str(d["text"])))
    return docs


def get_engine() -> RagEngine:
    mode = (os.getenv(_ENV_KEY) or "hash").strip().lower()
    if mode == "disabled":
        return NoopRagEngine()
    # 기본: 결정적 해싱 엔진
    eng = HashRagEngine()
    # CI/테스트의 안정성을 위해 픽스처를 자동 인덱싱(존재하는 경우에만)
    docs = _load_fixture()
    if docs:
        eng.index(docs)
    return eng
# [03] END: src/rag/config.py
