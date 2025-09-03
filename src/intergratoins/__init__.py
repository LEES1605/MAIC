# ============================== [01] integrations pkg — START ===============================
"""
MAIC integrations package.

- Official integrations live here (e.g., Google Drive).
- Import from `src.integrations`, not from typo paths.
"""
# Re-export for convenience; some code does `from src.integrations import gdrive`
from . import gdrive as gdrive  # noqa: F401

__all__ = ["gdrive"]
# =============================== [01] integrations pkg — END ================================
