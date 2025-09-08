# ===== [NEW FILE / src/services/index.py / L0001–L9999] — START =====
# [01] Imports & Constants ======================================================
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any, Dict, Tuple
import importlib

# ===== [02] Persist path resolution (SSOT: core.persist) — START =====
def _persist_dir() -> Path:
    """SSOT: core.persist.effective_persist_dir()만 사용.
    실패 시 홈 기본(~/.maic/persist)로 안전 폴백.
    """
    try:
        from src.core.persist import effective_persist_dir as _ssot  # lazy import
        p = _ssot()
        return p if isinstance(p, Path) else Path(str(p)).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"
# ===== [02] Persist path resolution (SSOT: core.persist) — END =====


# [03] SSOT helpers (.ready + chunks.jsonl) =====================================
def _chunks_path(p: Path) -> Path:
    return p / "chunks.jsonl"


def _ready_path(p: Path) -> Path:
    return p / ".ready"


def _local_ready(p: Optional[Path] = None) -> bool:
    """SSOT: .ready & chunks.jsonl(>0B) 동시 존재해야 READY."""
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        return _ready_path(base).exists() and cj.exists() and cj.stat().st_size > 0
    except Exception:
        return False


def _ensure_ready_signal(p: Optional[Path] = None) -> None:
    """chunks.jsonl이 있고 .ready가 없으면 .ready를 생성(멱등)."""
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        r = _ready_path(base)
        if cj.exists() and cj.stat().st_size > 0 and not r.exists():
            r.write_text("ok", encoding="utf-8")
    except Exception:
        pass


def index_status(p: Optional[Path] = None) -> Dict[str, Any]:
    """현 로컬 인덱스 상태 요약(SSOT)."""
    base = p or _persist_dir()
    try:
        cj = _chunks_path(base)
        return {
            "persist_dir": str(base),
            "chunks_exists": cj.exists(),
            "chunks_size": (cj.stat().st_size if cj.exists() else 0),
            "ready_flag": _ready_path(base).exists(),
            "local_ok": _local_ready(base),
            "code": "READY" if _local_ready(base) else "MISSING",
        }
    except Exception:
        return {
            "persist_dir": str(base),
            "chunks_exists": False,
            "chunks_size": 0,
            "ready_flag": False,
            "local_ok": False,
            "code": "MISSING",
        }
# [03] END ======================================================================


# ===== [04] Streamlit SSOT sync (optional, no hard dependency) — START =====
def _set_brain_status(code: str, msg: str = "", source: str = "", attached: bool = False) -> None:
    """app.py의 세션 키와 동일한 필드에 상태를 반영(존재 시)."""
    try:
        import streamlit as st
    except Exception:
        return
    try:
        ss = st.session_state
        ss["brain_status_code"] = code
        ss["brain_status_msg"] = msg
        ss["brain_source"] = source
        ss["brain_attached"] = bool(attached)
        ss["restore_recommend"] = code in ("MISSING", "ERROR")
        ss.setdefault("index_decision_needed", False)
        ss.setdefault("index_change_stats", {})
    except Exception:
        pass
# ===== [04] Streamlit SSOT sync (optional, no hard dependency) — END =====


# [05] Dynamic import helpers ====================================================
def _try_import(modname: str, names: list[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        mod = importlib.import_module(modname)
        for n in names:
            out[n] = getattr(mod, n, None)
    except Exception:
        for n in names:
            out[n] = None
    return out


# [06] Decision tree: choose best available indexer =============================
def _pick_reindex_fn() -> Tuple[Optional[Any], str]:
    """
    가능한 인덱싱 함수 후보 중 첫 번째로 발견되는 함수를 반환.
    반환: (callable | None, name)
    """
    # 긴 리스트를 상수 튜플로 분리해 E501(100자 제한) 위반 방지
    candidates: tuple[str, ...] = (
        "rebuild_index",
        "build_index",
        "rebuild",
        "index_all",
        "build_all",
        "build_index_with_checkpoint",
    )

    # _try_import는 list[str]을 받으므로 변환
    cand = _try_import("src.rag.index_build", list(candidates))

    for name in candidates:
        fn = cand.get(name)
        if callable(fn):
            return fn, name
    return None, ""
# ============================ [06] END =========================================



# ========================== [07] Public API: reindex() — START ==========================
def reindex(dest_dir=None) -> bool:
    """
    SSOT: core.persist.effective_persist_dir() 기준으로 인덱싱.
    - dest_dir가 주어지면 해당 경로에 빌드(테스트/임시용).
    - 성공 기준: chunks.jsonl > 0B && .ready 존재.
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    try:
        mod = importlib.import_module("src.rag.index_build")
        fn = getattr(mod, "rebuild_index", None)
        if not callable(fn):
            return False
        fn(output_dir=base)  # 인덱서에 명시적 출력 경로 전달
    except Exception:
        return False

    _ensure_ready_signal(base)
    try:
        cj = base / "chunks.jsonl"
        size = cj.stat().st_size if cj.exists() else 0
        ok = bool((base / ".ready").exists() and cj.exists() and size > 0)
        return ok
    except Exception:
        return False
# =========================== [07] Public API: reindex() — END ===========================


# [08] Public API: restore_or_attach() ==========================================
def restore_or_attach(dest_dir: Optional[str | Path] = None) -> bool:
    """
    복구(릴리스) 또는 로컬 첨부를 시도하여 사용 가능한 인덱스를 만든다.
    - 1) 이미 .ready+chunks가 있으면 그대로 READY
    - 2) GitHub 최신 릴리스 복구 시도 (있다면)
    - 3) 성공/부분성공이면 SSOT 보정 후 상태를 반영
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    if _local_ready(base):
        _set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
        return True

    gh = _try_import("src.backup.github_release", ["restore_latest"])
    restore_latest = gh.get("restore_latest")
    if callable(restore_latest):
        try:
            restored_ok = bool(restore_latest(base))
        except Exception:
            restored_ok = False
        if restored_ok:
            _ensure_ready_signal(base)

    status = index_status(base)
    if status["local_ok"]:
        _set_brain_status("READY", "릴리스 복구/연결 완료", "github", attached=True)
        return True

    _set_brain_status("MISSING", "복구/연결 실패(인덱스 없음)", "", attached=False)
    return False
# [08] END =====================================================================


# [09] Public API: attach_local() ===============================================
def attach_local(dest_dir: Optional[str | Path] = None) -> bool:
    """네트워크 호출 없이 로컬 신호만으로 READY 승격(.ready 보정 포함)."""
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    _ensure_ready_signal(base)

    if _local_ready(base):
        _set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
        return True

    _set_brain_status("MISSING", "인덱스 없음(attach 불가)", "", attached=False)
    return False
# [09] END =====================================================================

# ===== [NEW FILE / src/services/index.py / L0001–L9999] — END =====
