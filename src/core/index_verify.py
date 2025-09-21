# ===== [PATCH] FILE: src/core/index_verify.py — START =====
from __future__ import annotations
from pathlib import Path

from src.core.readiness import is_ready_text  # ✅ 단일 규칙 재사용

def verify_persist_dir(persist: Path) -> bool:
    """
    단순 구조 검증: chunks.jsonl 존재/비어있지 않음 + .ready 텍스트가 유효.
    (이 모듈의 기존 공개 API가 다르면 동일 시그니처 함수에서 아래 내용을 사용하도록 옮기세요.)
    """
    chunks = persist / "chunks.jsonl"
    ready  = persist / ".ready"
    try:
        txt = ready.read_text(encoding="utf-8") if ready.exists() else ""
    except Exception:
        txt = ""
    return chunks.exists() and chunks.stat().st_size > 0 and is_ready_text(txt)
# ===== [PATCH] FILE: src/core/index_verify.py — END =====
