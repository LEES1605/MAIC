# ===== [01] STUB =============================================================
from __future__ import annotations
from typing import Any, Dict, List, Callable, Mapping, Set, Tuple
import streamlit as st

def build_index_with_checkpoint(
    update_pct: Callable[[int, str | None], None],
    update_msg: Callable[[str], None],
    gdrive_folder_id: str,
    gcp_creds: Mapping[str, Any],
    persist_dir: str,
    remote_manifest: Dict[str, Dict[str, Any]],
    should_stop: Callable[[], bool] | None = None,
):
    st.info("This is a stub for index build.")
    return object()
