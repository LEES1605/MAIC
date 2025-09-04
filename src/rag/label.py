# ============================ [01] RAG LABELER — START ============================
"""
출처 라벨러
- search_hits: 경량 RAG(search.py)를 사용해 prepared/ 또는 RAG_DATASET_DIR에서 검색
- decide_label: 히트의 경로/제목/소스 키워드로 [이유문법]/[문법책]/[AI지식] 판정
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# 경량 RAG 검색기
from src.rag import search as _rag


def _project_root() -> Path:
    """
    src/rag/label.py 기준으로 프로젝트 루트 추정.
    .../src/rag/label.py → parents[2] == repo root 로 가정.
    """
    return Path(__file__).resolve().parents[2]


def _prepared_dir() -> Path:
    """
    기본 코퍼스 위치 추정: <repo>/prepared
    (없으면 빈 결과 반환하게 두고, 테스트/CI에서는 tmp 코퍼스로 동작)
    """
    return _project_root() / "prepared"


def search_hits(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    질의어로 상위 히트들을 반환.
    - 우선순위: 인자 dataset_dir > 환경변수 RAG_DATASET_DIR > <repo>/prepared
    - 반환: [{"path","title","score","snippet","source"} ...]
    """
    q = (query or "").strip()
    if not q:
        return []

    # 코퍼스 위치 결정
    base_dir = (
        Path(dataset_dir)
        if dataset_dir
        else Path(os.getenv("RAG_DATASET_DIR", ""))
    )
    if not str(base_dir):
        base_dir = _prepared_dir()

    if not base_dir.exists():
        return []

    # 인덱스 빌드 및 검색
    try:
        idx = _rag.build_index(str(base_dir))
        hits = _rag.search(q, index=idx, top_k=int(top_k))
    except Exception:
        return []

    # 각 히트에 source 필드 보강(라벨 판정 근거)
    out: List[Dict[str, Any]] = []
    for h in hits:
        path = str(h.get("path", "")).lower()
        title = str(h.get("title", "")).lower()
        hay = f"{path} {title}"

        if any(k in hay for k in ("iyu", "이유문법", "reason-grammar", "iyu-grammar")):
            src = "iyu"
        elif any(k in hay for k in ("book", "문법책", "교과서", "textbook")):
            src = "book"
        else:
            src = "other"

        out.append(
            {
                "path": h.get("path"),
                "title": h.get("title"),
                "score": h.get("score"),
                "snippet": h.get("snippet"),
                "source": src,
            }
        )
    return out


def decide_label(
    hits: Iterable[Dict[str, Any]] | None,
    default_if_none: str = "[AI지식]",
) -> str:
    """
    히트가 있을 경우 경로/제목/소스 키워드로 라벨 판정.
    - [이유문법] 키워드(iyu/이유문법 등)가 보이면 우선.
    - 다음으로 [문법책]/[교과서]/textbook 등.
    - 없으면 [AI지식].
    """
    try:
        items = list(hits or [])
        if not items:
            return default_if_none

        # 상위 1개를 우선 참고(스코어가 가장 높음)
        top = items[0]
        path = str(top.get("path", "")).lower()
        title = str(top.get("title", "")).lower()
        src = str(top.get("source", "")).lower()
        hay = f"{path} {title} {src}"

        if any(k in hay for k in ("iyu", "이유문법", "reason-grammar", "iyu-grammar")):
            return "[이유문법]"
        if any(k in hay for k in ("book", "문법책", "교과서", "textbook")):
            return "[문법책]"
        return default_if_none
    except Exception:
        return default_if_none
# ============================= [01] RAG LABELER — END =============================
