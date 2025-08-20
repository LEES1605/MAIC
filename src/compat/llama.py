# ===== [01] PURPOSE ==========================================================
# LlamaIndex 호환 레이어: 프로젝트 전체는 여기서만 Document를 가져온다.
# 사용: from src.compat.llama import Document

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations

from typing import Any, Dict, Optional


# ===== [03] DOCUMENT RESOLUTION (SINGLE BINDING) =============================
# mypy가 제어 흐름을 따지지 않아서, 같은 이름을 import/정의로 중복하면 no-redef가 납니다.
# 따라서 'Document'를 변수로 선언하고(타입: 'type[Any]'), 런타임에 한 번만 바인딩합니다.
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


# ===== [04] EXPORTS ==========================================================
__all__ = ["Document"]

# ===== [05] END ==============================================================
