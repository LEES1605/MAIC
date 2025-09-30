# ===== [01] FILE: src/ui/utils/readiness.py — START =====
# -*- coding: utf-8 -*-
"""
Header Readiness (H1)
- Tri-state badge for the app header:
  🟩 READY            → latest release restored (prompts-latest == local)
  🟨 준비중(로컬만)     → local index present but not latest
  🟧 없음               → no local index (or release missing)

How it decides:
1) 우선, 세션 오버라이드 키를 존중합니다.
   - st.session_state['_INDEX_IS_LATEST'] ∈ {True, False}
   - st.session_state['_INDEX_LOCAL_READY'] ∈ {True, False}
2) 없으면 자동 진단:
   - GitHub Release('prompts-latest' → 'prompts.yaml') 메타 조회
   - 로컬 캐시에서 복원 여부/릴리스 태그 추정
3) 결과를 간단한 배지(이모지+텍스트)로 렌더합니다.

Secrets (optional):
- GITHUB_REPO = "OWNER/REPO"
- GITHUB_TOKEN = "<pat>"           # private 레포 또는 rate-limit 회피 시
- PROMPTS_CACHE_DIR = "var/prompts"  # 로컬 복원 위치 힌트

SSOT/운영 원칙은 docs/_gpt 문서를 따릅니다.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# lazy imports (Streamlit / requests)
st = importlib.import_module("streamlit")
try:
    req = importlib.import_module("requests")
except Exception:
    req = None  # 네트워크 불가 환경 고려


# ---------- data model ----------
@dataclass
class ReleaseInfo:
    ok: bool
    tag: Optional[str] = None
    published_at: Optional[str] = None
    has_prompts: bool = False
    message: str = ""


# ---------- helpers ----------
def _split_repo(repo_full: str) -> Tuple[str, str]:
    if repo_full and "/" in repo_full:
        o, r = repo_full.split("/", 1)
        return o, r
    return "", ""


def _http_get_json(url: str, token: Optional[str] = None, timeout: int = 12) -> dict:
    if req is None:
        raise RuntimeError("requests not available")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = req.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _read_text(p: Path) -> Optional[str]:
    try:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


# ---------- release / local detection ----------
def fetch_release_info() -> ReleaseInfo:
    """Get latest release meta (prefer tag 'prompts-latest')."""
    repo_full = st.secrets.get("GITHUB_REPO", "")
    token = st.secrets.get("GITHUB_TOKEN")
    owner, repo = _split_repo(repo_full)
    if not owner or not repo:
        return ReleaseInfo(ok=False, message="GITHUB_REPO unset or malformed")

    # try /releases/tags/prompts-latest → fallback /releases/latest
    try:
        rel = _http_get_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases/tags/prompts-latest",
            token=token,
        )
    except Exception as exc_latest_tag:  # noqa: BLE001
        try:
            rel = _http_get_json(
                f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
                token=token,
            )
        except Exception as exc_latest:  # noqa: BLE001
            return ReleaseInfo(ok=False, message=f"release not found: {exc_latest_tag or exc_latest}")

    assets = rel.get("assets") or []
    has_prompts = any((a.get("name") or "").lower() in ("prompts.yaml", "prompts.yml") for a in assets)
    return ReleaseInfo(
        ok=True,
        tag=rel.get("tag_name") or "latest",
        published_at=rel.get("published_at") or rel.get("created_at"),
        has_prompts=bool(has_prompts),
        message=f"tag={rel.get('tag_name') or 'latest'}, assets={len(assets)}",
    )


def detect_local_index() -> Tuple[bool, Optional[str]]:
    """
    Detect restored prompts index locally.
    Heuristics:
      - PROMPTS_CACHE_DIR (default 'var/prompts')
      - look for: {cache}/latest/prompts.yaml
      - optional meta: {cache}/latest/release_tag.txt OR meta.json {'release_tag':...}
    Returns: (has_local_index, release_tag_if_known)
    """
    cache_root = Path(st.secrets.get("PROMPTS_CACHE_DIR", "var/prompts"))
    latest_dir = cache_root / "latest"
    has_local = (latest_dir / "prompts.yaml").exists()
    release_tag = None

    # meta files (best-effort)
    tag_txt = _read_text(latest_dir / "release_tag.txt")
    if tag_txt:
        release_tag = tag_txt
    else:
        meta_json = _read_text(latest_dir / "meta.json")
        if meta_json:
            try:
                obj = json.loads(meta_json)
                release_tag = obj.get("release_tag")
            except Exception:
                pass
    return has_local, release_tag


# ---------- core API ----------
def compute_readiness() -> Tuple[str, str]:
    """
    Returns:
      state: "green" | "yellow" | "orange"
      detail: short human-readable text
    Resolution order:
      - honor st.session_state overrides (set by orchestrator/restore job)
      - fallback to auto-detection (release vs local)
    """
    # 0) explicit overrides (if orchestrator already set them)
    is_latest = st.session_state.get("_INDEX_IS_LATEST")
    local_ready = st.session_state.get("_INDEX_LOCAL_READY")

    # 1) if not set, auto-detect
    if is_latest is None or local_ready is None:
        rel = fetch_release_info()
        has_local, local_tag = detect_local_index()
        local_ready = bool(has_local) if local_ready is None else local_ready

        if rel.ok and rel.has_prompts and local_tag and rel.tag:
            is_latest = bool(local_tag == rel.tag)
        elif rel.ok and rel.has_prompts and has_local and is_latest is None:
            # local exists but tag unknown → treat as not-latest (conservative)
            is_latest = False
        elif is_latest is None:
            is_latest = False

    # 2) decide tri-state
    if is_latest:
        return "green", "🟩 READY — 최신 인덱스를 복원했습니다."
    if local_ready:
        return "yellow", "🟨 준비중 — 로컬 인덱스만 감지되었습니다(최신 아님)."
    return "orange", "🟧 없음 — 인덱스가 없습니다."


def render_readiness_header(compact: bool = True) -> None:
    """
    Renders a tiny header badge. Place it near the top of your page.
    """
    state, text = compute_readiness()
    if compact:
        # single-line chip
        st.markdown(
            f"<div style='padding:6px 10px;border-radius:8px;"
            f"font-size:0.95rem;display:inline-block;"
            f"background:{'#E7F8EA' if state=='green' else '#FFF7E0' if state=='yellow' else '#FFE8E5'};"
            f"color:#111;border:1px solid {('#BCE7C4' if state=='green' else '#F2D49A' if state=='yellow' else '#F5B1A8')};'>"
            f"{text}</div>",
            unsafe_allow_html=True,
        )
    else:
        # verbose with context (release/local info)
        rel = fetch_release_info()
        has_local, local_tag = detect_local_index()
        st.markdown(f"**상태:** {text}")
        with st.expander("세부 정보", expanded=False):
            st.markdown(
                f"- 릴리스: {'있음' if rel.ok else '없음'}"
                + (f" (tag=`{rel.tag}`, assets=prompts={'있음' if rel.has_prompts else '없음'})" if rel.ok else "")
            )
            st.markdown(
                f"- 로컬 인덱스: {'있음' if has_local else '없음'}"
                + (f" (tag=`{local_tag}`)" if local_tag else "")
            )
# ===== [01] FILE: src/ui/utils/readiness.py — END =====
