# ===== [01] PURPOSE ==========================================================
# LlamaIndex 호환 레이어: 프로젝트 전체는 여기서만 Document를 가져온다.
# from src.compat.llama import Document

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

from typing import Dict, Optional

# ===== [03] DOCUMENT RESOLUTION =============================================
try:
    # 0.12.x+
    from llama_index.core.schema import Document as _LIDocument  # type: ignore[assignment]
except Exception:
    try:
        # older versions
        from llama_index.core import Document as _LIDocument  # type: ignore[assignment]
    except Exception:
        class _LIDocument:  # 최소 스텁(타입/런타임 안전)
            def __init__(self, text: str = "", metadata: Optional[Dict[str, object]] = None) -> None:
                self.text = text
                self.metadata = metadata or {}

# ===== [04] SINGLE BINDING / EXPORT =========================================
Document = _LIDocument
__all__ = ["Document"]
# ===== [05] END ==============================================================
