# ===== [NEW FILE / src/services/index.py / L0001–L9999] — START =====
# [01] Imports & Constants ======================================================
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any, Dict, Tuple
import importlib
import io
import os
import shutil
import tempfile
import traceback

# ===== [02] Persist path resolution (IDX → CFG → ~/.maic/persist) — START =====
def _persist_dir() -> Path:
    """우선순위: src.rag.index_build.PERSIST_DIR → src.config.PERSIST_DIR → ~/.maic/persist"""
    # 1) 인덱서가 노출하는 경로
    try:
        from src.rag.index_build import PERSIST_DIR as IDX
        return Path(IDX).expanduser()
    except Exception:
        pass
    # 2) 전역 설정
    try:
        from src.config import PERSIST_DIR as CFG
        return Path(CFG).expanduser()
    except Exception:
        pass
    # 3) 폴백
    return Path.home() / ".maic" / "persist"
# ===== [02] Persist path resolution (IDX → CFG → ~/.maic/persist) — END =====


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
        # 로깅은 호출부에서 종합
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
        # 세션이 없거나 읽기 전용일 때도 앱이 죽지 않도록 무시
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
    cand = _try_import(
        "src.rag.index_build",
        [
            "rebuild_index",
            "build_index",
            "rebuild",
            "index_all",
            "build_all",
            "build_index_with_checkpoint",
        ],
    )
    order = [
        "rebuild_index",
        "build_index",
        "rebuild",
        "index_all",
        "build_all",
        "build_index_with_checkpoint",
    ]
    for name in order:
        fn = cand.get(name)
        if callable(fn):
            return fn, name
    return None, ""


# [07] Public API: reindex() ====================================================
def reindex(dest_dir: Optional[str | Path] = None) -> bool:
    """
    로컬 인덱스를 재구축(또는 초기 구축)합니다.
    - 가능한 인덱서 함수를 동적으로 탐색하여 호출합니다.
    - 인자 시그니처 차이를 흡수(있으면 경로 전달, 아니면 무인자 호출).
    - 빌더가 다른 경로에 산출물을 만들더라도, chunks.jsonl(.gz) / chunks/*.jsonl을
      찾아서 dest 루트로 이관/병합 후 SSOT(.ready + chunks.jsonl) 보정합니다.

    반환값: 성공 True / 실패 False
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        _set_brain_status("ERROR", "인덱스 경로 생성 실패", "local", attached=False)
        return False

    # ---- 내부 헬퍼: 산출물 탐지/이관/병합 -------------------------------------
    def _decompress_gz(src: Path, dst: Path) -> bool:
        try:
            import gzip
            with gzip.open(src, "rb") as gf:
                dst.write_bytes(gf.read())
            return True
        except Exception:
            return False

    def _merge_chunk_dir(chunk_dir: Path, out_file: Path) -> bool:
        """chunks/*.jsonl 여러 파일을 라인단위로 out_file에 병합."""
        try:
            out_file.unlink(missing_ok=True)  # 기존 파일 있으면 교체
            with out_file.open("wb") as w:
                for p in sorted(chunk_dir.glob("*.jsonl")):
                    try:
                        with p.open("rb") as r:
                            shutil.copyfileobj(r, w)
                    except Exception:
                        continue
            return out_file.exists() and out_file.stat().st_size > 0
        except Exception:
            return False

    def _bring_chunks_to_root(candidates: list[Path]) -> bool:
        """후보 경로들에서 chunks 산출물을 찾아 base/chunks.jsonl로 만든다."""
        target = base / "chunks.jsonl"

        # 1) 정확히 chunks.jsonl
        for c in candidates:
            if c.is_dir():
                p = c / "chunks.jsonl"
            else:
                p = c if c.name == "chunks.jsonl" else None
            if p and p.exists() and p.is_file() and p.stat().st_size > 0:
                shutil.copy2(p, target)
                return True

        # 2) chunks.jsonl.gz
        for c in candidates:
            if c.is_dir():
                gz = c / "chunks.jsonl.gz"
            else:
                gz = c if c.name == "chunks.jsonl.gz" else None
            if gz and gz.exists() and gz.is_file():
                return _decompress_gz(gz, target)

        # 3) chunks/ 디렉터리 내 *.jsonl 병합
        for c in candidates:
            chunk_dir = (c / "chunks") if c.is_dir() else None
            if chunk_dir and chunk_dir.is_dir():
                if _merge_chunk_dir(chunk_dir, target):
                    return True

        # 4) 광역 탐색: **/chunks.jsonl / **/chunks.jsonl.gz / **/chunks/*.jsonl
        try:
            found = next(
                (p for cand in candidates for p in cand.rglob("chunks.jsonl")),
                None,
            )
        except Exception:
            found = None
        if found and found.is_file() and found.stat().st_size > 0:
            shutil.copy2(found, target)
            return True

        try:
            found_gz = next(
                (p for cand in candidates for p in cand.rglob("chunks.jsonl.gz")),
                None,
            )
        except Exception:
            found_gz = None
        if found_gz and found_gz.is_file():
            return _decompress_gz(found_gz, target)

        try:
            found_dir = next(
                (d for cand in candidates for d in cand.rglob("chunks") if d.is_dir()),
                None,
            )
        except Exception:
            found_dir = None
        if found_dir and _merge_chunk_dir(found_dir, target):
            return True

        return False

    # ---- 인덱서 선택 및 호출 ---------------------------------------------------
    fn, name = _pick_reindex_fn()
    if not callable(fn):
        _set_brain_status("MISSING", "재인덱싱 함수가 없습니다.", "local", attached=False)
        return False

    # 호출 전후로 후보 경로를 넓게 수집
    candidates: list[Path] = [base]
    try:
        # 모듈이 노출하는 기본 출력 경로도 후보에 추가
        try:
            from src.rag.index_build import PERSIST_DIR as IDX_DIR
            candidates.append(Path(str(IDX_DIR)).expanduser())
        except Exception:
            pass

        # 인자 유무에 맞춰 호출하고 반환값을 검사
        ret: Any
        try:
            ret = fn(base)
        except TypeError:
            ret = fn()

        # 반환값이 경로/딕셔너리면 후보에 추가
        try:
            if isinstance(ret, (str, Path)):
                candidates.append(Path(ret).expanduser())
            elif isinstance(ret, dict):
                for k in (
                    "output_dir",
                    "out_dir",
                    "persist_dir",
                    "dir",
                    "path",
                    "chunks_dir",
                ):
                    v = ret.get(k)
                    if isinstance(v, (str, Path)):
                        candidates.append(Path(v).expanduser())
        except Exception:
            pass
    except Exception as e:
        _set_brain_status("ERROR", f"재인덱싱 실패: {type(e).__name__}", "local", attached=False)
        return False

    # ---- 산출물 이관/복원 ------------------------------------------------------
    # 중복 제거 및 존재하는 경로만
    uniq: list[Path] = []
    seen = set()
    for c in candidates:
        try:
            cp = c.resolve()
        except Exception:
            cp = c
        if (str(cp) not in seen) and cp.exists():
            uniq.append(cp)
            seen.add(str(cp))

    if not _bring_chunks_to_root(uniq):
        # 산출물을 찾지 못했거나, 0B → 실패 처리(SSOT 미충족)
        _set_brain_status(
            "MISSING",
            "재인덱싱 완료했지만 산출물(chunks.jsonl)을 찾지 못했습니다.",
            "local",
            attached=False,
        )
        return False

    # ---- SSOT 보정 및 최종 판정 -------------------------------------------------
    _ensure_ready_signal(base)
    status = index_status(base)
    if status["local_ok"]:
        _set_brain_status("READY", "재인덱싱 완료(READY)", "local", attached=True)
        return True

    _set_brain_status(
        "MISSING",
        "재인덱싱 완료했지만 READY 조건(.ready+chunks)이 미충족",
        "local",
        attached=False,
    )
    return False
# [07] END =====================================================================


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
    """
    네트워크 호출 없이 로컬 신호만으로 READY 승격(.ready 보정 포함).
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    _ensure_ready_signal(base)

    if _local_ready(base):
        _set_brain_status("READY", "로컬 인덱스 연결됨", "local", attached=True)
        return True

    _set_brain_status("MISSING", "인덱스 없음(attach 불가)", "", attached=False)
    return False
# [09] END =====================================================================


# [10] Safety: minimal logger (console only) ====================================
def _log_console(msg: str) -> None:
    try:
        print(f"[services.index] {msg}")
    except Exception:
        pass


# ===== [NEW FILE / src/services/index.py / L0001–L9999] — END =====
