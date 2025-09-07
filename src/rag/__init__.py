# ===== [01] EXPORTS ==========================================================  # [01] START
from __future__ import annotations

# 안정된 엔트리만 export.
# 호환성: 기존 호출 지점들이 기대하는 build_index_with_checkpoint 를
# 신규 구현 rebuild_index 에 매핑한다.
from .index_build import rebuild_index as build_index_with_checkpoint, rebuild_index

__all__ = [
    "rebuild_index",
    "build_index_with_checkpoint",
]
# [01] END
