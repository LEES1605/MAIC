# ===== [01] STUB =============================================================
from __future__ import annotations

from typing import Callable, Dict, Mapping

import streamlit as st


def build_index_with_checkpoint(
    update_pct: Callable[[int, str | None], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,
    gcp_creds: Mapping[str, object],
    persist_dir: str,
    remote_manifest: Dict[str, Dict[str, object]],
    should_stop: Callable[[], bool] | None = None,
):
    st.info("This is a stub for index build.")
    return object()

# ===== [02] END ==============================================================
