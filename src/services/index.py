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
    - 빌더가 다른 경로에 산출물을 만들더라도, 다양한 패턴의 *.jsonl(.gz)와
      chunks/ 디렉터리를 찾아 dest 루트로 이관/해제/병합 후 SSOT(.ready+chunks) 보정.
    """
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        _set_brain_status("ERROR", "인덱스 경로 생성 실패", "local", attached=False)
        return False

    # ---- 내부 헬퍼 --------------------------------------------------------------
    def _size(p: Path) -> int:
        try:
            return p.stat().st_size
        except Exception:
            return 0

    def _decompress_gz(src: Path, dst: Path) -> bool:
        try:
            import gzip
            with gzip.open(src, "rb") as gf:
                data = gf.read()
            if not data:
                return False
            dst.write_bytes(data)
            return True
        except Exception:
            return False

    def _merge_chunk_dir(chunk_dir: Path, out_file: Path) -> bool:
        """chunks/*.jsonl 여러 파일을 라인단위로 out_file에 병합."""
        try:
            bytes_written = 0
            tmp_out = out_file.with_suffix(".jsonl.tmp")
            tmp_out.unlink(missing_ok=True)
            with tmp_out.open("wb") as w:
                for p in sorted(chunk_dir.glob("*.jsonl")):
                    try:
                        with p.open("rb") as r:
                            while True:
                                buf = r.read(1024 * 1024)
                                if not buf:
                                    break
                                w.write(buf)
                                bytes_written += len(buf)
                    except Exception:
                        continue
            if bytes_written > 0:
                out_file.unlink(missing_ok=True)
                tmp_out.replace(out_file)
                return True
            tmp_out.unlink(missing_ok=True)
            return False
        except Exception:
            return False

    def _bring_chunks_to_root(cands: list[Path]) -> bool:
        """후보 경로들에서 산출물을 찾아 base/chunks.jsonl로 만든다."""
        target = base / "chunks.jsonl"

        # 0바이트 target이 있으면 우선 제거(정상 산출물로 대체 예정)
        if target.exists() and _size(target) == 0:
            target.unlink(missing_ok=True)

        # 1) 정확명 우선
        exact = []
        exact_gz = []
        dirs = []
        any_jsonl = []
        any_gz = []
        for c in cands:
            if not c.exists():
                continue
            try:
                exact += [p for p in c.rglob("chunks.jsonl") if _size(p) > 0]
            except Exception:
                pass
            try:
                exact_gz += [p for p in c.rglob("chunks.jsonl.gz") if _size(p) > 0]
            except Exception:
                pass
            try:
                dirs += [d for d in c.rglob("chunks") if d.is_dir()]
            except Exception:
                pass
            try:
                any_jsonl += [p for p in c.rglob("*.jsonl") if _size(p) > 0]
            except Exception:
                pass
            try:
                any_gz += [p for p in c.rglob("*.jsonl.gz") if _size(p) > 0]
            except Exception:
                pass

        if exact:
            best = max(exact, key=_size)
            shutil.copy2(best, target)
            return True
        if exact_gz:
            best_gz = max(exact_gz, key=_size)
            return _decompress_gz(best_gz, target)
        for d in dirs:
            if _merge_chunk_dir(d, target):
                return True
        if any_jsonl:
            best_any = max(any_jsonl, key=_size)
            shutil.copy2(best_any, target)
            return True
        if any_gz:
            best_any_gz = max(any_gz, key=_size)
            return _decompress_gz(best_any_gz, target)

        return False

    # ---- 인덱서 선택 및 호출 ---------------------------------------------------
    fn, _name = _pick_reindex_fn()
    if not callable(fn):
        _set_brain_status("MISSING", "재인덱싱 함수가 없습니다.", "local", attached=False)
        return False

    # 호출 전후로 후보 경로를 넓게 수집
    candidates: list[Path] = [base]
    try:
        try:
            from src.rag.index_build import PERSIST_DIR as IDX_DIR
            candidates.append(Path(str(IDX_DIR)).expanduser())
        except Exception:
            pass

        # 인자 유무에 맞춰 호출
        try:
            ret = fn(base)
        except TypeError:
            ret = fn()

        # 반환값 힌트 흡수
        try:
            if isinstance(ret, (str, Path)):
                candidates.append(Path(ret).expanduser())
            elif isinstance(ret, dict):
                for k in (
                    "output_dir", "out_dir", "persist_dir",
                    "dir", "path", "chunks_dir",
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
