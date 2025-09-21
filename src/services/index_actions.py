
# =============================== [01] future import — START ===========================
from __future__ import annotations
# ================================ [01] future import — END ============================

# =============================== [02] module imports — START ==========================
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
import zipfile
import traceback
import importlib
import time
import os
import sys
try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore[assignment]

from .index_state import (
    INDEX_STEP_NAMES,
    ensure_index_state as _ensure_index_state,
    step_reset as _step_reset,
    step_set as _step_set,
    render_index_steps as _render_index_steps,
    log as _log,
)
# ================================ [02] module imports — END ===========================

# ============================= [03] local helpers — START =============================
def _persist_dir_safe() -> Path:
    """persist 경로를 안전하게 해석한다."""
    try:
        from src.core.persist import effective_persist_dir
        p = Path(str(effective_persist_dir())).expanduser()
        return p
    except Exception:
        return Path.home() / ".maic" / "persist"


def _stamp_persist(p: Path) -> None:
    """인덱스 완료 후 간단한 스탬프 파일을 남겨 변경시각 추적(베스트에포트)."""
    try:
        (p / ".stamp").write_text(str(int(time.time())), encoding="utf-8")
    except Exception:
        pass


def _load_prepared_lister():
    """prepared 파일 목록 조회 함수를 동적으로 로드한다."""
    tried: List[str] = []
    def _try(modname: str):
        try:
            m = importlib.import_module(modname)
            fn = getattr(m, "list_prepared_files", None)
            if callable(fn):
                tried.append(f"ok: {modname}")
                return fn
            tried.append(f"miss func: {modname}")
            return None
        except Exception as e:
            tried.append(f"fail: {modname} ({e})")
            return None

    for name in ("src.integrations.gdrive", "gdrive"):
        fn = _try(name)
        if fn:
            return fn, tried
    return None, tried


def _load_prepared_api():
    """prepared 소비/체크 API를 동적으로 로드한다."""
    tried2: List[str] = []

    def _try(modname: str):
        try:
            m = importlib.import_module(modname)
            chk_fn = getattr(m, "check_prepared_updates", None)
            mark_fn = getattr(m, "mark_prepared_consumed", None)
            if callable(chk_fn) and callable(mark_fn):
                tried2.append(f"ok: {modname}")
                return chk_fn, mark_fn
            tried2.append(f"miss attrs: {modname}")
            return None, None
        except Exception as e:
            tried2.append(f"fail: {modname} ({e})")
            return None, None

    for name in ("prepared", "gdrive", "src.prepared", "src.drive.prepared", "src.integrations.gdrive"):
        chk, mark = _try(name)
        if chk and mark:
            return chk, mark, tried2
    return None, None, tried2


def _resolve_owner_repo_and_token() -> Tuple[str, str, str]:
    """시크릿/환경변수에서 GitHub owner/repo/token을 해석."""
    def _secret(name: str, default: str = "") -> str:
        try:
            if st is not None:
                v = st.secrets.get(name)
                if isinstance(v, str) and v:
                    return v
        except Exception:
            pass
        return os.getenv(name, default)

    tok = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
    owner = _secret("GH_OWNER") or _secret("GITHUB_OWNER")
    repo = _secret("GH_REPO") or _secret("GITHUB_REPO_NAME")
    combo = _secret("GITHUB_REPO")
    if combo and "/" in combo:
        o, r = combo.split("/", 1)
        owner, repo = o.strip(), r.strip()
    return owner or "", repo or "", tok or ""


def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """앱의 _errlog가 있으면 위임, 없으면 콘솔 출력."""
    try:
        app_mod = sys.modules.get("__main__")
        app_err = getattr(app_mod, "_errlog", None)
        if callable(app_err):
            app_err(msg, where=where, exc=exc)
            return
    except Exception:
        pass
    print(f"[ERR]{' ' + where if where else ''} {msg}")
    if exc:
        traceback.print_exception(exc)
# ============================== [03] local helpers — END ==============================

# ============================= [04] public API — START ================================
def make_index_backup_zip(persist_dir: Path) -> Path:
    """persist 내용을 backups/index_<ts>.zip으로 압축."""
    backup_dir = persist_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    zpath = backup_dir / f"index_{int(time.time())}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _d, files in os.walk(str(persist_dir)):
            for fn in files:
                pth = Path(root) / fn
                # backups/ 내부의 오래된 zip은 제외(자기 자신 포함)
                if pth.is_file() and pth.suffix != ".zip":
                    zf.write(str(pth), arcname=str(pth.relative_to(persist_dir)))
    return zpath


def upload_index_zip_to_release(zip_path: Path, *, tag: str | None = None) -> str:
    """ZIP을 GitHub Release에 업로드(태그 없으면 index-<ts>). 실패시 예외."""
    owner, repo, tok = _resolve_owner_repo_and_token()
    if not (owner and repo and tok):
        raise RuntimeError("시크릿/리포 정보가 부족합니다(GITHUB_REPO/GITHUB_TOKEN 등).")
    try:
        from src.runtime.gh_release import GHConfig, GHReleases
    except Exception as exc:
        raise RuntimeError(f"릴리스 클라이언트 로드 실패: {exc}") from exc

    if tag is None:
        tag = f"index-{int(time.time())}"
    client = GHReleases(GHConfig(owner=owner, repo=repo, token=tok))
    rel = client.ensure_release(tag, name=tag)
    client.upload_asset(rel, zip_path)
    return f"OK: {zip_path.name} → {owner}/{repo} tag={tag}"


def collect_prepared_files() -> tuple[list[dict], list[str]]:
    """prepared 파일 목록과 디버그 문자열 목록을 반환한다."""
    lister, dbg = _load_prepared_lister()
    files: List[Dict[str, Any]] = []
    if lister:
        try:
            files = lister() or []
        except Exception as e:
            _errlog(f"prepared 목록 조회 실패: {e}", where="[collect_prepared_files]", exc=e)
    return files, dbg


def run_admin_index_job(req: Dict[str, Any]) -> None:
    """관리자 강제 인덱싱(동기). 상태 펄스+바, 스텝/로그 갱신."""
    if st is None:
        return

    # 진행 표시에 사용할 펄스 + 바(대략적 비율)
    status = st.status("⚙️ 인덱싱 준비 중", expanded=True)
    prog = st.progress(0)

    step_names = list(INDEX_STEP_NAMES)
    _ensure_index_state(step_names)
    _step_reset(step_names)
    _log("인덱싱 시작")

    used_persist = _persist_dir_safe()
    files_list, debug_msgs = collect_prepared_files()
    for msg in debug_msgs:
        _log("• " + msg, "warn")

    try:
        from src.rag import index_build as _idx
    except Exception as exc:
        status.update(label=f"❌ 인덱싱 모듈 로드 실패: {exc}", state="error")
        _log(f"인덱싱 모듈 로드 실패: {exc}", "err")
        _step_set(2, "fail", "모듈 로드 실패")
        try:
            # 앱의 가드가 있으면 리셋
            app_mod = sys.modules.get("__main__")
            _reset = getattr(app_mod, "_reset_rerun_guard", None)
            if callable(_reset):
                _reset("idx_run")
        except Exception:
            pass
        return

    try:
        # 1) persist 확인
        status.update(label="📁 persist 확인 중", state="running")
        _step_set(1, "run", "persist 확인 중")
        _step_set(1, "ok", str(used_persist))
        _log(f"persist={used_persist}")
        prog.progress(10)

        # 2) HQ 인덱싱
        status.update(label="⚙️ HQ 인덱싱 중 (prepared 전용)", state="running")
        _step_set(2, "run", "HQ 인덱싱 중")
        os.environ["MAIC_INDEX_MODE"] = "HQ"
        os.environ["MAIC_USE_PREPARED_ONLY"] = "1"
        _idx.rebuild_index()  # 시간이 걸릴 수 있음
        _step_set(2, "ok", "완료")
        _log("인덱싱 완료")
        prog.progress(60)

        # 산출물 위치 보정 + ready 표준화
        cj = used_persist / "chunks.jsonl"
        if not (cj.exists() and cj.stat().st_size > 0):
            try:
                cand = next(used_persist.glob("**/chunks.jsonl"))
                used_persist = cand.parent
                cj = cand
                _log(f"산출물 위치 자동조정: {used_persist}")
            except StopIteration:
                pass
        if cj.exists() and cj.stat().st_size > 0:
            try:
                (used_persist / ".ready").write_text("ready", encoding="utf-8")
            except Exception:
                pass
            _stamp_persist(used_persist)

        # 3) prepared 소비(seen 마킹)
        status.update(label="🧾 prepared 소비(seen) 마킹", state="running")
        _step_set(3, "run", "prepared 소비 중")
        try:
            chk, mark, dbg2 = _load_prepared_api()
            info: Dict[str, Any] = {}
            new_files: List[str] = []
            if callable(chk):
                try:
                    info = chk(used_persist, files_list) or {}
                except TypeError:
                    info = chk(used_persist) or {}
                new_files = list(info.get("files") or info.get("new") or [])
            else:
                for m in dbg2:
                    _log("• " + m, "warn")
            if new_files and callable(mark):
                try:
                    mark(used_persist, new_files)
                except TypeError:
                    mark(new_files)
                _log(f"소비(seen) {len(new_files)}건")
            _step_set(3, "ok", f"{len(new_files)}건")
        except Exception as e:
            _step_set(3, "fail", "소비 실패")
            _log(f"prepared 소비 실패: {e}", "err")
        prog.progress(75)

        # 4) 요약 계산
        status.update(label="📊 요약 계산", state="running")
        _step_set(4, "run", "요약 계산")
        try:
            from src.rag.index_status import get_index_summary
            s2 = get_index_summary(used_persist)
            _step_set(4, "ok", f"files={s2.total_files}, chunks={s2.total_chunks}")
            _log(f"요약 files={s2.total_files}, chunks={s2.total_chunks}")
        except Exception:
            _step_set(4, "ok", "요약 모듈 없음")
            _log("요약 모듈 없음", "warn")
        prog.progress(85)

        # 5) ZIP/Release 업로드(선택)
        auto_up = bool(req.get("auto_up"))
        if auto_up:
            status.update(label="⏫ ZIP 생성 및 Release 업로드...", state="running")
            _step_set(5, "run", "ZIP/Release 업로드")
            try:
                z = make_index_backup_zip(used_persist)
                msg = upload_index_zip_to_release(z, tag=f"index-{int(time.time())}")
                _step_set(5, "ok", "업로드 완료")
                _log(msg)
            except Exception as e:
                _step_set(5, "fail", f"upload_error: {e}")
                _log(f"업로드 실패: {e}", "err")
        else:
            _step_set(5, "skip", "건너뜀(자동 업로드 OFF)")
        prog.progress(100)

        status.update(label="✅ 강제 재인덱싱 완료", state="complete")
        if hasattr(st, "success"):
            st.success("강제 재인덱싱 완료 (prepared 전용)")
    except Exception as e:
        status.update(label=f"❌ 인덱싱 실패: {e}", state="error")
        _step_set(2, "fail", "인덱싱 실패")
        _log(f"인덱싱 실패: {e}", "err")
    finally:
        try:
            app_mod = sys.modules.get("__main__")
            _reset = getattr(app_mod, "_reset_rerun_guard", None)
            if callable(_reset):
                _reset("idx_run")
        except Exception:
            pass
# ============================== [04] public API — END =================================

# 편의 export
persist_dir_safe = _persist_dir_safe
