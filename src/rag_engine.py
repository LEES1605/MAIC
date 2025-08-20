# ===== [01] IMPORTS ==========================================================
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from src.compat.config_bridge import PERSIST_DIR

# ===== [02] CONFIG BRIDGE ====================================================
# (임포트는 [01]에서 완료. 중복 임포트 방지를 위해 설명 주석만 유지)

# ===== [03] ERRORS ===========================================================
class RAGEngineError(Exception): ...
class QueryEngineNotReady(RAGEngineError): ...
class LocalIndexMissing(RAGEngineError): ...

# ===== [04] LOCAL INDEX HELPERS =============================================
def _index_exists(persist_dir: str | bytes | "Path") -> bool:
    p = Path(persist_dir)
    try:
        return p.exists() and any(p.iterdir())
    except Exception:
        return False

def _load_index_from_disk(persist_dir: str) -> Any:
    if not _index_exists(persist_dir):
        raise LocalIndexMissing("No local index")
    class _DummyIndex:
        def as_query_engine(self, **kw: Any):
            class _QE:
                def query(self, q: str) -> Any:
                    return type("R", (), {"response": f"[stub] {q}"})
            return _QE()
    return _DummyIndex()

# ===== [05] PUBLIC API =======================================================
def get_or_build_index(
    update_pct: Optional[Callable[[int], None]] = None,
    update_msg: Optional[Callable[[str], None]] = None,
    gdrive_folder_id: Optional[str] = None,
    raw_sa: Optional[str] = None,
    persist_dir: str = str(PERSIST_DIR),
    manifest_path: Optional[str] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Any:
    if _index_exists(persist_dir):
        return _load_index_from_disk(persist_dir)
    # 초기 생성: 빈 폴더를 만들어 다음 호출부터 로드 가능하도록
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return _load_index_from_disk(persist_dir)
# ===== [06] END ==============================================================
