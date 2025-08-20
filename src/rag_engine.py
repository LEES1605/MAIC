# ===== [01] IMPORTS ==========================================================
from __future__ import annotations
from typing import Any, Optional, Callable
from src.compat.config_bridge import settings, PERSIST_DIR

# ===== [02] ERRORS ===========================================================
class RAGEngineError(Exception): ...
class QueryEngineNotReady(RAGEngineError): ...
class LocalIndexMissing(RAGEngineError): ...

# ===== [03] INDEX LOAD/CREATE (STUB) ========================================
def _index_exists(persist_dir: str | bytes | "os.PathLike[str]") -> bool:
    from pathlib import Path
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

# ===== [04] PUBLIC API =======================================================
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
    # TODO: plug actual build/restore
    # for now, create an empty folder so _index_exists passes next time
    from pathlib import Path
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return _load_index_from_disk(persist_dir)
