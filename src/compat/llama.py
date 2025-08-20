# ===== [01] PURPOSE ==========================================================
# LlamaIndex 호환 레이어: 프로젝트 전체는 여기서만 Document를 가져온다.

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations
from typing import Any, Dict, Optional

# ===== [03] DOCUMENT RESOLUTION =============================================
try:
    # 0.12.x+
    from llama_index.core.schema import Document as _LIDocument  # type: ignore[assignment]
except Exception:
    try:
        # older versions
        from llama_index.core import Document as _LIDocument  # type: ignore[assignment]
    except Exception:
        class _LIDocument:
            def __init__(self, text: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
                self.text = text
                self.metadata = metadata or {}

# ===== [04] SINGLE BINDING / EXPORT =========================================
Document = _LIDocument
__all__ = ["Document"]
# ===== [05] END ==============================================================
