# ============================ [01] SIMPLE RAG SEARCH — START ============================
"""
경량 RAG 검색기.

- 지원 확장자: .md, .txt, .pdf
- 인덱스 저장: JSON(선택). 저장하지 않아도 메모리에서 즉시 검색 가능.
- 토크나이즈: 영문/숫자/한글을 단어로 인식 (정규식)
- 스코어: 간단한 TF-IDF
- 한국어 토큰 정규화: 대표 조사(예: 은/는/이/가/을/를/과/와/로/의/도/만/
  에게/한테/에서/부터/까지 등)를 제거
- PDF 처리:
  * PyPDF2 등이 설치되어 있으면 본문을 추출
  * 미설치/추출 실패 시, 파일명(제목)만으로 최소 인덱싱
"""

from __future__ import annotations

import json
import math
import os
import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_EXTS = {".md", ".txt", ".pdf"}
TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")

# 말단 조사(길이 긴 것 → 짧은 것 순서) — 과도 절단 방지(토큰 길이 체크)
_KR_SUFFIXES = [
    "으로써",
    "으로서",
    "에게서",
    "한테서",
    "로부터",
    "부터",
    "까지",
    "이라고",
    "라고",
    "이며",
    "이고",
    "에게",
    "한테",
    "에서",
    "으로",
    "처럼",
    "보다",
    "과",
    "와",
    "로",
    "의",
    "도",
    "만",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
]


@dataclass
class Doc:
    id: int
    path: str
    title: str
    text: str


def _read_text_pdf(path: Path) -> str:
    """
    PDF 텍스트 추출(가능하면). 실패 시 빈 문자열 반환.
    외부 라이브러리가 없을 수 있으므로 예외를 모두 잡아 폴백합니다.
    """
    try:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            PdfReader = None  # type: ignore
        if PdfReader is not None:
            txt_parts: List[str] = []
            reader = PdfReader(str(path))
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                if t:
                    txt_parts.append(t)
            return "\n".join(txt_parts).strip()
    except Exception:
        pass
    return ""


# ====================== [01] PATCH: _read_text_pdf — START ======================
def _read_text_pdf(path: Path) -> str:
    """
    PDF 텍스트 추출(가능하면). 실패 시 빈 문자열 반환.
    외부 라이브러리가 없을 수 있으므로 예외를 모두 잡아 폴백합니다.
    """
    try:
        try:
            from PyPDF2 import PdfReader  # 외부 라이브러리 사용 가능 시
        except Exception:
            PdfReader = None
        if PdfReader is not None:
            txt_parts: List[str] = []
            reader = PdfReader(str(path))
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                if t:
                    txt_parts.append(t)
            return "\n".join(txt_parts).strip()
    except Exception:
        pass
    return ""
# ======================= [01] PATCH: _read_text_pdf — END =======================


def _normalize_token(tok: str) -> str:
    """한국어 토큰 말단 조사 제거(너무 짧아지지 않도록 길이 체크)."""
    t = tok.lower()
    for suf in _KR_SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 2:
            return t[: -len(suf)]
    return t


def _tokenize_norm(text: str) -> List[str]:
    toks = [m.group(0) for m in TOKEN_RE.finditer(text)]
    norm = [_normalize_token(t) for t in toks]
    return [t for t in norm if t]


def _title_from_path(p: Path) -> str:
    return p.stem.replace("_", " ").replace("-", " ").strip() or p.name


def build_index(dataset_dir: str) -> Dict:
    """
    dataset_dir를 순회하여 간단한 역색인을 구성해 dict로 반환.
    - PDF는 텍스트 추출 실패 시 파일명(제목)만으로 최소 인덱싱합니다.
    """
    base = Path(dataset_dir)
    docs: List[Doc] = []
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            raw = _read_text(p)
            title = _title_from_path(p)
            if not raw and p.suffix.lower() == ".pdf":
                raw = title
            docs.append(Doc(id=len(docs), path=str(p), title=title, text=raw))

    postings: Dict[str, Dict[int, int]] = {}
    df: Dict[str, int] = {}
    for d in docs:
        toks = _tokenize_norm(d.text)
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

    q_toks = _tokenize_norm(query)
    if not q_toks:
        return []

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
    for doc_id, sc in ranked:
        path = docs[doc_id]["path"]
        title = docs[doc_id]["title"]
        try:
            text = _read_text(Path(path))
        except Exception:
            text = ""
        needle = q_toks[0]
        snippet = _make_snippet(text, needle) if text else ""
        results.append({"path": path, "title": title, "score": sc, "snippet": snippet})
    return results
# ============================= [01] SIMPLE RAG SEARCH — END =============================

# ========================= [02] PERSISTENT CACHE LAYER — START =========================
# RAG 인덱스 캐시/지속화 레이어:
# - 데이터셋 파일 목록·크기·mtime을 해시(sha1)로 요약해 '시그니처' 생성
# - 동일 시그니처면 디스크에 저장된 인덱스를 재사용
# - 다르면 재빌드 후 저장
# - 캐시 경로: ~/.maic/persist/rag_cache/<sha1(absdir)>__<sig>.json

def _default_persist_dir() -> Path:
    return Path("~/.maic/persist").expanduser()


def _cache_dir() -> Path:
    p = _default_persist_dir() / "rag_cache"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def _dataset_signature(dataset_dir: str) -> str:
    base = Path(dataset_dir)
    h = hashlib.sha1()
    try:
        items: List[Tuple[str, int, int]] = []
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                stat = p.stat()
                rel = str(p.relative_to(base)).replace(os.sep, "/")
                items.append((rel, int(stat.st_size), int(stat.st_mtime)))
        payload = json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        h.update(payload)
    except Exception:
        h.update(b"fallback")
    return h.hexdigest()


def _cache_path_for(dataset_dir: str) -> Path:
    abs_dir = str(Path(dataset_dir).expanduser().resolve())
    head = hashlib.sha1(abs_dir.encode("utf-8")).hexdigest()
    sig = _dataset_signature(dataset_dir)
    name = f"{head}__{sig}.json"
    return _cache_dir() / name


def get_or_build_index(dataset_dir: str, *, use_cache: bool = True) -> Dict:
    """
    캐시 사용 시:
      1) 시그니처 기반 파일명을 계산
      2) 동일 파일이 있으면 load → 반환
      3) 없으면 build_index → 저장 → 반환
    """
    if not use_cache:
        return build_index(dataset_dir)

    cpath = _cache_path_for(dataset_dir)
    if cpath.exists():
        try:
            return load_index(str(cpath))
        except Exception:
            pass

    idx = build_index(dataset_dir)
    try:
        save_index(idx, str(cpath))
    except Exception:
        pass
    return idx
# ========================== [02] PERSISTENT CACHE LAYER — END ==========================

# ========================= [03] REBUILD API — START =========================
def rebuild_and_cache(dataset_dir: str) -> Dict:
    """
    데이터셋을 '항상' 새로 인덱싱하고, 디스크 캐시에 저장 후 인덱스를 반환합니다.
    관리자 모드에서 강제 재인덱싱이 필요할 때 사용하세요.
    """
    idx = build_index(dataset_dir)
    try:
        cpath = _cache_path_for(dataset_dir)
        save_index(idx, str(cpath))
    except Exception:
        pass
    return idx
# ========================== [03] REBUILD API — END ==========================
