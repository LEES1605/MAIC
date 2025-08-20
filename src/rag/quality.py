
# ===== [01] IMPORTS & CONSTS =================================================
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Set, Tuple

from src.compat.config_bridge import QUALITY_REPORT_PATH
from src.compat.llama import Document

log = logging.getLogger(__name__)
_WS_RE = re.compile(r"[ \t\f\v]+")

# ===== [02] TEXT CLEANERS ====================================================
def _clean_text(s: str) -> str:
    """
    공백/개행을 정돈하고 불필요한 연속 개행/스페이스를 제거합니다.
    """
    s = s.replace("\u00a0", " ").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()

# ===== [03] HASH HELPERS (Bandit-safe) ======================================
def _sha256_hex(s: str) -> str:
    """
    문서 텍스트의 SHA-256 해시(hex)를 반환합니다.
    (B303: insecure hash 경고를 피하기 위해 sha256 사용)
    """
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

# ===== [04] DOCUMENT UTIL ====================================================
def _clone_with_text_and_meta(d: Any, new_text: str, new_meta: Dict[str, Any]) -> Document:
    """
    원본 객체의 메타데이터를 보존/병합하여 새 Document 인스턴스를 생성합니다.
    """
    try:
        md = dict(getattr(d, "metadata", {}) or {})
        md.update(new_meta)
    except Exception:
        md = dict(new_meta)
    return Document(text=new_text, metadata=md)

# ===== [05] PREPROCESS / DEDUP ==============================================
def preprocess_docs(
    docs: List[Any],
    seen_hashes: Set[str],
    min_chars: int,
    dedup: bool,
) -> Tuple[List[Document], Dict[str, Any]]:
    """
    - 텍스트 정리(_clean_text)
    - 최소 글자수 필터(min_chars)
    - 중복 제거(dedup=True이면 동일 해시 건너뜀)
    - 결과와 간단 통계를 반환
    """
    kept: List[Document] = []
    stats: Dict[str, Any] = {
        "input_docs": len(docs),
        "kept": 0,
        "skipped_low_text": 0,
        "skipped_dup": 0,
        "total_chars": 0,
    }

    for d in docs:
        raw = getattr(d, "text", "") or ""
        t = _clean_text(raw)

        if len(t) < int(min_chars):
            stats["skipped_low_text"] += 1
            continue

        h = _sha256_hex(t)
        if dedup and h in seen_hashes:
            stats["skipped_dup"] += 1
            continue

        md: Dict[str, Any] = dict(getattr(d, "metadata", {}) or {})
        md["text_hash"] = h

        kept.append(_clone_with_text_and_meta(d, t, md))
        seen_hashes.add(h)
        stats["kept"] += 1
        stats["total_chars"] += len(t)

    return kept, stats

# ===== [06] QUALITY REPORT I/O ==============================================
def load_quality_report(path: str | None = None) -> Dict[str, Any]:
    """
    품질 리포트를 JSON으로부터 로드합니다.
    실패 시 빈 구조를 반환합니다(런타임을 막지 않음).
    """
    target = path or str(QUALITY_REPORT_PATH or "quality_report.json")
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.debug("quality report load failed: %r", e)
        return {"summary": {}, "files": {}}

def save_quality_report(data: Dict[str, Any], path: str | None = None) -> None:
    """
    품질 리포트를 JSON으로 저장합니다.
    디렉터리가 없으면 생성합니다.
    """
    target = path or str(QUALITY_REPORT_PATH or "quality_report.json")
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception as e:
        log.debug("quality report save failed: %r", e)

# ===== [07] OPTIONAL: DOC SUMMARIZER (SAFE NO-OP) ============================
def maybe_summarize_docs(docs: List[Document], enabled: bool = False, max_chars: int = 4000) -> None:
    """
    옵션이 켜진 경우에만 문서를 간단 요약하여 metadata['doc_summary']에 저장합니다.
    실패는 무시하되 로그만 남깁니다(전체 파이프라인을 멈추지 않음).
    """
    if not enabled or not docs:
        return
    try:
        # LlamaIndex Settings가 있을 때만 사용 (mypy: ignore는 설정에서 무시)
        from llama_index.core import Settings  # type: ignore[import]

        for idx, d in enumerate(list(docs)):
            md = dict(getattr(d, "metadata", {}) or {})
            if "doc_summary" in md:
                continue
            text = (getattr(d, "text", "") or "")[:max_chars]
            if not text:
                continue

            prompt = (
                "다음 문서를 교사 시각에서 5줄 이내 핵심 bullet로 요약하라.\n"
                "교재 단원/개념/예문/핵심 규칙을 간단히 표시하라.\n\n"
                f"[문서 내용]\n{text}"
            )
            try:
                resp = Settings.llm.complete(prompt)
                summary = getattr(resp, "text", None) or str(resp)
                md["doc_summary"] = summary.strip()
                docs[idx] = Document(text=getattr(d, "text", ""), metadata=md)
            except Exception as e:  # 요약 실패는 무시하고 기록만 남김
                log.debug("summarize failed (ignored): %r", e)
    except Exception as e:
        log.debug("Settings import failed (ignored): %r", e)

# ===== [08] EXPORTS ==========================================================
__all__ = [
    "preprocess_docs",
    "load_quality_report",
    "save_quality_report",
    "maybe_summarize_docs",
]
# ===== [09] END ==============================================================
