# ===== [01] PURPOSE ==========================================================
# LlamaIndex 호환 레이어: 프로젝트 전체는 여기서만 Document를 가져온다.
# 사용: from src.compat.llama import Document, DocumentType

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, TypeAlias


# ===== [03] TYPING SURFACE (INSTANCE SHAPE) ==================================
class _DocumentInstance(Protocol):
    text: str
    metadata: Dict[str, object]


# 문서 "인스턴스" 타입(타입 힌트 전용)
DocumentType: TypeAlias = _DocumentInstance


# ===== [04] RUNTIME BINDING (SINGLE NAME) ====================================
# 런타임에서 사용할 "클래스" 이름은 오직 하나: Document
Document: type[Any]

try:
    # 0.12.x+
    from llama_index.core.schema import Document as _DocSchema
    Document = _DocSchema
except Exception:
    try:
        # older versions
        from llama_index.core import Document as _DocCore
        Document = _DocCore
    except Exception:
        class _StubDocument:
            def __init__(
                self,
                text: str = "",
                metadata: Optional[Dict[str, object]] = None,
            ) -> None:
                self.text = text
                self.metadata = metadata or {}

        Document = _StubDocument


# ===== [05] EXPORTS ==========================================================
__all__ = ["Document", "DocumentType"]

# ===== [06] END ==============================================================
