# ===== [01] FILE: src/services/index.py — START =====
from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

from src.core.persist import effective_persist_dir
from src.core.index_probe import (
    IndexHealth,
    probe_index_health,
    get_brain_status,
    mark_ready,
)
from src.backup.packaging import make_index_zip
from src.runtime.gh_release import GHConfig, GHReleases, GHError


# ────────────────────────── persist / health ──────────────────────────
def persist_dir() -> Path:
    """SSOT persist 경로 반환."""
    return effective_persist_dir()


def local_index_health(sample_lines: int = 50) -> IndexHealth:
    """로컬 인덱스 상태 스냅샷."""
    return probe_index_health(effective_persist_dir(), sample_lines=sample_lines)


def local_brain_status() -> Dict[str, str]:
    """
    UI에서 쓰는 요약 상태 코드/문구.
    READY/MISSING 등 간단한 표식 위주(표시는 배지 정책과 별개로 활용).
    """
    return get_brain_status(effective_persist_dir())


# ────────────────────────── indexing (HQ/prepared) ──────────────────────────
def force_reindex(prepared_only: bool = True) -> Dict[str, Any]:
    """
    (관리자) 강제 재인덱싱. 성공 시 '.ready' 표준화.
    반환: 요약 정보 dict (최소 persist/chunks 존재 여부 포함)
    """
    try:
        from src.rag import index_build as _idx
    except Exception as e:
        raise RuntimeError(f"index_build 모듈 로드 실패: {e}") from e

    # prepared-only 모드 환경변수는 호출자(UI)에서 세팅하는 것이 일반적이나,
    # 기본값을 보수적으로 적용
    import os
    if prepared_only:
        os.environ["MAIC_INDEX_MODE"] = "HQ"
        os.environ["MAIC_USE_PREPARED_ONLY"] = "1"

    _idx.rebuild_index()

    p = effective_persist_dir()
    mark_ready(p)

    cj = p / "chunks.jsonl"
    return {
        "persist": str(p),
        "chunks": str(cj),
        "chunks_exists": cj.exists(),
        "chunks_size": (cj.stat().st_size if cj.exists() else 0),
    }


# ────────────────────────── packaging / release ──────────────────────────
def build_index_zip(
    *,
    out_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> Path:
    """
    persist → ZIP 생성(불필요 디렉토리 제외).
    """
    return make_index_zip(effective_persist_dir(), out_dir=out_dir, filename=filename)


def upload_index_zip(
    *,
    owner: str,
    repo: str,
    token: str,
    zip_path: Path,
    tag: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """
    ZIP을 GitHub Release에 업로드. 릴리스가 없으면 생성.
    """
    client = GHReleases(GHConfig(owner=owner, repo=repo, token=token))
    rel = client.ensure_release(tag or "index-latest", name=name or (tag or "index-latest"))
    client.upload_asset(rel, zip_path)
    return f"OK: uploaded {zip_path.name} to {owner}/{repo} tag={tag or 'index-latest'}"
# ===== [01] FILE: src/services/index.py — END =====
