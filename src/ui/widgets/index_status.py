# ===== [01] FILE: src/ui/widgets/index_status.py — START =====
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Iterable, Optional

from src.core.readiness import normalize_ready_file
from src.core.restore_meta import save_restore_meta
from src.runtime.gh_release import GHConfig, GHError, GHReleases, RestoreLog


def _count_files(dest: Path) -> int:
    if not dest.exists():
        return 0
    return sum(1 for p in dest.rglob("*") if p.is_file())


def _pick_asset(assets: list[dict], candidates: Iterable[str]) -> Optional[dict]:
    # 정확 일치 우선, 없으면 *.zip 중 첫 번째
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
    repo_full: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """
    Release 상태/복원 위젯 (순차번호 시스템).
    - '복원' 버튼: 최신 인덱스 복원 → .ready 표준화 → restore_meta 저장 → 세션 플래그 갱신 → 헤더 즉시 반영
    - '파일 수 갱신' 버튼: 로컬 persist 파일 개수 새로 고침
    """
    st: Any = importlib.import_module("streamlit")

    repo_full = repo_full or st.secrets.get("GITHUB_REPO", os.getenv("GITHUB_REPO", ""))
    token = token or st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))

    if "/" not in str(repo_full):
        st.error("GITHUB_REPO is missing (expected 'OWNER/REPO').")
        return

    owner, repo = str(repo_full).split("/", 1)
    
    # 순차번호 관리자 사용
    from src.runtime.sequential_release import create_sequential_manager
    seq_manager = create_sequential_manager(owner, repo, token)

    # 최신 인덱스 릴리스 정보 조회
    rel = seq_manager.find_latest_by_number("index")
    chosen_tag = rel.get('tag_name') if rel else None
    assets = (rel or {}).get("assets") or []
    asset = _pick_asset(assets, ["index.tar.gz", "index.zip"]) if rel else None

    left, mid, right = st.columns(3)
    left.metric("Release Tag", chosen_tag or "(none)")
    mid.metric("Asset", (asset or {}).get("name", "(none)"))
    right.metric("Files", _count_files(dest_dir))

    with st.expander("Release 메타데이터", expanded=False):
        if rel:
            st.json(rel)
        else:
            st.info("릴리스 정보를 찾지 못했습니다.")

    c1, c2 = st.columns(2)

    # 1) 최신 인덱스 복원
    with c1:
        if st.button("Release에서 최신 인덱스 복원", use_container_width=True):
            try:
                res = seq_manager.restore_latest_index(
                    dest=dest_dir,
                    clean_dest=True,
                )

                # 순차번호 시스템 결과 처리
                rtag = res.get("tag")
                rid = res.get("release_id")
                detail = res.get("detail", str(res))

                # (1) ready 표준화
                try:
                    normalize_ready_file(dest_dir)
                except Exception:
                    pass

                # (2) restore_meta 저장
                saved_meta = None
                try:
                    saved_meta = save_restore_meta(dest_dir, tag=rtag, release_id=rid)
                except Exception:
                    pass

                # (3) 세션 플래그 갱신 → 헤더가 즉시 🟩로 전환되도록
                try:
                    st.session_state["_RESTORE_LATEST_DONE"] = True
                    st.session_state["_INDEX_LOCAL_READY"] = True
                    st.session_state["_LATEST_RELEASE_TAG"] = rtag
                    if saved_meta is not None and hasattr(saved_meta, "to_dict"):
                        st.session_state["_LAST_RESTORE_META"] = saved_meta.to_dict()
                except Exception:
                    pass

                st.success(detail or "최신 릴리스 복원 완료")
                if rtag or rid:
                    st.toast(f"복원 태그={rtag} (release_id={rid})")

                # 헤더/배지 즉시 반영
                st.rerun()
            except GHError as e:
                st.error(f"복원 실패: {e}")

    # 2) 로컬 persist 파일 수 갱신
    with c2:
        if st.button("📂 현재 persist 파일 수 갱신", use_container_width=True):
            st.toast(f"파일 수: {_count_files(dest_dir)}")


__all__ = ["render_index_status_panel"]
# ===== [01] FILE: src/ui/widgets/index_status.py — END =====
