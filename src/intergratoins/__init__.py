# ============================== [01] integrations pkg — START ===============================
"""
MAIC integrations package.

- Holds official integration drivers (e.g., Google Drive).
- Other modules should import from `src.integrations` (not from typo paths).
"""
# re-export for convenience (some modules import the package and expect `gdrive`)
from . import gdrive as gdrive  # noqa: F401

__all__ = ["gdrive"]
# =============================== [01] integrations pkg — END ================================
