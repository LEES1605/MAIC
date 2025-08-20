# ===== [01] PURPOSE ==========================================================
# settings / PERSIST_DIR 등 공통 심볼을 단일 바인딩하여
# no-redef / 경로 폴백 문제를 영구 제거합니다.

# ===== [02] IMPORTS ==========================================================
from __future__ import annotations
from importlib import import_module
from typing import Optional

# ===== [03] RESOLUTION =======================================================
try:
    _cfg = import_module("src.config")
except Exception:
    _cfg = import_module("config")

# ===== [04] SINGLE BINDINGS ==================================================
settings = _cfg.settings
PERSIST_DIR = _cfg.PERSIST_DIR
QUALITY_REPORT_PATH: Optional[str] = getattr(_cfg, "QUALITY_REPORT_PATH", None)
MANIFEST_PATH: Optional[str] = getattr(_cfg, "MANIFEST_PATH", None)
CHECKPOINT_PATH: Optional[str] = getattr(_cfg, "CHECKPOINT_PATH", None)

# ===== [05] EXPORTS ==========================================================
__all__ = ["settings", "PERSIST_DIR", "QUALITY_REPORT_PATH", "MANIFEST_PATH", "CHECKPOINT_PATH"]
# ===== [06] END ==============================================================
