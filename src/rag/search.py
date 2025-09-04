# ============================ [01] SIMPLE RAG SEARCH — START ============================
"""
표준 라이브러리만으로 동작하는 경량 RAG 검색기.
- 지원 확장자: .md, .txt (그 외는 건너뜀)
- 인덱스 저장: JSON(선택). 저장하지 않아도 메모리에서 즉시 검색 가능.
- 토크나이즈: 영문/숫자/한글을 단어로 인식 (정규식)
- 스코어: 간단한 TF-IDF
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

SUPPORTED_EXTS = {".md", ".txt"}
TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")


@dataclass
class Doc:
    id: int
    path: str
    title: str
    text: str


def _read_text(path: Path) -> str:
    # 인코딩 추정(실패하면 공백 반환)
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    return ""


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def _title_from_path(p: Path) -> str:
    return p.stem.replace("_", " ").replace("-", " ").strip() or p.name


def build_index(dataset_dir: str) -> Dict:
    """dataset_dir를 순회하여 간단한 역색인을 구성해 dict로 반환."""
    base = Path(dataset_dir)
    docs: List[Doc] = []
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            docs.append(
                Doc(
                    id=len(docs),
                    path=str(p),
                    title=_title_from_path(p),
                    text=_read_text(p),
                )
            )

    # 역색인과 df 계산
    postings: Dict[str, Dict[int, int]] = {}
    df: Dict[str, int] = {}
    for d in docs:
        toks = _tokenize(d.text)
        if not toks:
            continue
        tf_local: Dict[str, int] = {}
        for t in toks:
            tf_local[t] = tf_local.get(t, 0) + 1
        for t, tf in tf_local.items():
            postings.setdefault(t, {})[d.id] = tf
            df[t] = df.get(t, 0) + 1

    return {
        "docs": [{"id": d.id, "path": d.path, "title": d.title} for d in docs],
        "df": df,
        "postings": postings,
        "meta": {"N": len(docs)},
    }


def save_index(index: Dict, persist_path: str) -> None:
    Path(persist_path).parent.mkdir(parents=True, exist_ok=True)
    with open(persist_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)


def load_index(persist_path: str) -> Dict:
    with open(persist_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _idf(N: int, df: int) -> float:
    return math.log((N + 1) / (df + 1)) + 1.0


def _make_snippet(text: str, needle: str, width: int = 120) -> str:
    if not text:
        return ""
    text_l = text.replace("\n", " ")
    pos = text_l.lower().find(needle.lower())
    if pos < 0:
        base = text_l[:width]
        return base + ("…" if len(text_l) > width else "")
    start = max(0, pos - width // 2)
    end = min(len(text_l), pos + width // 2)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text_l) else ""
    return f"{prefix}{text_l[start:end]}{suffix}"


def search(
    query: str,
    *,
    dataset_dir: Optional[str] = None,
    index: Optional[Dict] = None,
    top_k: int = 5,
) -> List[Dict]:
    """
    query로 상위 top_k 문서를 반환.
    반환: [{"path","title","score","snippet"} ...]
    """
    if index is None:
        if not dataset_dir:
            return []
        index = build_index(dataset_dir)

    docs = {d["id"]: d for d in index.get("docs", [])}
    df = index.get("df", {})
    postings = index.get("postings", {})
    N = int(index.get("meta", {}).get("N", 1) or 1)

    q_toks = _tokenize(query)
    if not q_toks:
        return []

    # 쿼리 tf
    q_tf: Dict[str, int] = {}
    for t in q_toks:
        q_tf[t] = q_tf.get(t, 0) + 1

    scores: Dict[int, float] = {}
    for t, qtf in q_tf.items():
        if t not in postings:
            continue
        idf = _idf(N, df.get(t, 0))
        for doc_id, tf in postings[t].items():
            scores[doc_id] = scores.get(doc_id, 0.0) + (tf * idf * qtf)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results: List[Dict] = []
    # 스니펫 생성을 위해 텍스트를 다시 읽음(인덱스에는 본문 저장 안함)
    for doc_id, sc in ranked:
        path = docs[doc_id]["path"]
        title = docs[doc_id]["title"]
        try:
            text = _read_text(Path(path))
        except Exception:
            text = ""
        # 첫 쿼리 토큰으로 스니펫
        snippet = _make_snippet(text, q_toks[0]) if text else ""
        results.append({"path": path, "title": title, "score": sc, "snippet": snippet})
    return results
# ============================= [01] SIMPLE RAG SEARCH — END =============================
