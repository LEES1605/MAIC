# =============================== [01] future import — START ===========================
from __future__ import annotations
# ================================ [01] future import — END ============================

# =============================== [02] module imports — START ==========================
import os
import json
import time
import traceback
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import streamlit as st
except Exception:
    st = None

from src.core.secret import promote_env as _promote_env, get as _secret_get
from src.core.persist import effective_persist_dir, share_persist_dir_to_session
from src.core.index_probe import (
    is_brain_ready as core_is_ready,
    mark_ready as core_mark_ready,
)
# ================================ [02] module imports — END ===========================

# =============================== [03] helpers(persist) — START ========================
def _persist_dir_safe() -> Path:
    try:
        return Path(str(effective_persist_dir())).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"


def _load_prepared_lister():
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
# ================================ [03] helpers(persist) — END =========================

# ===== [04] bootstrap env — START =====
# (안전상 중복 import 허용)
import os, time

def _bootstrap_env() -> None:
    try:
        _promote_env(keys=[
            "OPENAI_API_KEY", "OPENAI_MODEL",
            "GEMINI_API_KEY", "GEMINI_MODEL",
            "GH_TOKEN", "GITHUB_TOKEN",
            "GH_OWNER", "GH_REPO", "GITHUB_OWNER", "GITHUB_REPO_NAME", "GITHUB_REPO",
            "APP_MODE", "AUTO_START_MODE", "LOCK_MODE_FOR_STUDENTS",
            "APP_ADMIN_PASSWORD", "DISABLE_BG",
            "MAIC_PERSIST_DIR",
            "GDRIVE_PREPARED_FOLDER_ID", "GDRIVE_BACKUP_FOLDER_ID",
        ])
    except Exception:
        pass

    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")


_bootstrap_env()
if st:
    # 페이지 타이틀/레이아웃
    try:
        st.set_page_config(page_title="LEES AI Teacher",
                           layout="wide", initial_sidebar_state="collapsed")
    except Exception:
        pass

    # (A) experimental_* 호환 래퍼(경고 제거)
    try:
        if hasattr(st, "experimental_get_query_params"):
            st.experimental_get_query_params = lambda: st.query_params  # type: ignore
        if hasattr(st, "experimental_set_query_params"):
            def _set_qp(**kwargs: object) -> None:
                for k, v in kwargs.items():
                    st.query_params[k] = v  # type: ignore[index]
            st.experimental_set_query_params = _set_qp  # type: ignore
    except Exception:
        pass

    # (B) 기본 멀티페이지 네비 전역 숨김(학생/관리자 공통) — 로그인 화면 잔재 제거
    try:
        st.markdown(
            "<style>"
            "nav[data-testid='stSidebarNav']{display:none!important;}"
            "div[data-testid='stSidebarNav']{display:none!important;}"
            "section[data-testid='stSidebar'] [data-testid='stSidebarNav']{display:none!important;}"
            "section[data-testid='stSidebar'] ul[role='list']{display:none!important;}"
            "</style>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    # (C) admin/goto 쿼리 파라미터 → 관리자 플래그 ON/OFF (영구 수정)
    try:
        v = st.query_params.get("admin", None)
        goto = st.query_params.get("goto", None)

        def _norm(x: object) -> str:
            return str(x).strip().lower()

        def _truthy(x: object) -> bool:
            return _norm(x) in ("1", "true", "on", "yes", "y")

        def _falsy(x: object) -> bool:
            return _norm(x) in ("0", "false", "off", "no", "n")

        def _has(param: object, pred) -> bool:
            if isinstance(param, list):
                return any(pred(x) for x in param)
            return pred(param) if param is not None else False

        prev = bool(st.session_state.get("admin_mode", False))
        new_mode = prev

        # 켜기: admin=1/true/on or goto=admin
        if _has(v, _truthy) or _has(goto, lambda x: _norm(x) == "admin"):
            new_mode = True

        # 끄기(우선): admin=0/false/off or goto=back|prompt|home
        if _has(v, _falsy) or _has(goto, lambda x: _norm(x) in ("back", "prompt", "home")):
            new_mode = False

        if new_mode != prev:
            if new_mode:
                st.session_state["_admin_ok"] = True
            else:
                st.session_state.pop("_admin_ok", None)
            st.session_state["admin_mode"] = new_mode
            st.session_state["_ADMIN_TOGGLE_TS"] = time.time()
            st.rerun()
    except Exception:
        pass

    # (D) 관리자/학생 크롬 적용 — 학생은 숨김, 관리자는 최소 사이드바 즉시 렌더
    try:
        _sider = __import__("src.ui.utils.sider", fromlist=["apply_admin_chrome"])
        getattr(_sider, "apply_admin_chrome", lambda **_: None)(
            back_page="app.py", icon_only=True
        )
    except Exception:
        pass
# ===== [04] bootstrap env — END =====




# ======================= [05] path & logger — START =======================
PERSIST_DIR: Path = effective_persist_dir()
try:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

try:
    share_persist_dir_to_session(PERSIST_DIR)
except Exception:
    pass


def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    try:
        prefix = f"{where} " if where else ""
        print(f"[ERR] {prefix}{msg}")
        if exc:
            traceback.print_exception(exc)
        try:
            import streamlit as _st
            with _st.expander("자세한 오류 로그", expanded=False):
                detail = ""
                if exc:
                    try:
                        detail = "".join(
                            traceback.format_exception(type(exc), exc, exc.__traceback__)
                        )
                    except Exception:
                        detail = "traceback 사용 불가"
                _st.code(f"{prefix}{msg}\n{detail}")
        except Exception:
            pass
    except Exception:
        pass
# ===================== [05] path & logger — END ========================

# ======================== [06] admin gate — START ========================
def _is_admin_view() -> bool:
    if st is None:
        return False
    try:
        ss = st.session_state
        if ss.get("is_admin") and not ss.get("admin_mode"):
            ss["admin_mode"] = True
            try:
                del ss["is_admin"]
            except Exception:
                pass
        return bool(ss.get("admin_mode"))
    except Exception:
        return False
# ========================= [06] admin gate — END ==============================

# ========================= [07] rerun guard — START =============================
import time
from typing import Any, Dict

def _safe_rerun(tag: str, ttl: float = 0.3) -> None:
    """
    Debounced rerun. One rerun per 'tag' within TTL seconds.
    - TTL 기본값 0.3s(UX↑)
    - 만료 시 기존 엔트리를 삭제하여 재시도 안정성↑
    """
    s = globals().get("st", None)
    if s is None:
        return
    try:
        ss = getattr(s, "session_state", None)
        if ss is None:
            return

        tag = str(tag or "rerun")
        try:
            ttl_s = float(ttl)
            if ttl_s <= 0:
                ttl_s = 0.3
        except Exception:
            ttl_s = 0.3

        key = "__rerun_counts__"
        counts = ss.get(key)
        if not isinstance(counts, dict):
            counts = {}

        rec = counts.get(tag) or {}
        cnt = int(rec.get("count", 0)) if isinstance(rec, dict) else int(rec or 0)
        exp = float(rec.get("expires_at", 0.0)) if isinstance(rec, dict) else 0.0

        now = time.time()
        # 만료 시 엔트리 제거(메모리 위생 + 재시도 안정)
        if exp and now >= exp:
            try:
                counts.pop(tag, None)
            except Exception:
                counts = {}
            cnt = 0
            exp = 0.0

        # TTL 안에서는 중복 rerun 차단
        if cnt >= 1 and (exp and now < exp):
            return

        counts[tag] = {"count": cnt + 1, "expires_at": now + ttl_s}
        ss[key] = counts

        try:
            s.rerun()
        except Exception:
            try:
                s.experimental_rerun()
            except Exception:
                pass
    except Exception:
        # 절대 예외 전파 금지 (UX 보호)
        pass


def _reset_rerun_guard(tag: str) -> None:
    """
    Clear rerun-guard entry for a given tag.
    - 인덱싱 잡 종료 후 반드시 호출하여 다음 클릭이 막히지 않도록 함.
    """
    s = globals().get("st", None)
    if s is None:
        return
    try:
        ss = getattr(s, "session_state", None)
        if ss is None:
            return
        key = "__rerun_counts__"
        counts = ss.get(key)
        if isinstance(counts, dict) and tag in counts:
            counts = dict(counts)
            counts.pop(tag, None)
            ss[key] = counts
    except Exception:
        pass
# ================================= [07] rerun guard — END =============================


# =============================== [08] header — START ==================================
def _header() -> None:
    """
    헤더 배지는 '파일시스템 READY' 기준(SSOT)을 사용한다.
    - src.ui.header.render 가 있으면 그대로 사용하고,
      실패/부재 시에는 persist 상태를 직접 검사해 렌더링한다.
    """
    # 1) 외부 헤더가 있으면 먼저 사용
    try:
        from src.ui.header import render as _render_header
        _render_header()
        return
    except Exception:
        pass

    # 2) 폴백: 파일시스템 READY 기준 표시
    if st is None:
        return
    try:
        p = _persist_dir_safe()
        ok = core_is_ready(p)
    except Exception:
        ok = False
        p = _persist_dir_safe()

    badge = "🟢 READY" if ok else "🟡 준비중"
    st.markdown(f"{badge} **LEES AI Teacher**")
    with st.container():
        st.caption("Persist Dir")
        st.code(str(p), language="text")
# ================================== [08] header — END =================================

# =============================== [09] background — START ===============================
def _inject_modern_bg_lib() -> None:
    try:
        s = globals().get("st", None)
        if s is not None and hasattr(s, "session_state"):
            s.session_state["__bg_lib_injected__"] = False
    except Exception:
        pass


def _mount_background(**_kw) -> None:
    return
# ================================= [09] background — END ===============================

# =============================== [10] auto-restore — START ============================
def _boot_auto_restore_index() -> None:
    """
    최신 릴리스 자동 복원 훅.
    규칙:
      - 로컬 준비 상태(.ready + chunks.jsonl)는 별도 기록(_INDEX_LOCAL_READY)
      - 원격 최신 태그와 로컬 저장 메타가 '일치'면 복원 생략(최신으로 간주)
      - '불일치'면 복원 강제
      - 복원 성공 시에만 세션에 _INDEX_IS_LATEST=True 로 기록(헤더는 이 값으로만 초록 표시)
    """
    # 멱등 보호: 한 세션에서 한 번만 수행
    try:
        if "st" in globals() and st is not None:
            if st.session_state.get("_BOOT_RESTORE_DONE"):
                return
    except Exception:
        pass

    p = effective_persist_dir()
    cj = p / "chunks.jsonl"
    rf = p / ".ready"

    # --- 공용 판정기(역호환 허용) 로드 ---
    try:
        from src.core.readiness import is_ready_text, normalize_ready_file
    except Exception:
        # 폴백(동일 로직)
        def _norm(x: str | bytes | None) -> str:
            if x is None:
                return ""
            if isinstance(x, bytes):
                x = x.decode("utf-8", "ignore")
            return x.replace("\ufeff", "").strip().lower()

        def is_ready_text(x):  # type: ignore
            return _norm(x) in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}

        def normalize_ready_file(_):  # type: ignore
            try:
                (p / ".ready").write_text("ready", encoding="utf-8")
                return True
            except Exception:
                return False

    # --- 로컬 준비 상태 계산 & 기록 ---
    ready_txt = ""
    try:
        if rf.exists():
            ready_txt = rf.read_text(encoding="utf-8")
    except Exception:
        ready_txt = ""
    local_ready = cj.exists() and cj.stat().st_size > 0 and is_ready_text(ready_txt)

    try:
        if "st" in globals() and st is not None:
            st.session_state["_INDEX_LOCAL_READY"] = bool(local_ready)
            # 헤더가 사용할 최신 여부 플래그는 기본 False로 초기화(부팅 직후 초록 금지)
            st.session_state.setdefault("_INDEX_IS_LATEST", False)
    except Exception:
        pass

    # --- 복원 메타 유틸(있으면 사용) ---
    def _safe_load_meta(path):
        try:
            return load_restore_meta(path)  # type: ignore[name-defined]
        except Exception:
            return None

    def _safe_meta_matches(meta, tag: str) -> bool:
        try:
            return bool(meta_matches_tag(meta, tag))  # type: ignore[name-defined]
        except Exception:
            return False

    def _safe_save_meta(path, tag: str | None, release_id: int | None):
        try:
            return save_restore_meta(path, tag=tag, release_id=release_id)  # type: ignore[name-defined]
        except Exception:
            return None

    stored_meta = _safe_load_meta(p)

    # --- GitHub Releases 최신 메타 취득 ---
    repo_full = os.getenv("GITHUB_REPO", "")
    token = os.getenv("GITHUB_TOKEN", None)
    try:
        if "st" in globals() and st is not None:
            repo_full = st.secrets.get("GITHUB_REPO", repo_full)
            token = st.secrets.get("GITHUB_TOKEN", token)
    except Exception:
        pass

    if not repo_full or "/" not in str(repo_full):
        # 원격 확인 불가: 최신 여부 판단 불가 → 초록 금지(_INDEX_IS_LATEST=False 유지)
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
        except Exception:
            pass
        return

    owner, repo = str(repo_full).split("/", 1)

    try:
        from src.runtime.gh_release import GHConfig, GHReleases
    except Exception:
        # GH API 사용 불가: 초록 금지 유지
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
        except Exception:
            pass
        return

    gh = GHReleases(GHConfig(owner=owner, repo=repo, token=token))

    remote_tag: Optional[str] = None
    remote_release_id: Optional[int] = None
    try:
        latest_rel = gh.get_latest_release()
        remote_tag = str(latest_rel.get("tag_name") or latest_rel.get("name") or "").strip() or None
        raw_id = latest_rel.get("id")
        try:
            remote_release_id = int(raw_id)
        except (TypeError, ValueError):
            remote_release_id = None
    except Exception:
        remote_tag = None
        remote_release_id = None
    finally:
        try:
            if "st" in globals() and st is not None:
                st.session_state["_LATEST_RELEASE_TAG"] = remote_tag
                st.session_state["_LATEST_RELEASE_ID"] = remote_release_id
                if stored_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(stored_meta, "to_dict", lambda: {})()
        except Exception:
            pass

    # --- 일치/불일치 판정 ---
    if local_ready and remote_tag and _safe_meta_matches(stored_meta, remote_tag):
        # 이미 최신(메타 일치) → 복원 생략, 최신으로 간주
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = True  # 최신으로 표기
        except Exception:
            pass
        return

    # 이외(불일치 또는 로컬 미준비): 최신 복원 강제
    # 태그 후보: 정적 + 동적(최근 5년)
    try:
        import datetime as _dt
        this_year = _dt.datetime.utcnow().year
        dyn_tags = [f"index-{y}-latest" for y in range(this_year, this_year - 5, -1)]
    except Exception:
        dyn_tags = []
    tag_candidates = ["indices-latest", "index-latest"] + dyn_tags + ["latest"]
    asset_candidates = ["indices.zip", "persist.zip", "hq_index.zip", "prepared.zip"]

    try:
        result = gh.restore_latest_index(
            tag_candidates=tag_candidates,
            asset_candidates=asset_candidates,
            dest=p,
            clean_dest=True,
        )

        # 복원 성공 → .ready 표준화 & 메타 저장 & 최신으로 표기
        normalize_ready_file(p)
        saved_meta = _safe_save_meta(
            p,
            tag=(getattr(result, "tag", None) or remote_tag),
            release_id=(getattr(result, "release_id", None) or remote_release_id),
        )

        try:
            if "st" in globals() and st is not None:
                st.session_state["_PERSIST_DIR"] = p.resolve()
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state["_INDEX_IS_LATEST"] = True   # 최신 복원 성공 → 초록 근거
                st.session_state["_INDEX_LOCAL_READY"] = True  # 로컬도 준비됨
                if saved_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(saved_meta, "to_dict", lambda: {})()
        except Exception:
            pass
    except Exception:
        # 복원 실패 → 최신 아님(초록 금지), 로컬 준비여부에 따라 헤더에서 노랑/오렌지 표기
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = False
        except Exception:
            pass
        return
# ================================= [10] auto-restore — END ============================



# =============================== [11] boot hooks — START ==============================
def _boot_autoflow_hook() -> None:
    try:
        mod = None
        for name in ("src.ui_orchestrator", "ui_orchestrator"):
            try:
                mod = importlib.import_module(name)
                break
            except Exception:
                mod = None
        if mod and hasattr(mod, "autoflow_boot_check"):
            mod.autoflow_boot_check(interactive=_is_admin_view())
    except Exception as e:
        _errlog(f"boot_autoflow_hook: {e}", where="[boot_hook]", exc=e)


def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False) -> None:
    if st is None:
        return
    ss = st.session_state
    ss["brain_status_code"] = code
    ss["brain_status_msg"] = msg
    ss["brain_source"] = source
    ss["brain_attached"] = bool(attached)
    ss["restore_recommend"] = code in ("MISSING", "ERROR")
    ss.setdefault("index_decision_needed", False)
    ss.setdefault("index_change_stats", {})


def _auto_start_once() -> None:
    try:
        if st is None or not hasattr(st, "session_state"):
            return
        if st.session_state.get("_auto_start_done"):
            return
        st.session_state["_auto_start_done"] = True
    except Exception:
        return

    mode = (os.getenv("AUTO_START_MODE") or _secret_get("AUTO_START_MODE", "off") or "off").lower()
    if mode not in ("restore", "on"):
        return

    try:
        rel = importlib.import_module("src.backup.github_release")
        fn = getattr(rel, "restore_latest", None)
    except Exception:
        fn = None

    used_persist = effective_persist_dir()
    ok = False
    if callable(fn):
        try:
            ok = bool(fn(dest_dir=used_persist))
        except Exception as e:
            _errlog(f"restore_latest failed: {e}", where="[auto_start]", exc=e)
            ok = False
    else:
        try:
            _boot_auto_restore_index()
            ok = core_is_ready(used_persist)
        except Exception:
            ok = False

    if ok:
        try:
            core_mark_ready(used_persist)  # 표준화: "ready"
        except Exception:
            pass
        if hasattr(st, "toast"):
            st.toast("자동 복원 완료", icon="✅")
        else:
            st.success("자동 복원 완료")
        _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
        _safe_rerun("auto_start", ttl=1)
# ================================= [11] boot hooks — END ==============================
# ======================= [11.4] admin index: request consumer — START =======================
def _consume_admin_index_request() -> None:
    """
    렌더 사이클 초입에서 _IDX_REQ를 소비하여 인덱싱 잡을 즉시 실행.
    - 버튼 핸들러는 요청만 적재하고 rerun
    - 다음 사이클 시작 시 이 소비자가 항상 먼저 실행되어야 '아무 일 없음'을 방지
    """
    if st is None:
        return
    try:
        req = st.session_state.pop("_IDX_REQ", None)
    except Exception:
        req = None

    if req:
        try:
            _run_admin_index_job(req)
        except Exception as e:
            try:
                _log(f"인덱싱 소비 실패: {e}", "err")
            except Exception:
                pass
# ======================== [11.4] admin index: request consumer — END ========================

# ============================ [11.5] admin index helpers — START ======================
_INDEX_STEP_NAMES: Tuple[str, ...] = (
    "persist 확인",
    "HQ 인덱싱",
    "prepared 소비",
    "요약 계산",
    "ZIP/Release 업로드",
)


def _ensure_index_state(step_names: Sequence[str] | None = None) -> None:
    if st is None:
        return
    names = list(step_names or _INDEX_STEP_NAMES)
    steps = st.session_state.get("_IDX_STEPS")
    if not isinstance(steps, list) or len(steps) != len(names):
        st.session_state["_IDX_STEPS"] = [
            {"name": name, "status": "wait", "detail": ""} for name in names
        ]
    st.session_state.setdefault("_IDX_LOGS", [])
    st.session_state.setdefault("_IDX_STEPPER_PH", None)
    st.session_state.setdefault("_IDX_STATUS_PH", None)


def _steps() -> List[Dict[str, Any]]:
    if st is None:
        return []
    _ensure_index_state()
    raw = st.session_state.get("_IDX_STEPS", [])
    if isinstance(raw, list):
        return raw
    steps = [{"name": name, "status": "wait", "detail": ""} for name in _INDEX_STEP_NAMES]
    st.session_state["_IDX_STEPS"] = steps
    return steps


def _render_stepper(force: bool = False) -> None:
    if st is None:
        return
    _ensure_index_state()
    placeholder = st.session_state.get("_IDX_STEPPER_PH")
    if placeholder is None:
        if not force:
            return
        placeholder = st.empty()
        st.session_state["_IDX_STEPPER_PH"] = placeholder
    steps = _steps()
    icon_map = {"wait": "⏸", "run": "⏳", "ok": "✅", "fail": "❌", "skip": "⏭"}
    with placeholder.container():
        if not steps:
            st.caption("표시할 단계가 없습니다.")
            return
        total = len(steps)
        done = sum(1 for step in steps if step.get("status") in {"ok", "skip"})
        if total:
            st.progress(int(done / total * 100))
            st.caption(f"{done}/{total} 단계 완료")
        else:
            st.progress(0)
        for idx, step in enumerate(steps, start=1):
            name = str(step.get("name") or "")
            status = str(step.get("status") or "wait")
            detail = str(step.get("detail") or "")
            icon = icon_map.get(status, "•")
            if detail:
                st.write(f"{idx}. {icon} **{name}** — {detail}")
            else:
                st.write(f"{idx}. {icon} **{name}**")


def _render_status(force: bool = False) -> None:
    if st is None:
        return
    _ensure_index_state()
    placeholder = st.session_state.get("_IDX_STATUS_PH")
    if placeholder is None:
        if not force:
            return
        placeholder = st.empty()
        st.session_state["_IDX_STATUS_PH"] = placeholder
    logs = st.session_state.get("_IDX_LOGS", [])
    icon_map = {"info": "ℹ️", "warn": "⚠️", "err": "❌"}
    with placeholder.container():
        if not logs:
            st.caption("로그가 없습니다.")
            return
        for entry in logs[-50:]:
            level = str(entry.get("level") or "info")
            message = str(entry.get("message") or "")
            icon = icon_map.get(level, "•")
            st.write(f"{icon} {message}")


def _step_reset(step_names: Sequence[str] | None = None) -> None:
    if st is None:
        return
    names = list(step_names or _INDEX_STEP_NAMES)
    _ensure_index_state(names)
    st.session_state["_IDX_STEPS"] = [
        {"name": name, "status": "wait", "detail": ""} for name in names
    ]
    st.session_state["_IDX_LOGS"] = []
    placeholder = st.session_state.get("_IDX_STEPPER_PH")
    if placeholder is not None:
        try:
            placeholder.empty()
        except Exception:
            pass
    placeholder2 = st.session_state.get("_IDX_STATUS_PH")
    if placeholder2 is not None:
        try:
            placeholder2.empty()
        except Exception:
            pass
    _render_stepper()
    _render_status()


def _step_set(step_index: int, status: str, detail: str) -> None:
    if st is None:
        return
    steps = _steps()
    if not steps:
        return
    idx = max(0, min(step_index - 1, len(steps) - 1))
    steps[idx]["status"] = status
    steps[idx]["detail"] = detail
    st.session_state["_IDX_STEPS"] = steps
    if st.session_state.get("_IDX_STEPPER_PH") is not None:
        _render_stepper()


def _render_logs_if_ready() -> None:
    if st is None:
        return
    if st.session_state.get("_IDX_STATUS_PH") is not None:
        _render_status()


def _log(message: str, level: str = "info") -> None:
    ts = int(time.time())
    if st is None:
        print(f"[IDX][{level}] {message}")
        return
    _ensure_index_state()
    logs = st.session_state.setdefault("_IDX_LOGS", [])
    logs.append({"ts": ts, "level": level, "message": message})
    st.session_state["_IDX_LOGS"] = logs[-200:]
    _render_logs_if_ready()


def _stamp_persist(path: Path) -> None:
    try:
        stamp_path = path / ".last_index_ts"
        stamp_path.write_text(str(int(time.time())), encoding="utf-8")
    except Exception:
        pass


def _collect_prepared_files() -> Tuple[List[Dict[str, Any]], List[str]]:
    files_list: List[Dict[str, Any]] = []
    lister, debug_msgs = _load_prepared_lister()
    dbg: List[str] = list(debug_msgs or [])
    if callable(lister):
        try:
            files_list = lister() or []
        except Exception as exc:
            dbg.append(f"list_prepared_files 실패: {exc}")
    return files_list, dbg


def _run_admin_index_job(req: Dict[str, Any]) -> None:
    if st is None:
        return

    step_names = list(_INDEX_STEP_NAMES)
    _ensure_index_state(step_names)
    _step_reset(step_names)
    _log("인덱싱 시작")

    used_persist = _persist_dir_safe()
    files_list, debug_msgs = _collect_prepared_files()
    for msg in debug_msgs:
        _log("• " + msg, "warn")

    try:
        from src.rag import index_build as _idx
    except Exception as exc:
        _log(f"인덱싱 모듈 로드 실패: {exc}", "err")
        _step_set(2, "fail", "모듈 로드 실패")
        return

    try:
        _step_set(1, "run", "persist 확인 중")
        _step_set(1, "ok", str(used_persist))
        _log(f"persist={used_persist}")

        _step_set(2, "run", "HQ 인덱싱 중")
        os.environ["MAIC_INDEX_MODE"] = "HQ"
        os.environ["MAIC_USE_PREPARED_ONLY"] = "1"
        _idx.rebuild_index()
        _step_set(2, "ok", "완료")
        _log("인덱싱 완료")

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

        _step_set(4, "run", "요약 계산")
        try:
            from src.rag.index_status import get_index_summary

            s2 = get_index_summary(used_persist)
            _step_set(4, "ok", f"files={s2.total_files}, chunks={s2.total_chunks}")
            _log(f"요약 files={s2.total_files}, chunks={s2.total_chunks}")
        except Exception:
            _step_set(4, "ok", "요약 모듈 없음")
            _log("요약 모듈 없음", "warn")

        if req.get("auto_up"):
            _step_set(5, "run", "ZIP/Release 업로드")

            def _secret(name: str, default: str = "") -> str:
                try:
                    v = st.secrets.get(name)
                    if isinstance(v, str) and v:
                        return v
                except Exception:
                    pass
                return os.getenv(name, default)

            def _resolve_owner_repo() -> Tuple[str, str]:
                owner = _secret("GH_OWNER") or _secret("GITHUB_OWNER")
                repo = _secret("GH_REPO") or _secret("GITHUB_REPO_NAME")
                combo = _secret("GITHUB_REPO")
                if combo and "/" in combo:
                    o, r = combo.split("/", 1)
                    owner, repo = o.strip(), r.strip()
                return owner or "", repo or ""

            tok = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
            ow, rp = _resolve_owner_repo()
            if tok and ow and rp:
                import zipfile

                backup_dir = used_persist / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                z = backup_dir / f"index_{int(time.time())}.zip"
                with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _d, _f in os.walk(str(used_persist)):
                        for fn in _f:
                            pth = Path(root) / fn
                            zf.write(str(pth), arcname=str(pth.relative_to(used_persist)))

                tag = f"index-{int(time.time())}"
                try:
                    from src.runtime.gh_release import GHConfig, GHError, GHReleases

                    client = GHReleases(GHConfig(owner=ow, repo=rp, token=tok))
                    rel = client.ensure_release(tag, name=tag)
                    client.upload_asset(rel, z)
                    _step_set(5, "ok", "업로드 완료")
                except GHError as e:
                    _step_set(5, "fail", str(e))
                except Exception as e:
                    _step_set(5, "fail", f"upload_error: {e}")
            else:
                _step_set(5, "skip", "시크릿 없음")
        else:
            _step_set(5, "skip", "건너뜀")

        st.success("강제 재인덱싱 완료 (prepared 전용)")
    except Exception as e:
        _step_set(2, "fail", "인덱싱 실패")
        _log(f"인덱싱 실패: {e}", "err")
# ============================= [11.5] admin index helpers — END ==================

# =============================== [12] diag header — START =============================
def _render_index_orchestrator_header() -> None:
    if "st" not in globals() or st is None:
        return

    # 공용 판정기(역호환 허용)
    try:
        from src.core.readiness import is_ready_text
    except Exception:
        def _norm(x: str | bytes | None) -> str:
            if x is None:
                return ""
            if isinstance(x, bytes):
                x = x.decode("utf-8", "ignore")
            return x.replace("\ufeff", "").strip().lower()
        def is_ready_text(x):  # type: ignore
            return _norm(x) in {"ready", "ok", "true", "1", "on", "yes", "y", "green"}

    st.markdown("### 🧪 인덱스 오케스트레이터")
    persist = _persist_dir_safe()
    with st.container():
        st.caption("Persist Dir")
        st.code(str(persist), language="text")

    # 로컬 준비 상태 재계산(세션 키 보정)
    cj = persist / "chunks.jsonl"
    rf = persist / ".ready"
    try:
        ready_txt = rf.read_text(encoding="utf-8") if rf.exists() else ""
    except Exception:
        ready_txt = ""
    local_ready = cj.exists() and cj.stat().st_size > 0 and is_ready_text(ready_txt)
    st.session_state["_INDEX_LOCAL_READY"] = bool(local_ready)

    # 최신 여부(헤더 칩 결정용)
    is_latest = bool(st.session_state.get("_INDEX_IS_LATEST", False))
    latest_tag = st.session_state.get("_LATEST_RELEASE_TAG")

    # 칩 계산
    if is_latest:
        badge = "🟩 준비완료"
        badge_code = "READY"
        badge_desc = f"최신 릴리스 적용됨 (tag={latest_tag})" if latest_tag else "최신 릴리스 적용됨"
    elif local_ready:
        badge = "🟨 준비중(로컬 인덱스 감지)"
        badge_code = "MISSING"  # 글로벌 상단용 코드 체계 유지
        badge_desc = "로컬 인덱스는 있으나 최신 릴리스와 불일치 또는 미확인"
    else:
        badge = "🟧 없음"
        badge_code = "MISSING"
        badge_desc = "인덱스 없음"

    st.markdown(f"**상태**\n\n{badge}")

    # 상단 글로벌 배지 동기화
    try:
        _set_brain_status(badge_code, badge_desc, "index", attached=(badge_code == "READY"))
    except Exception:
        pass

    if _is_admin_view():
        cols = st.columns([1, 1, 2])
        if cols[0].button("⬇️ Release에서 최신 인덱스 복원", use_container_width=True):
            try:
                _boot_auto_restore_index()
                st.success("Release 복원을 시도했습니다. 상태를 확인하세요.")
            except Exception as e:
                st.error(f"복원 실행 실패: {e}")

        if cols[1].button("✅ 로컬 구조 검증", use_container_width=True):
            try:
                ok = local_ready
                rec = {
                    "result": "성공" if ok else "실패",
                    "chunk": str(cj),
                    "ready": ready_txt.strip() or "(없음)",
                    "persist": str(persist),
                    "latest_tag": latest_tag,
                    "is_latest": is_latest,
                    "ts": int(time.time()),
                }
                st.session_state["_LAST_RESTORE_CHECK"] = rec

                if ok:
                    st.success("검증 성공: chunks.jsonl 존재 & .ready 유효")
                else:
                    st.error("검증 실패: 산출물/ready 상태가 불일치")
            except Exception as e:
                st.error(f"검증 실행 실패: {e}")

        with st.expander("최근 검증/복원 기록", expanded=False):
            rec = st.session_state.get("_LAST_RESTORE_CHECK")
            st.json(rec or {"hint": "위의 복원/검증 버튼을 사용해 기록을 남길 수 있습니다."})

        with st.expander("ℹ️ 최신 릴리스/메타 정보", expanded=False):
            st.write({
                "latest_release_tag": latest_tag,
                "latest_release_id": st.session_state.get("_LATEST_RELEASE_ID"),
                "last_restore_meta": st.session_state.get("_LAST_RESTORE_META"),
                "is_latest": is_latest,
                "local_ready": local_ready,
            })

        # (선택) 기존 Release 후보 디버그 존재 시 호출
        try:
            _render_release_candidates_debug()
        except Exception:
            pass

    st.info(
        "강제 인덱싱(HQ, 느림)·백업과 인덱싱 파일 미리보기는 **관리자 인덱싱 패널**에서 합니다. "
        "관리자 모드 진입 후 아래 섹션으로 이동하세요.",
        icon="ℹ️",
    )
    st.markdown("<span id='idx-admin-panel'></span>", unsafe_allow_html=True)
# ================================= [12] diag header — END =============================


# =========================== [13] admin indexing panel — START ===========================
def _render_admin_index_panel() -> None:
    """
    관리자 인덱싱 패널 본문.
    - 패널 시작 직후 요청 소비자(_consume_admin_index_request) 호출(가장 중요)
    - 버튼은 _IDX_REQ 적재 → _safe_rerun('idx_run', 0.3)로 다음 사이클에서 실행
    """
    if st is None:
        return

    # 1) 렌더 초입: 요청 소비
    _consume_admin_index_request()

    st.markdown("### 🔧 관리자 인덱싱 패널 (prepared 전용)")

    # 옵션: ZIP/Release 자동 업로드 여부
    c1, c2 = st.columns([1, 1])
    with c1:
        auto_zip = st.toggle("인덱싱 후 ZIP/Release 업로드", value=False, help="GH_TOKEN/GITHUB_REPO 필요")
    with c2:
        show_debug = st.toggle("디버그 로그 표시", value=True)

    # 실행 버튼
    if st.button("🚀 강제 재인덱싱(HQ, prepared)", type="primary", use_container_width=True, key="idx_run_btn"):
        try:
            st.session_state["_IDX_REQ"] = {"auto_up": bool(auto_zip), "debug": bool(show_debug)}
        except Exception:
            st.session_state["_IDX_REQ"] = {"auto_up": False}
        # 다음 사이클에서 소비되도록 안전 rerun (중복 제한 TTL 0.3s)
        _safe_rerun("idx_run", ttl=0.3)

    # 진행/상태 패널(기존 스텝 로거 사용 가정)
    try:
        _render_index_steps()  # 이미 존재하는 스텝 표시 함수가 있다면 호출
    except Exception:
        pass
# ============================ [13] admin indexing panel — END ============================

# =============================== [14] admin legacy — START ============================
def _render_admin_panels() -> None:
    # legacy 자리표시자(문법 안정 목적). 현재는 사용하지 않습니다.
    return None
# ================================= [14] admin legacy — END ============================


# =============================== [15] prepared scan — START ===========================
def _render_admin_prepared_scan_panel() -> None:
    if st is None or not _is_admin_view():
        return

    st.markdown("<h4>🔍 새 파일 스캔(인덱싱 없이)</h4>", unsafe_allow_html=True)

    c1, c2, _c3 = st.columns([1, 1, 2])
    act_scan = c1.button("🔍 스캔 실행", use_container_width=True)
    act_clear = c2.button("🧹 화면 지우기", use_container_width=True)

    if act_clear:
        st.session_state.pop("_PR_SCAN_RESULT", None)
        _safe_rerun("pr_scan_clear", ttl=1)

    prev = st.session_state.get("_PR_SCAN_RESULT")
    if isinstance(prev, dict) and not act_scan:
        st.caption("이전에 실행한 스캔 결과:")
        st.json(prev)

    if not act_scan:
        return

    idx_persist = _persist_dir_safe()
    lister, dbg1 = _load_prepared_lister()
    files_list: List[Dict[str, Any]] = []
    if lister:
        try:
            files_list = lister() or []
        except Exception as e:
            st.error(f"prepared 목록 조회 실패: {e}")
    else:
        with st.expander("디버그(파일 나열 함수 로드 경로)"):
            st.write("\n".join(dbg1) or "(정보 없음)")

    chk, _mark, dbg2 = _load_prepared_api()
    info: Dict[str, Any] = {}
    new_files: List[str] = []
    if callable(chk):
        try:
            info = chk(idx_persist, files_list) or {}
        except TypeError:
            info = chk(idx_persist) or {}
        except Exception as e:
            st.error(f"스캔 실행 실패: {e}")
            info = {}
        try:
            new_files = list(info.get("files") or info.get("new") or [])
        except Exception:
            new_files = []
    else:
        with st.expander("디버그(소비 API 로드 경로)"):
            st.write("\n".join(dbg2) or "(정보 없음)")

    total_prepared = len(files_list)
    total_new = len(new_files)
    st.success(f"스캔 완료 · prepared 총 {total_prepared}건 · 새 파일 {total_new}건")

    if total_new:
        with st.expander("새 파일 미리보기(최대 50개)"):
            rows = []
            for rec in (new_files[:50] if isinstance(new_files, list) else []):
                if isinstance(rec, str):
                    rows.append({"name": rec})
                elif isinstance(rec, dict):
                    nm = str(rec.get("name") or rec.get("path") or rec.get("file") or "")
                    fid = str(rec.get("id") or rec.get("fileId") or "")
                    rows.append({"name": nm, "id": fid})
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.write("(표시할 항목이 없습니다.)")
    else:
        st.info("새 파일이 없습니다. 재인덱싱을 수행할 필요가 없습니다.")

    st.session_state["_PR_SCAN_RESULT"] = {
        "persist": str(idx_persist),
        "prepared_total": total_prepared,
        "new_total": total_new,
        "timestamp": int(time.time()),
        "sample_new": new_files[:10] if isinstance(new_files, list) else [],
    }
# ================================= [15] prepared scan — END ===========================

# =============================== [16] indexed sources — START =========================
def _render_admin_indexed_sources_panel() -> None:
    if st is None or not _is_admin_view():
        return

    chunks_path = _persist_dir_safe() / "chunks.jsonl"
    with st.container(border=True):
        st.subheader("📄 인덱싱된 파일 목록 (읽기 전용)")
        st.caption(f"경로: `{str(chunks_path)}`")

        if not chunks_path.exists():
            st.info("아직 인덱스가 없습니다. 먼저 인덱싱을 수행해 주세요.")
            return

        docs: Dict[str, Dict[str, Any]] = {}
        total_lines = 0
        parse_errors = 0
        try:
            with chunks_path.open("r", encoding="utf-8") as rf:
                for line in rf:
                    s = line.strip()
                    if not s:
                        continue
                    total_lines += 1
                    try:
                        obj = json.loads(s)
                    except Exception:
                        parse_errors += 1
                        continue
                    doc_id = str(obj.get("doc_id") or obj.get("source") or "")
                    title = str(obj.get("title") or "")
                    source = str(obj.get("source") or "")
                    if not doc_id:
                        continue
                    row = docs.setdefault(
                        doc_id, {"doc_id": doc_id, "title": title, "source": source, "chunks": 0}
                    )
                    row["chunks"] += 1
        except Exception as e:
            _errlog(f"read chunks.jsonl failed: {e}", where="[indexed-sources.read]", exc=e)
            st.error("인덱스 파일을 읽는 중 오류가 발생했어요.")
            return

        rows2 = [
            {"title": r["title"], "path": r["source"], "doc_id": r["doc_id"], "chunks": r["chunks"]}
            for r in docs.values()
        ]
        st.caption(
            f"총 청크 수: {total_lines} · 문서 수: {len(rows2)} (파싱오류 {parse_errors}건)"
        )
        st.dataframe(rows2, hide_index=True, use_container_width=True)
# ================================= [16] indexed sources — END =========================

# =============================== [17] chat styles & mode — START ======================
def _inject_chat_styles_once() -> None:
    if st is None:
        return
    if st.session_state.get("_chat_styles_injected_v2"):
        return
    st.session_state["_chat_styles_injected_v2"] = True

    st.markdown(
        """
<style>
  .chatpane{
    position:relative; background:#EDF4FF; border:1px solid #D5E6FF; border-radius:18px;
    padding:10px; margin-top:12px;
  }
  .chatpane .messages{ max-height:60vh; overflow-y:auto; padding:8px; }
  .chatpane div[data-testid="stRadio"]{ background:#EDF4FF; padding:8px 10px 0 10px; margin:0; }
  .chatpane div[data-testid="stRadio"] > div[role="radiogroup"]{ display:flex; gap:10px; flex-wrap:wrap; }
  .chatpane div[data-testid="stRadio"] [role="radio"]{
    border:2px solid #bcdcff; border-radius:12px; padding:6px 12px; background:#fff; color:#0a2540;
    font-weight:700; font-size:14px; line-height:1;
  }
  .chatpane div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{
    background:#eaf6ff; border-color:#9fd1ff; color:#0a2540;
  }
  .chatpane div[data-testid="stRadio"] svg{ display:none!important }

  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...']) {
    position:relative; background:#EDF4FF; padding:8px 10px 10px 10px; margin:0;
  }
  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...'])
  [data-testid="stTextInput"] input{
    background:#FFF8CC !important; border:1px solid #F2E4A2 !important;
    border-radius:999px !important; color:#333 !important; height:46px; padding-right:56px;
  }
  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...']) ::placeholder{ color:#8A7F4A !important; }

  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...']) .stButton,
  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...']) .row-widget.stButton{
    position:absolute; right:14px; top:50%; transform:translateY(-50%);
    z-index:2; margin:0!important; padding:0!important;
  }
  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...']) .stButton > button,
  form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요...']) .row-widget.stButton > button{
    width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
    font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
    padding:0; min-height:0;
  }

  .msg-row{ display:flex; margin:8px 0; }
  .msg-row.left{ justify-content:flex-start; }
  .msg-row.right{ justify-content:flex-end; }
  .bubble{
    max-width:88%; padding:10px 12px; border-radius:16px; line-height:1.6; font-size:15px;
    box-shadow:0 1px 1px rgba(0,0,0,.05); white-space:pre-wrap; position:relative;
  }
  .bubble.user{ border-top-right-radius:8px; border:1px solid #F2E4A2; background:#FFF8CC; color:#333; }
  .bubble.ai  { border-top-left-radius:8px;  border:1px solid #BEE3FF; background:#EAF6FF; color:#0a2540; }

  .chip{
    display:inline-block; margin:-2px 0 6px 0; padding:2px 10px; border-radius:999px;
    font-size:12px; font-weight:700; color:#fff; line-height:1;
  }
  .chip.me{ background:#059669; }
  .chip.pt{ background:#2563eb; }
  .chip.mn{ background:#7c3aed; }
  .chip-src{
    display:inline-block; margin-left:6px; padding:2px 8px; border-radius:10px;
    background:#eef2ff; color:#3730a3; font-size:12px; font-weight:600; line-height:1;
    border:1px solid #c7d2fe; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    vertical-align:middle;
  }

  @media (max-width:480px){
    .bubble{ max-width:96%; }
    .chip-src{ max-width:160px; }
  }
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_mode_controls_pills() -> str:
    _inject_chat_styles_once()
    if st is None:
        return "grammar"
    try:
        from src.core.modes import enabled_modes
        modes = enabled_modes()
        labels = [m.label for m in modes]
        keys = [m.key for m in modes]
    except Exception:
        labels = ["문법", "문장", "지문"]
        keys = ["grammar", "sentence", "passage"]

    ss = st.session_state
    last_key = str(ss.get("__mode") or "grammar")
    try:
        cur_idx = keys.index(last_key)
    except ValueError:
        cur_idx = 0

    sel_label = st.radio(
        "질문 모드",
        options=labels,
        index=cur_idx,
        horizontal=True,
        label_visibility="collapsed",
    )

    spec = None
    try:
        import src.core.modes as _mcore
        spec = _mcore.find_mode_by_label(sel_label)
    except Exception:
        spec = None

    try:
        cur_key = spec.key if spec else keys[labels.index(sel_label)]
    except Exception:
        cur_key = "grammar"

    ss["qa_mode_radio"] = sel_label
    ss["__mode"] = cur_key
    return cur_key
# =============================== [17] chat styles & mode — END ========================

# =============================== [18] chat panel — START ==============================
def _render_chat_panel() -> None:
    import importlib as _imp
    import html
    import re
    from typing import Optional, Callable
    from src.agents.responder import answer_stream
    from src.agents.evaluator import evaluate_stream
    from src.llm.streaming import BufferOptions, make_stream_handler

    try:
        try:
            _label_mod = _imp.import_module("src.rag.label")
        except Exception:
            _label_mod = _imp.import_module("label")
        _decide_label = getattr(_label_mod, "decide_label", None)
        _search_hits = getattr(_label_mod, "search_hits", None)
        _make_chip = getattr(_label_mod, "make_source_chip", None)
    except Exception:
        _decide_label = None
        _search_hits = None
        _make_chip = None

    def _resolve_sanitizer() -> Callable[[Optional[str]], str]:
        try:
            from src.modes.types import sanitize_source_label as _san
            return _san
        except Exception:
            try:
                mod = _imp.import_module("modes.types")
                fn = getattr(mod, "sanitize_source_label", None)
                if callable(fn):
                    return fn
            except Exception:
                pass

        def _fallback(label: Optional[str] = None) -> str:
            return "[AI지식]"

        return _fallback

    sanitize_source_label = _resolve_sanitizer()

    def _esc(t: str) -> str:
        s = html.escape(t or "").replace("\n", "<br/>")
        return re.sub(r"  ", "&nbsp;&nbsp;", s)

    def _chip_html(who: str) -> str:
        klass = {"나": "me", "피티쌤": "pt", "미나쌤": "mn"}.get(who, "pt")
        return f'<span class="chip {klass}">{html.escape(who)}</span>'

    def _src_html(label: Optional[str]) -> str:
        if not label:
            return ""
        return f'<span class="chip-src">{html.escape(label)}</span>'

    def _emit_bubble(placeholder, who: str, acc_text: str,
                     *, source: Optional[str], align_right: bool) -> None:
        side_cls = "right" if align_right else "left"
        klass = "user" if align_right else "ai"
        chips = _chip_html(who) + (_src_html(source) if not align_right else "")
        html_block = (
            f'<div class="msg-row {side_cls}">'
            f'  <div class="bubble {klass}">{chips}<br/>{_esc(acc_text)}</div>'
            f"</div>"
        )
        placeholder.markdown(html_block, unsafe_allow_html=True)

    if st is None:
        return
    ss = st.session_state
    question = str(ss.get("inpane_q", "") or "").strip()
    if not question:
        return

    src_label = "[AI지식]"
    hits = []
    if callable(_search_hits):
        try:
            hits = _search_hits(question, top_k=5)
        except Exception:
            hits = []

    if callable(_decide_label):
        try:
            src_label = _decide_label(hits, default_if_none="[AI지식]")
        except Exception:
            src_label = "[AI지식]"

    src_label = sanitize_source_label(src_label)

    chip_text = src_label
    if callable(_make_chip):
        try:
            chip_text = _make_chip(hits, src_label)
        except Exception:
            chip_text = src_label

    ph_user = st.empty()
    _emit_bubble(ph_user, "나", question, source=None, align_right=True)

    ph_ans = st.empty()
    acc_ans = ""

    def _on_emit_ans(chunk: str) -> None:
        nonlocal acc_ans
        acc_ans += str(chunk or "")
        _emit_bubble(ph_ans, "피티쌤", acc_ans, source=chip_text, align_right=False)

    emit_chunk_ans, close_stream_ans = make_stream_handler(
        on_emit=_on_emit_ans,
        opts=BufferOptions(
            min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
            flush_on_strong_punct=True, flush_on_newline=True,
        ),
    )
    for piece in answer_stream(question=question, mode=ss.get("__mode", "")):
        emit_chunk_ans(str(piece or ""))
    close_stream_ans()
    full_answer = acc_ans.strip()

    ph_eval = st.empty()
    acc_eval = ""

    def _on_emit_eval(chunk: str) -> None:
        nonlocal acc_eval
        acc_eval += str(chunk or "")
        _emit_bubble(ph_eval, "미나쌤", acc_eval, source=chip_text, align_right=False)

    emit_chunk_eval, close_stream_eval = make_stream_handler(
        on_emit=_on_emit_eval,
        opts=BufferOptions(
            min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
            flush_on_strong_punct=True, flush_on_newline=True,
        ),
    )
    for piece in evaluate_stream(
        question=question, mode=ss.get("__mode", ""), answer=full_answer, ctx={"answer": full_answer}
    ):
        emit_chunk_eval(str(piece or ""))
    close_stream_eval()

    ss["last_q"] = question
    ss["inpane_q"] = ""
# ================================= [18] chat panel — END ==============================

# =============================== [19] body & main — START =============================
def _render_body() -> None:
    if st is None:
        return

    # 1) 부팅 훅
    if not st.session_state.get("_boot_checked"):
        try:
            _boot_auto_restore_index()
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            st.session_state["_boot_checked"] = True

    # 2) ✅ 상태 확정(자동 복원/READY 반영)을 헤더보다 먼저 수행
    try:
        _auto_start_once()
    except Exception as e:
        _errlog(f"auto_start_once failed: {e}", where="[render_body.autostart]", exc=e)

    # 3) 배경/헤더
    _mount_background()
    _header()

    # 4) 관리자 패널
    if _is_admin_view():
        _render_index_orchestrator_header()
        try:
            _render_admin_prepared_scan_panel()
        except Exception:
            pass
        try:
            _render_admin_index_panel()
        except Exception:
            pass
        try:
            _render_admin_indexed_sources_panel()
        except Exception:
            pass

    # 5) 채팅 메시지 영역
    _inject_chat_styles_once()
    with st.container():
        st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    # 6) 채팅 입력 폼
    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        submitted: bool = False
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요...", key="q_text")
            submitted = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

    # 7) 전송 처리
    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        _safe_rerun("chat_submit", ttl=1)
    else:
        st.session_state.setdefault("inpane_q", "")


def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()


if __name__ == "__main__":
    main()
# ================================= [19] body & main — END =============================
