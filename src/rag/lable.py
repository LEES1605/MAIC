# ============================ [01] RAG LABELER (MVP) — START ============================
"""
간단한 출처 라벨러
- hits: RAG 검색 결과(없어도 안전)
- decide_label: 히트가 있으면 [이유문법]/[문법책], 없으면 [AI지식]
- search_hits: MVP에서는 빈 리스트 또는 간단 규칙 기반(추후 인덱스 연결)
"""

from __future__ import annotations
from typing import Any, Iterable, List, Dict

def decide_label(hits: Iterable[Dict[str, Any]] | None, default_if_none: str = "[AI지식]") -> str:
    try:
        items = list(hits or [])
        if not items:
            return default_if_none
        src_set = {str(x.get("source", "")).lower() for x in items}
        if "iyu" in src_set or "reason-grammar" in src_set or "iyu-grammar" in src_set:
            return "[이유문법]"
        if "book" in src_set or "textbook" in src_set:
            return "[문법책]"
        return "[AI지식]"
    except Exception:
        return default_if_none

def search_hits(query: str) -> List[Dict[str, Any]]:
    """
    MVP: 아직 실제 인덱스 연결 전.
    - '이유문법'/'문법책' 키워드가 들어오면 가짜 히트 1건 반환(데모)
    - 그렇지 않으면 빈 리스트
    """
    q = (query or "").lower()
    if "이유문법" in q:
        return [{"source": "iyu", "title": "이유문법(데모)", "page": None}]
    if "문법책" in q or "교과서" in q or "textbook" in q:
        return [{"source": "book", "title": "문법책(데모)", "page": None}]
    return []
# ============================= [01] RAG LABELER (MVP) — END =============================
