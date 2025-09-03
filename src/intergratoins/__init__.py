# =============================== [01] compat shim — START ================================
"""
Compatibility shim for old typo path: `src.intergratoins`

New code MUST import from `src.integrations`.
This module re-exports `gdrive` for backward compatibility.
"""
from src.integrations import gdrive as gdrive  # noqa: F401
__all__ = ["gdrive"]
# ================================ [01] compat shim — END =================================
