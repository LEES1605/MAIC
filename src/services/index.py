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

# [07] Public API: reindex() ====================================================  # [07] START
def reindex(dest_dir=None) -> bool:
    """
    로컬 인덱스를 재구축(또는 초기 구축)합니다.
    - 동시 실행 방지(.lock, TTL 30분)
    - tmp 빌드 → 검증 → 원자 스왑
    - manifest.json 갱신, .ready 보정
    - LOCAL-FIRST 정책: 빌드 산출물 기준으로 로컬만 갱신(자동 원격 복구 없음)
    """
    # 지역 임포트(E402 회피 & 테스트 용이성)
    import os
    import json
    import time
    import shutil
    import tempfile
    import importlib
    from pathlib import Path
    from typing import Any, Optional, Dict

    # ---------- 내부 유틸 ----------
    def _persist_dir() -> Path:
        # 우선순위: state.session > rag.index_build > config > ~/.maic/persist
        try:
            from src.state.session import persist_dir
            return persist_dir()
        except Exception:
            pass
        try:
            from src.rag.index_build import PERSIST_DIR as IDX
            return Path(str(IDX)).expanduser()
        except Exception:
            pass
        try:
            from src.config import PERSIST_DIR as CFG
            return Path(str(CFG)).expanduser()
        except Exception:
            pass
        return Path.home() / ".maic" / "persist"

    def _set_brain_status(code: str, msg: str, origin: str, attached: bool) -> None:
        try:
            from src.state.session import set_brain_status
            set_brain_status(code, msg, origin, attached)
        except Exception:
            # 상태 반영 실패는 무시(표시용)
            pass

    def index_status(base: Optional[Path] = None) -> Dict[str, Any]:
        p = base or _persist_dir()
        cj = p / "chunks.jsonl"
        ready = (p / ".ready").exists()
        try:
            size = cj.stat().st_size if cj.exists() else 0
        except Exception:
            size = 0
        return {
            "persist_dir": str(p),
            "ready_flag": ready,
            "chunks_exists": cj.exists(),
            "chunks_size": size,
            "local_ok": bool(ready and cj.exists() and size > 0),
        }

    def _ensure_ready_signal(base: Path) -> None:
        try:
            r = base / ".ready"
            if not r.exists():
                r.write_text("ok", encoding="utf-8")
        except Exception:
            pass

    def _pick_reindex_fn():
        """가장 먼저 발견되는 빌더 함수를 반환."""
        cands = [
            ("src.services.index_impl", "reindex"),  # 확장 포인트(있으면 최우선)
            ("src.rag.index_build", "rebuild_index"),
            ("src.rag.index_build", "build_index"),
            ("src.rag.index_build", "rebuild"),
            ("src.rag.index_build", "index_all"),
            ("src.rag.index_build", "build_all"),
            ("src.rag.index_build", "build_index_with_checkpoint"),
        ]
        for mod, name in cands:
            try:
                m = importlib.import_module(mod)
                fn = getattr(m, name, None)
                if callable(fn):
                    return fn
            except Exception:
                continue
        return None

    def _sha256_file(p: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with p.open("rb") as r:
            for chunk in iter(lambda: r.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _verify_jsonl(p: Path, max_lines: int = 100) -> tuple[bool, int]:
        """간이 검증: 상위 N라인 파싱 ok & 총 라인 수 count"""
        count = 0
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    count += 1
                    if count <= max_lines:
                        json.loads(line)
        except Exception:
            return False, count
        return (count > 0), count

    def _write_manifest(base: Path, chunk_path: Path, count: int) -> None:
        mode = (os.getenv("MAIC_INDEX_MODE") or "STD").upper()
        manifest = {
            "build_id": time.strftime("%Y%m%d-%H%M%S"),
            "created_at": int(time.time()),
            "mode": mode,
            "file": "chunks.jsonl",
            "sha256": _sha256_file(chunk_path),
            "chunks": int(count),
            "persist_dir": str(base),
            "version": 2,
        }
        mf = base / "manifest.json"
        mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _lock_path(base: Path) -> Path:
        return base / ".lock"

    def _acquire_lock(base: Path, ttl_sec: int = 1800) -> bool:
        lp = _lock_path(base)
        now = int(time.time())
        if lp.exists():
            try:
                data = json.loads(lp.read_text(encoding="utf-8"))
                ts = int(data.get("ts") or 0)
                if now - ts < ttl_sec:
                    return False  # 다른 작업이 진행 중
            except Exception:
                pass
        try:
            lp.write_text(json.dumps({"ts": now, "pid": os.getpid()}), encoding="utf-8")
            return True
        except Exception:
            return False

    # ---------- 본문 ----------
    base = Path(dest_dir).expanduser() if dest_dir else _persist_dir()
    base.mkdir(parents=True, exist_ok=True)

    if not _acquire_lock(base):
        _set_brain_status(
            code="BUSY",
            msg="다른 인덱싱/복구 작업이 진행 중입니다.",
            origin="local",
            attached=False,
        )
        return False

    tmp_root: Optional[Path] = None
    try:
        # 1) tmp 작업 디렉터리
        tmp_root = Path(tempfile.mkdtemp(prefix=".build_", dir=str(base)))
        tmp_chunks = tmp_root / "chunks.jsonl"

        # 2) 빌더 호출(tmp로 유도)
        fn = _pick_reindex_fn()
        if not callable(fn):
            _set_brain_status(
                code="MISSING",
                msg="재인덱싱 함수가 없습니다.",
                origin="local",
                attached=False,
            )
            return False
        try:
            ret = fn(tmp_root)  # 선호 시그니처
        except TypeError:
            ret = fn()          # 레거시 시그니처
        except Exception as e:
            _set_brain_status(
                code="ERROR",
                msg=f"reindex 빌더 예외: {e}",
                origin="local",
                attached=False,
            )
            return False

        # 3) 후보 경로 수집 → tmp로 정리
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

        cands = [tmp_root]
        try:
            from pathlib import Path as _P
            if isinstance(ret, (str, _P)):
                cands.append(_P(ret).expanduser())
            elif isinstance(ret, dict):
                for k in ("output_dir", "out_dir", "persist_dir", "dir", "path", "chunks_dir"):
                    v = ret.get(k)
                    if isinstance(v, (str, _P)):
                        cands.append(_P(v).expanduser())
        except Exception:
            pass

        exact: list[Path] = []
        exact_gz: list[Path] = []
        dirs: list[Path] = []
        any_jsonl: list[Path] = []
        any_gz: list[Path] = []
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

        wrote = False
        # (A) exact match: chunks.jsonl
        if exact:
            best = max(exact, key=_size)
            try:
                if best.resolve() == tmp_chunks.resolve():
                    # 이미 목표 경로에 존재 → 복사 불필요
                    wrote = True
                else:
                    shutil.copy2(best, tmp_chunks)
                    wrote = True
            except Exception:
                if str(best) == str(tmp_chunks):
                    wrote = True
                else:
                    _set_brain_status(
                        code="ERROR",
                        msg=f"chunks 복사 예외: {best}",
                        origin="local",
                        attached=False,
                    )
                    return False
        # (B) exact gz
        elif exact_gz:
            best_gz = max(exact_gz, key=_size)
            wrote = _decompress_gz(best_gz, tmp_chunks)
        else:
            # (C) 디렉터리 병합
            for d in dirs:
                try:
                    bytes_written = 0
                    tmp_out = tmp_chunks.with_suffix(".jsonl.tmp")
                    tmp_out.unlink(missing_ok=True)
                    with tmp_out.open("wb") as w:
                        for p in sorted(d.glob("*.jsonl")):
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
                        if tmp_chunks.exists():
                            tmp_chunks.unlink()
                        tmp_out.replace(tmp_chunks)
                        wrote = True
                        break
                    tmp_out.unlink(missing_ok=True)
                except Exception:
                    continue
            # (D) fallback: *.jsonl / *.jsonl.gz
            if not wrote and any_jsonl:
                best_any = max(any_jsonl, key=_size)
                try:
                    if best_any.resolve() == tmp_chunks.resolve():
                        wrote = True
                    else:
                        shutil.copy2(best_any, tmp_chunks)
                        wrote = True
                except Exception:
                    if str(best_any) == str(tmp_chunks):
                        wrote = True
                    else:
                        _set_brain_status(
                            code="ERROR",
                            msg=f"fallback 복사 예외: {best_any}",
                            origin="local",
                            attached=False,
                        )
                        return False
            if not wrote and any_gz:
                best_any_gz = max(any_gz, key=_size)
                wrote = _decompress_gz(best_any_gz, tmp_chunks)

        if not wrote or (not tmp_chunks.exists()):
            _set_brain_status(
                code="MISSING",
                msg="재인덱싱 완료했지만 산출물(chunks.jsonl)을 찾지 못했습니다.",
                origin="local",
                attached=False,
            )
            return False

        # 4) 검증
        ok, lines = _verify_jsonl(tmp_chunks)
        if not ok:
            _set_brain_status(
                code="ERROR",
                msg="산출물 검증 실패(JSONL 파싱/라인수)",
                origin="local",
                attached=False,
            )
            return False

        # 5) 원자 스왑
        target = base / "chunks.jsonl"
        tmp_final = target.with_suffix(".jsonl.new")
        if tmp_final.exists():
            tmp_final.unlink()
        try:
            shutil.copy2(tmp_chunks, tmp_final)
            if target.exists():
                target.unlink()
            tmp_final.replace(target)
        except Exception as e:
            _set_brain_status(
                code="ERROR",
                msg=f"원자 스왑 실패: {e}",
                origin="local",
                attached=False,
            )
            return False

        # 6) manifest + ready
        _write_manifest(base, target, int(lines))
        _ensure_ready_signal(base)

        stt = index_status(base)
        if stt["local_ok"]:
            _set_brain_status(
                code="READY",
                msg="재인덱싱 완료(READY)",
                origin="local",
                attached=True,
            )
            return True
        _set_brain_status(
            code="MISSING",
            msg="재인덱싱 완료했지만 READY 조건 미충족",
            origin="local",
            attached=False,
        )
        return False
    finally:
        try:
            if tmp_root and tmp_root.exists():
                shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass
        try:
            (_persist_dir() / ".lock").unlink(missing_ok=True)
        except Exception:
            pass
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
