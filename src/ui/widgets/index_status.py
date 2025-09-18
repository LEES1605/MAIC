from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Iterable, Optional

from src.runtime.gh_release import GHConfig, GHReleases, GHError


def _fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            if u == "B":
                return f"{int(v)} {u}"
            return f"{v:.1f} {u}"
        v /= 1024.0
    return f"{v:.1f} TB"


def _count_files(dest: Path) -> int:
    if not dest.exists():
        return 0
    return sum(1 for p in dest.rglob("*") if p.is_file())


def _pick_asset(assets: list[dict], candidates: Iterable[str]) -> Optional[dict]:
    for name in candidates:
        for a in assets:
            if a.get("name") == name:
                return a
    for a in assets:
        if str(a.get("name", "")).lower().endswith(".zip"):
            return a
    return None


def render_index_status_panel(
    *,
    dest_dir: Path,
    tag_candidates: Iterable[str],
    asset_candidates: Iterable[str],
    repo_full: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """Render status panel with badges and action buttons."""
    st: Any = importlib.import_module("streamlit")

    # repo / token
    repo_full = repo_full or st.secrets.get("GITHUB_REPO", os.getenv("GITHUB_REPO", ""))
    token = token or st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))

    if "/" not in repo_full:
        st.error("GITHUB_REPO is missing (expected 'OWNER/REPO').")
        return
    owner, repo = repo_full.split("/", 1)
    gh = GHReleases(GHConfig(owner=owner, repo=repo, token=token))

    # read release meta
    rel = None
    chosen_tag = None
    for t in tag_candidates:
        try:
            rel = gh.get_release_by_tag(t)
            chosen_tag = t
            break
        except Exception:  # noqa: BLE001
            continue

    assets = (rel or {}).get("assets") or []
    asset = _pick_asset(assets, asset_candidates) if rel else None

    # badges
    left, mid, right = st.columns(3)
    left.metric("Release Tag", chosen_tag or "(none)")
    mid.metric("Asset", (asset or {}).get("name", "(none)"))
    right.metric("Files", _count_files(dest_dir))

    # meta/controls
    with st.expander("Release 메타데이터", expanded=False):
        if rel:
            st.json(rel)
        else:
            st.info("릴리스 정보를 찾지 못했습니다.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Release에서 최신 인덱스 복원", use_container_width=True):
            try:
                log = gh.restore_latest_index(
                    tag_candidates=tag_candidates,
                    asset_candidates=asset_candidates,
                    dest=dest_dir,
                )
                st.success(log)
            except GHError as e:
                st.error(f"복원 실패: {e}")

    with col2:
        if st.button("📂 현재 persist 파일 수 갱신", use_container_width=True):
            st.toast("파일 수를 갱신했습니다.")
