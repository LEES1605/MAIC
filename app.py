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


def _get_indexing_state_file() -> Path:
    """인덱싱 상태 파일 경로"""
    return _persist_dir_safe() / ".indexing_state.json"


def _load_indexing_state() -> Dict[str, Any]:
    """인덱싱 상태 로드"""
    state_file = _get_indexing_state_file()
    try:
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {"indexed_files": {}, "last_scan_time": None}


def _save_indexing_state(state: Dict[str, Any]) -> None:
    """인덱싱 상태 저장"""
    try:
        state_file = _get_indexing_state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get_file_hash(file_path: Path) -> str:
    """파일 해시값 계산"""
    try:
        import hashlib
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""


def _get_new_files_to_index(source_dir: Path) -> List[Path]:
    """새로 인덱싱해야 할 파일들만 반환"""
    state = _load_indexing_state()
    indexed_files = state.get("indexed_files", {})
    new_files = []
    
    try:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                file_str = str(file_path)
                file_hash = _get_file_hash(file_path)
                
                # 파일이 새로 추가되었거나 수정된 경우
                if file_str not in indexed_files or indexed_files[file_str] != file_hash:
                    new_files.append(file_path)
                    
        print(f"[DEBUG] Found {len(new_files)} new/modified files to index")
        return new_files
    except Exception as e:
        print(f"[DEBUG] Error scanning for new files: {e}")
        return []


def _update_indexing_state(new_files: List[Path]) -> None:
    """인덱싱 상태 업데이트"""
    state = _load_indexing_state()
    indexed_files = state.get("indexed_files", {})
    
    for file_path in new_files:
        file_str = str(file_path)
        file_hash = _get_file_hash(file_path)
        indexed_files[file_str] = file_hash
    
    state["indexed_files"] = indexed_files
    state["last_scan_time"] = time.time()
    _save_indexing_state(state)
    print(f"[DEBUG] Updated indexing state with {len(new_files)} files")


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

    # (B) 기본 멀티페이지 네비 전역 숨김(학생/관리자 공통)
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

        # 끄기(우선): admin=0/false/off or goto=back|home
        # ❗️기존의 'prompt'는 여기서 제외 → 프롬프트 페이지 진입 시 관리자 모드 유지
        if _has(v, _falsy) or _has(goto, lambda x: _norm(x) in ("back", "home")):
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

    # (D) 학생 사이드바 숨김 (관리자는 별도 처리)
    try:
        adm = bool(st.session_state.get("admin_mode", False))
        if not adm:
            # 학생: 사이드바 전체 숨김
            st.markdown(
                "<style>section[data-testid='stSidebar']{display:none!important;}</style>",
                unsafe_allow_html=True,
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


# 공통 유틸리티 함수 import
from src.common.utils import errlog as _errlog
# ===================== [05] path & logger — END ========================

# ======================== [06] admin gate — START ========================
def _is_admin_view() -> bool:
    """관리자 모드 여부(세션 키 보정 포함)."""
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
import time as _time_guard
from typing import Any as _Any_guard, Dict as _Dict_guard

def _safe_rerun(tag: str, ttl: float = 0.3) -> None:
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
        # 만료 시 엔트리 제거
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
    """rerun guard 엔트리 제거(다음 액션을 위해)."""
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


def _reset_rerun_guard(tag: str) -> None:
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
    H1: 상단 헤더에서 **최신 릴리스 복원 여부**를 3단계(🟩/🟨/🟧)로 항상 표기합니다.
    - 우선 tri-state 배지를 렌더(지연 import, 실패 시 무시)
    - 가능하면 외부 헤더(src.ui.header.render)도 이어서 렌더
    - 외부 헤더가 없을 때만 간단 폴백을 표시
    (H1 규칙은 MASTERPLAN vNext의 합의안을 준수합니다)
    """
    if st is None:
        return

    # 0) Tri-state readiness chip (관리자 모드에서만 표시)
    try:
        # 관리자 모드일 때만 readiness 헤더 표시
        if st.session_state.get("admin_mode", False):
            from src.ui.utils.readiness import render_readiness_header  # type: ignore
            render_readiness_header(compact=True)
    except Exception:
        # 배지 렌더 실패는 치명적이지 않으므로 조용히 계속 진행
        pass

    # 1) 외부 헤더가 정의되어 있으면 추가로 렌더
    try:
        from src.ui.header import render as _render_header
        _render_header()
        return
    except Exception:
        # 외부 헤더가 없으면 아래 폴백으로 이어감
        pass

    # 2) 폴백 헤더 (일관성 있는 상태 표시)
    try:
        p = _persist_dir_safe()
        cj = p / "chunks.jsonl"
        rf = p / ".ready"
        
        # 실제 파일 상태 확인
        chunks_ready = cj.exists() and cj.stat().st_size > 0
        ready_file = rf.exists()
        
        # 세션 상태와 실제 파일 상태 일치 확인
        session_ready = st.session_state.get("_INDEX_LOCAL_READY", False)
        
        # 일관성 있는 상태 표시
        if chunks_ready and ready_file:
            badge = "🟢 준비완료"
            status_color = "green"
        elif chunks_ready or ready_file:
            badge = "🟡 부분준비"
            status_color = "orange"
        else:
            badge = "🔴 인덱스없음"
            status_color = "red"
            
        st.markdown(f"{badge} **LEES AI Teacher**")
        
        # 관리자 모드에서만 상세 정보 표시
        if st.session_state.get("admin_mode", False):
            with st.container():
                st.caption("상태 정보")
                st.json({
                    "chunks_ready": chunks_ready,
                    "ready_file": ready_file,
                    "session_ready": session_ready,
                    "persist_dir": str(p)
                })
    except Exception as e:
        st.markdown("🔴 오류 **LEES AI Teacher**")
        if st.session_state.get("admin_mode", False):
            st.error(f"상태 확인 오류: {e}")
# ================================== [08] header — END =================================

# =============================== [09] student progress stepper — START =====================
def _render_stepper(*, force: bool = False) -> None:
    """
    학생 화면에서 보여줄 '미니 진행바'.
    - 진행률: ok=1.0, run=0.6, wait/err=0.0 가중 합을 총 스텝수로 나눠 환산.
    - 라벨: 'run' 상태가 있으면 그 스텝의 detail/name, 모두 OK면 '인덱스 복원 완료'.
    """
    if st is None:
        return

    try:
        from src.services.index_state import (
            ensure_index_state,
            render_progress_with_fallback,
        )
        ensure_index_state()
    except Exception:
        return

    ph = st.session_state.get("_IDX_STEPPER_PH")
    if ph is None:
        if not force:
            return
        ph = st.empty()
        st.session_state["_IDX_STEPPER_PH"] = ph

    steps: list[dict[str, object]] = st.session_state.get("_IDX_STEPS") or []
    if not isinstance(steps, list):
        steps = []

    total = max(1, len(steps))
    weight = {"ok": 1.0, "run": 0.6, "wait": 0.0, "err": 0.0}

    acc = 0.0
    running_label = ""
    for s in steps:
        stt = str(s.get("status", "wait"))
        acc += weight.get(stt, 0.0)
        if not running_label and stt == "run":
            running_label = str(s.get("detail") or s.get("name") or "")

    pct = int(min(100, max(0, round(acc / total * 100))))
    # ✅ 완료 시 라벨도 완료로 바꿔 준다
    if pct >= 100:
        text = "인덱스 복원 완료"
    else:
        text = running_label or "인덱스 준비 중•••"

    with ph.container():
        st.caption("인덱싱 단계 표시기(간이 모드)")
        render_progress_with_fallback(pct, text=text)
# =============================== [09] student progress stepper — END =======================


# =============================== [10] auto-restore — START ============================
def _boot_auto_restore_index() -> None:
    """
    최신 릴리스 자동 복원 훅.
    규칙(개선):
      - 로컬 준비 기록(_INDEX_LOCAL_READY)은 그대로 유지
      - 원격 최신과의 일치 판정은 **release_id 우선**, 없을 때만 tag 비교로 폴백
      - 일치하지 않으면 복원 강제
      - 복원 성공 시에만 _INDEX_IS_LATEST=True

    UI 연동(진행표시 훅): 플레이스홀더 생성은 [19]에서만 수행
    """
    import os
    # 멱등 보호 (UI 버튼 클릭 시에는 강제 재시도 허용)
    try:
        if "st" in globals() and st is not None:
            # UI에서 명시적으로 호출된 경우에는 멱등 보호 무시
            if st.session_state.get("_BOOT_RESTORE_DONE") and not st.session_state.get("_FORCE_RESTORE", False):
                print(f"[DEBUG] Skipping restore - already done: {st.session_state.get('_BOOT_RESTORE_DONE')}")
                return
    except Exception:
        pass

    def _idx(name: str, *args, **kwargs):
        try:
            mod = importlib.import_module("src.services.index_state")
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        except Exception:
            return None

    _idx("ensure_index_state")
    _idx("log", "부팅: 인덱스 복원 준비 중...")
    
    p = effective_persist_dir()
    print(f"[DEBUG] Starting restore process - persist_dir: {p}")
    cj = p / "chunks.jsonl"
    rf = p / ".ready"

    # --- 공용 판정기 로드 ---
    try:
        from src.core.readiness import is_ready_text, normalize_ready_file
    except Exception:
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

    # --- 로컬 준비 상태 ---
    _idx("step_set", 1, "run", "로컬 준비 상태 확인")
    print(f"[DEBUG] Checking local files: cj={cj}, rf={rf}")
    print(f"[DEBUG] cj.exists(): {cj.exists()}")
    if cj.exists():
        print(f"[DEBUG] cj.size(): {cj.stat().st_size}")
    print(f"[DEBUG] rf.exists(): {rf.exists()}")
    
    ready_txt = ""
    try:
        if rf.exists():
            ready_txt = rf.read_text(encoding="utf-8")
            print(f"[DEBUG] ready_txt content: {repr(ready_txt)}")
    except Exception as e:
        print(f"[DEBUG] Error reading ready file: {e}")
        ready_txt = ""
    
    local_ready = cj.exists() and cj.stat().st_size > 0 and is_ready_text(ready_txt)
    print(f"[DEBUG] local_ready calculation: cj.exists()={cj.exists()}, cj.size()={cj.stat().st_size if cj.exists() else 0}, is_ready_text()={is_ready_text(ready_txt)}")
    _idx("log", f"로컬 준비: {'OK' if local_ready else '미검출'}")

    try:
        if "st" in globals() and st is not None:
            st.session_state["_INDEX_LOCAL_READY"] = bool(local_ready)
            st.session_state.setdefault("_INDEX_IS_LATEST", False)
    except Exception:
        pass
    _idx("step_set", 1, "ok" if local_ready else "wait", "로컬 준비 기록")

    # --- 복원 메타 유틸 ---
    def _safe_load_meta(path):
        try:
            return load_restore_meta(path)  # type: ignore[name-defined]
        except Exception:
            return None

    def _safe_meta_tag_matches(meta, tag: str) -> bool:
        try:
            return bool(meta_matches_tag(meta, tag))  # type: ignore[name-defined]
        except Exception:
            return False

    def _safe_meta_release_id(meta) -> Optional[int]:
        try:
            for k in ("release_id", "releaseId", "id"):
                v = getattr(meta, k, None)
                if v is not None:
                    return int(v)
        except Exception:
            pass
        try:
            if isinstance(meta, dict):
                for k in ("release_id", "releaseId", "id"):
                    v = meta.get(k)
                    if v is not None:
                        return int(v)
        except Exception:
            pass
        return None

    def _safe_save_meta(path, tag: str | None, release_id: int | None):
        try:
            return save_restore_meta(path, tag=tag, release_id=release_id)  # type: ignore[name-defined]
        except Exception:
            return None

    stored_meta = _safe_load_meta(p)

    # --- 원격 최신 메타 ---
    _idx("step_set", 2, "run", "원격 릴리스 조회")
    repo_full = os.getenv("GITHUB_REPO", "")
    token = os.getenv("GITHUB_TOKEN", None)
    try:
        if "st" in globals() and st is not None:
            repo_full = st.secrets.get("GITHUB_REPO", repo_full)
            token = st.secrets.get("GITHUB_TOKEN", token)
    except Exception:
        pass

    if not repo_full or "/" not in str(repo_full):
        _idx("log", "GITHUB_REPO 미설정 → 원격 확인 불가", "warn")
        _idx("step_set", 2, "wait", "원격 확인 불가")
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
        _idx("log", "GH 릴리스 모듈 불가 → 최신 판정 보류", "warn")
        _idx("step_set", 2, "wait", "원격 확인 불가")
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
        _idx("log", f"원격 최신 릴리스: tag={remote_tag or '-'} id={remote_release_id or '-'}")
    except Exception:
        remote_tag = None
        remote_release_id = None
        _idx("log", "원격 최신 릴리스 조회 실패", "warn")
    finally:
        try:
            if "st" in globals() and st is not None:
                st.session_state["_LATEST_RELEASE_TAG"] = remote_tag
                st.session_state["_LATEST_RELEASE_ID"] = remote_release_id
                if stored_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(stored_meta, "to_dict", lambda: {})()
        except Exception:
            pass

    # --- 일치/불일치 판정 (release_id 우선) ---
    stored_id = _safe_meta_release_id(stored_meta)
    match_by_id = (remote_release_id is not None) and (stored_id is not None) and (stored_id == remote_release_id)
    match_by_tag = False
    if not match_by_id and remote_tag:
        match_by_tag = _safe_meta_tag_matches(stored_meta, remote_tag)

    if local_ready and (match_by_id or (remote_release_id is None and match_by_tag)):
        _idx("log", "메타 일치: 복원 생략 (이미 최신)")
        _idx("step_set", 2, "ok", "메타 일치")
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = True
        except Exception:
            pass
        return

    # --- 최신 복원 강제 (순차번호 시스템) ---
    _idx("step_set", 2, "run", "최신 인덱스 복원 중...")
    _idx("log", "순차번호 기반 릴리스 복원 시작...")
    try:
        from src.runtime.sequential_release import create_sequential_manager
        
        # GitHub 설정
        import os
        repo_full = st.secrets.get("GITHUB_REPO", os.getenv("GITHUB_REPO", ""))
        token = st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
        
        if "/" not in str(repo_full):
            raise RuntimeError("GitHub 설정이 필요합니다 (GITHUB_REPO/GITHUB_TOKEN)")
        
        owner, repo = str(repo_full).split("/", 1)
        
        # 순차번호 관리자 생성
        print(f"[DEBUG] Creating sequential manager for owner={owner}, repo={repo}")
        seq_manager = create_sequential_manager(owner, repo, token)
        print(f"[DEBUG] Sequential manager created successfully")
        
        # GitHub 릴리스 상태 확인
        try:
            print(f"[DEBUG] Checking GitHub releases for {owner}/{repo}")
            
            # 현재 실행 중인 코드 버전 확인
            print(f"[DEBUG] Code version check: Using GHReleases import")
            
            # 릴리스 목록 직접 확인
            from src.runtime.gh_release import GHReleases
            gh = GHReleases(owner=owner, repo=repo, token=token)
            releases = gh.list_releases()
            print(f"[DEBUG] Found {len(releases)} releases: {[r.get('tag_name') for r in releases]}")
            
            if releases:
                latest_release = releases[0]
                assets = latest_release.get('assets', [])
                print(f"[DEBUG] Latest release assets: {[a.get('name') for a in assets]}")
            else:
                print(f"[DEBUG] No releases found!")
                
        except Exception as e:
            print(f"[DEBUG] Error checking releases: {e}")
        
        # 최신 인덱스 복원
        print(f"[DEBUG] About to call restore_latest_index with p={p}, clean_dest=True")
        
        try:
            result = seq_manager.restore_latest_index(p, clean_dest=True)
            print(f"[DEBUG] restore_latest_index result: {result}")
        except Exception as e:
            print(f"[DEBUG] restore_latest_index FAILED: {e}")
            import traceback
            traceback_str = traceback.format_exc()
            print(f"[DEBUG] Traceback: {traceback_str}")
            # 예외 발생 시에도 계속 진행
            result = None
        
        # 복원 후 파일 상태 재확인
        print(f"[DEBUG] Post-restore check: cj.exists()={cj.exists()}, rf.exists()={rf.exists()}")
        
        if cj.exists():
            print(f"[DEBUG] Post-restore cj.size(): {cj.stat().st_size}")
        
        # persist 디렉토리 전체 내용 확인
        try:
            persist_files = list(p.iterdir()) if p.exists() else []
            print(f"[DEBUG] Persist directory contents: {[f.name for f in persist_files]}")
        except Exception as e:
            print(f"[DEBUG] Error listing persist directory: {e}")

        # 복원 성공/실패에 따른 일관성 있는 상태 설정
        restore_success = cj.exists() and cj.stat().st_size > 0
        print(f"[DEBUG] Restore success: {restore_success}")
        
        # 세션 상태 업데이트 (일관성 보장)
        try:
            if "st" in globals() and st is not None:
                st.session_state["_INDEX_LOCAL_READY"] = restore_success
                st.session_state["_INDEX_IS_LATEST"] = restore_success
                st.session_state["_BOOT_RESTORE_DONE"] = True
                print(f"[DEBUG] Session state updated: _INDEX_LOCAL_READY={restore_success}")
        except Exception as e:
            print(f"[DEBUG] Error updating session state: {e}")

        _idx("step_set", 3, "run", "메타 저장/정리...")
        normalize_ready_file(p)
        saved_meta = _safe_save_meta(
            p,
            tag=result.get("tag") if result else None,
            release_id=int(result.get("release_id")) if result and result.get("release_id") else None,
        )

        try:
            if "st" in globals() and st is not None:
                st.session_state["_PERSIST_DIR"] = p.resolve()
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state["_INDEX_IS_LATEST"] = True
                st.session_state["_INDEX_LOCAL_READY"] = True
                if saved_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(saved_meta, "to_dict", lambda: {})()
        except Exception:
            pass

        _idx("step_set", 2, "ok", "복원 완료")
        _idx("step_set", 3, "ok", "메타 저장 완료")
        _idx("step_set", 4, "ok", "마무리 정리")
        _idx("log", "✅ 최신 인덱스 복원 완료")
    except Exception as e:
        _idx("step_set", 2, "err", "복원 실패")
        _idx("log", f"❌ 최신 인덱스 복원 실패: {e}", "err")
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = False
                # UI에서 호출된 경우 오류 메시지 표시
                if st.session_state.get("_FORCE_RESTORE", False):
                    st.error(f"복원 실패: {e}")
                    st.session_state["_FORCE_RESTORE"] = False  # 플래그 리셋
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

    mode = (os.getenv("AUTO_START_MODE") or _secret_get("AUTO_START_MODE", "restore") or "restore").lower()
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
            core_mark_ready(used_persist)
        except Exception:
            pass
        if hasattr(st, "toast"):
            st.toast("자동 복원 완료", icon="✅")
        else:
            st.success("자동 복원 완료")
        _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
        _safe_rerun("auto_start", ttl=1)
# =============================== [12] auto-scan prepared — START ====================
def _boot_auto_scan_prepared() -> None:
    """
    부팅 시 prepared 폴더 자동 스캔.
    - 새 파일 발견 시 세션 상태에 기록
    - 사용자에게 알림 표시
    """
    try:
        if "st" in globals() and st is not None:
            # 이미 스캔했으면 스킵
            if st.session_state.get("_BOOT_SCAN_DONE"):
                return
    except Exception:
        pass

    def _idx(name: str, *args, **kwargs):
        try:
            mod = importlib.import_module("src.services.index_state")
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        except Exception:
            return None

    _idx("log", "부팅: prepared 폴더 스캔 중...")

    try:
        # prepared 파일 목록 조회
        lister, _ = _load_prepared_lister()
        if not lister:
            _idx("log", "prepared 폴더 접근 불가", "warn")
            return

        files_list = lister() or []
        total_files = len(files_list)

        # 상태 추적 기반 새 파일 확인
        try:
            # prepared 폴더 경로 추정 (실제 경로로 수정 필요)
            prepared_dir = Path("/mount/src/maic/data/prepared")  # 또는 실제 prepared 폴더 경로
            if prepared_dir.exists():
                new_files = _get_new_files_to_index(prepared_dir)
                print(f"[DEBUG] State-based scan: found {len(new_files)} new/modified files")
            else:
                # 기존 방식으로 폴백
                chk, _mark, _ = _load_prepared_api()
                new_files = []
                if callable(chk):
                    try:
                        persist_dir = effective_persist_dir()
                        info = chk(persist_dir, files_list) or {}
                        new_files = list(info.get("files") or info.get("new") or [])
                    except Exception as e:
                        _idx("log", f"새 파일 확인 실패: {e}", "warn")
                        return
        except Exception as e:
            print(f"[DEBUG] State-based scan failed, using fallback: {e}")
            # 기존 방식으로 폴백
            chk, _mark, _ = _load_prepared_api()
            new_files = []
            if callable(chk):
                try:
                    persist_dir = effective_persist_dir()
                    info = chk(persist_dir, files_list) or {}
                    new_files = list(info.get("files") or info.get("new") or [])
                except Exception as e:
                    _idx("log", f"새 파일 확인 실패: {e}", "warn")
                    return

        new_count = len(new_files)
        
        # 인덱싱 상태 업데이트 (새 파일이 있을 때만)
        if new_count > 0:
            try:
                _update_indexing_state(new_files)
                print(f"[DEBUG] Updated indexing state with {new_count} new files")
            except Exception as e:
                print(f"[DEBUG] Failed to update indexing state: {e}")
        
        # 결과를 세션 상태에 저장
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_SCAN_DONE"] = True
                st.session_state["_PREPARED_TOTAL_FILES"] = total_files
                st.session_state["_PREPARED_NEW_FILES"] = new_count
                st.session_state["_PREPARED_NEW_FILES_LIST"] = new_files[:10]  # 최대 10개만 저장
                
                # 새 파일이 있으면 알림
                if new_count > 0:
                    st.session_state["_PREPARED_HAS_NEW"] = True
                    _idx("log", f"새 파일 {new_count}개 발견! 재인덱싱을 권장합니다.", "warn")
                else:
                    st.session_state["_PREPARED_HAS_NEW"] = False
                    _idx("log", f"prepared 폴더 스캔 완료: 총 {total_files}개 파일, 새 파일 없음")
        except Exception:
            pass

    except Exception as e:
        _idx("log", f"prepared 폴더 스캔 실패: {e}", "err")

# ================================= [12] auto-scan prepared — END ======================


# ============================ [12] reserved — START (no-op) ===========================
# 향후: telemetry/hooks 자리
# ============================= [12] reserved — END =====================================

# ============================ [13] reserved — START (no-op) ===========================
# 향후: feature flags 자리
# ============================= [13] reserved — END =====================================

# ============================ [14] reserved — START (no-op) ===========================
# 향후: prompt orchestrator glue 자리
# ============================= [14] reserved — END =====================================

# ============================ [15] reserved — START (no-op) ===========================
# 향후: admin index quick-actions 자리
# ============================= [15] reserved — END =====================================

# ============================ [16] reserved — START (no-op) ===========================
# 향후: plugin mount 자리
# ============================= [16] reserved — END =====================================

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
  /* ▶ 메시지 영역 전용 컨테이너 */
  .chatpane-messages{
    position:relative; background:#EDF4FF; border:1px solid #D5E6FF; border-radius:18px;
    padding:10px; margin-top:12px;
  }
  .chatpane-messages .messages{ max-height:60vh; overflow-y:auto; padding:8px; }

  /* ▶ 입력 영역 전용 컨테이너 */
  .chatpane-input{
    position:relative; background:#EDF4FF; border:1px solid #D5E6FF; border-radius:18px;
    padding:8px 10px 10px 10px; margin-top:12px;
  }
  .chatpane-input div[data-testid="stRadio"]{ background:#EDF4FF; padding:8px 10px 0 10px; margin:0; }
  .chatpane-input div[data-testid="stRadio"] > div[role="radiogroup"]{ display:flex; gap:10px; flex-wrap:wrap; }
  .chatpane-input div[data-testid="stRadio"] [role="radio"]{
    border:2px solid #bcdcff; border-radius:12px; padding:6px 12px; background:#fff; color:#0a2540;
    font-weight:700; font-size:14px; line-height:1;
  }
  .chatpane-input div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{
    background:#eaf6ff; border-color:#9fd1ff; color:#0a2540;
  }
  .chatpane-input div[data-testid="stRadio"] svg{ display:none!important }

  /* 입력 폼/버튼은 입력 컨테이너 하위로만 적용 */
  .chatpane-input form[data-testid="stForm"] { position:relative; margin:0; }
  .chatpane-input form[data-testid="stForm"] [data-testid="stTextInput"] input{
    background:#FFF8CC !important; border:1px solid #F2E4A2 !important;
    border-radius:999px !important; color:#333 !important; height:46px; padding-right:56px;
  }
  .chatpane-input form[data-testid="stForm"] ::placeholder{ color:#8A7F4A !important; }
  .chatpane-input form[data-testid="stForm"] .stButton,
  .chatpane-input form[data-testid="stForm"] .row-widget.stButton{
    position:absolute; right:14px; top:50%; transform:translateY(-50%);
    z-index:2; margin:0!important; padding:0!important;
  }
  .chatpane-input form[data-testid="stForm"] .stButton > button,
  .chatpane-input form[data-testid="stForm"] .row-widget.stButton > button{
    width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
    font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
    padding:0; min-height:0;
  }

  /* ▶ 버블/칩 (글로벌) */
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

  /* ▶ 프롬프트/페르소나 대형 입력영역 */
  .prompt-editor .stTextArea textarea{
    min-height:260px !important; line-height:1.45; font-size:14px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  }
  .prompt-editor .persona-title, .prompt-editor .inst-title{
    font-weight:800; margin:6px 0 4px 0;
  }

  /* 모바일 반응형 스타일 */
  @media (max-width:480px){
    .bubble{ max-width:96%; }
    .chip-src{ max-width:160px; }
    
    /* 관리자 모드 모바일 최적화 */
    .mobile-status-grid {
      grid-template-columns: 1fr 1fr !important;
      gap: 6px !important;
    }
    .status-card {
      font-size: 10px !important;
      padding: 4px !important;
    }
    
    /* 버튼 모바일 최적화 */
    .stButton > button {
      font-size: 12px !important;
      padding: 8px 12px !important;
    }
    
    /* 로그 컨테이너 모바일 최적화 */
    .mobile-log-container {
      max-height: 120px !important;
      padding: 4px !important;
    }
    .log-entry {
      font-size: 10px !important;
      padding: 2px 0 !important;
    }
    
    /* 진행바 모바일 최적화 */
    .mobile-progress-container {
      padding: 4px !important;
    }
    .progress-bar {
      height: 14px !important;
    }
    .progress-text {
      font-size: 9px !important;
    }
    .progress-label {
      font-size: 10px !important;
    }
    
    /* 헤더 모바일 최적화 */
    .brand-title {
      font-size: 180% !important;
    }
    .ready-chip {
      font-size: 14px !important;
      padding: 1px 8px !important;
    }
    
    /* 사이드바 모바일 최적화 */
    .css-1d391kg {
      padding-top: 1rem !important;
    }
    
    /* 메인 컨테이너 모바일 최적화 */
    .main .block-container {
      padding-top: 1rem !important;
      padding-bottom: 1rem !important;
    }
  }
  
  /* 태블릿 반응형 (481px - 768px) */
  @media (min-width: 481px) and (max-width: 768px) {
    .mobile-status-grid {
      grid-template-columns: repeat(3, 1fr) !important;
      gap: 8px !important;
    }
    .status-card {
      font-size: 11px !important;
      padding: 6px !important;
    }
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
def _render_debug_panel():
    """관리자 전용 디버그 패널"""
    if st is None:
        return
    
    with st.expander("🔧 디버그 패널", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 복원 테스트", use_container_width=True):
                try:
                    print("[DEBUG] Manual restore test triggered")
                    _boot_auto_restore_index()
                    st.success("복원 테스트 완료")
                except Exception as e:
                    st.error(f"복원 테스트 실패: {e}")
        
        with col2:
            if st.button("📊 상태 확인", use_container_width=True):
                try:
                    persist_dir = effective_persist_dir()
                    cj = persist_dir / "chunks.jsonl"
                    rf = persist_dir / ".ready"
                    
                    status = {
                        "persist_dir": str(persist_dir),
                        "persist_exists": persist_dir.exists(),
                        "chunks_exists": cj.exists(),
                        "chunks_size": cj.stat().st_size if cj.exists() else 0,
                        "ready_exists": rf.exists(),
                        "ready_content": rf.read_text(encoding="utf-8") if rf.exists() else "",
                    }
                    st.json(status)
                except Exception as e:
                    st.error(f"상태 확인 실패: {e}")
        
        with col3:
            if st.button("🌐 GitHub 릴리스 확인", use_container_width=True):
                try:
                    from src.runtime.gh_release import GHReleases
                    repo_full = _secret_get("GITHUB_REPO")
                    token = _secret_get("GITHUB_TOKEN")
                    
                    if repo_full and token:
                        owner, repo = str(repo_full).split("/", 1)
                        gh = GHReleases(owner=owner, repo=repo, token=token)
                        releases = gh.list_releases()
                        
                        release_info = {
                            "total_releases": len(releases),
                            "latest_tag": releases[0].get('tag_name') if releases else None,
                            "latest_assets": releases[0].get('assets', []) if releases else []
                        }
                        st.json(release_info)
                    else:
                        st.warning("GitHub 설정이 없습니다")
                except Exception as e:
                    st.error(f"GitHub 릴리스 확인 실패: {e}")
        
        # 추가 테스트 버튼들
        st.markdown("---")
        col4, col5 = st.columns(2)
        
        with col4:
            if st.button("🔍 SequentialReleaseManager 테스트", use_container_width=True):
                try:
                    from src.runtime.sequential_release import create_sequential_manager
                    repo_full = _secret_get("GITHUB_REPO")
                    token = _secret_get("GITHUB_TOKEN")
                    
                    if repo_full and token:
                        owner, repo = str(repo_full).split("/", 1)
                        seq_manager = create_sequential_manager(owner, repo, token)
                        
                        # find_latest_by_number 직접 테스트
                        latest = seq_manager.find_latest_by_number("index")
                        
                        test_result = {
                            "manager_created": True,
                            "find_latest_result": latest.get('tag_name') if latest else None,
                            "find_latest_full": latest
                        }
                        
                        # 결과를 세션 상태에 저장
                        st.session_state["debug_seq_manager_test"] = test_result
                        st.json(test_result)
                    else:
                        st.warning("GitHub 설정이 없습니다")
                except Exception as e:
                    st.error(f"SequentialReleaseManager 테스트 실패: {e}")
                    st.session_state["debug_seq_manager_test"] = {"error": str(e)}
        
        with col5:
            if st.button("🔄 수동 복원 테스트", use_container_width=True):
                try:
                    from src.runtime.sequential_release import create_sequential_manager
                    repo_full = _secret_get("GITHUB_REPO")
                    token = _secret_get("GITHUB_TOKEN")
                    
                    if repo_full and token:
                        owner, repo = str(repo_full).split("/", 1)
                        seq_manager = create_sequential_manager(owner, repo, token)
                        
                        persist_dir = effective_persist_dir()
                        result = seq_manager.restore_latest_index(persist_dir, clean_dest=True)
                        
                        # 결과를 세션 상태에 저장
                        st.session_state["debug_manual_restore"] = {"success": True, "result": result}
                        st.success(f"복원 성공: {result}")
                    else:
                        st.warning("GitHub 설정이 없습니다")
                except Exception as e:
                    import traceback
                    error_info = {"error": str(e), "traceback": traceback.format_exc()}
                    st.session_state["debug_manual_restore"] = error_info
                    st.error(f"수동 복원 테스트 실패: {e}")
                    st.code(traceback.format_exc())
        
        # 인덱싱 상태 관리 버튼들
        st.markdown("---")
        col6, col7, col8 = st.columns(3)
        
        with col6:
            if st.button("📊 인덱싱 상태 확인", use_container_width=True):
                try:
                    state = _load_indexing_state()
                    indexed_count = len(state.get("indexed_files", {}))
                    last_scan = state.get("last_scan_time")
                    
                    status_info = {
                        "indexed_files_count": indexed_count,
                        "last_scan_time": last_scan,
                        "state_file_exists": _get_indexing_state_file().exists(),
                        "sample_files": list(state.get("indexed_files", {}).keys())[:5]  # 처음 5개만 표시
                    }
                    st.session_state["debug_indexing_state"] = status_info
                    st.json(status_info)
                except Exception as e:
                    st.error(f"인덱싱 상태 확인 실패: {e}")
        
        with col7:
            if st.button("🔄 인덱싱 상태 초기화", use_container_width=True):
                try:
                    state_file = _get_indexing_state_file()
                    if state_file.exists():
                        state_file.unlink()
                    st.success("인덱싱 상태가 초기화되었습니다")
                except Exception as e:
                    st.error(f"인덱싱 상태 초기화 실패: {e}")
        
        with col8:
            if st.button("🔍 새 파일 스캔 테스트", use_container_width=True):
                try:
                    # 예시 소스 디렉토리 (실제 경로로 변경 필요)
                    source_dir = Path("/mount/src/maic")  # 또는 실제 소스 디렉토리
                    new_files = _get_new_files_to_index(source_dir)
                    
                    scan_result = {
                        "source_dir": str(source_dir),
                        "new_files_count": len(new_files),
                        "sample_new_files": [str(f) for f in new_files[:5]]  # 처음 5개만 표시
                    }
                    st.session_state["debug_scan_test"] = scan_result
                    st.json(scan_result)
                except Exception as e:
                    st.error(f"새 파일 스캔 테스트 실패: {e}")
        
        # 모든 테스트 결과 표시
        if any(key in st.session_state for key in ["debug_seq_manager_test", "debug_manual_restore", "debug_indexing_state", "debug_scan_test"]):
            st.markdown("### 📊 모든 테스트 결과")
            
            if "debug_seq_manager_test" in st.session_state:
                st.markdown("**🔍 SequentialReleaseManager 테스트 결과:**")
                st.json(st.session_state["debug_seq_manager_test"])
            
            if "debug_manual_restore" in st.session_state:
                st.markdown("**🔄 수동 복원 테스트 결과:**")
                st.json(st.session_state["debug_manual_restore"])
            
            if "debug_indexing_state" in st.session_state:
                st.markdown("**📊 인덱싱 상태:**")
                st.json(st.session_state["debug_indexing_state"])
            
            if "debug_scan_test" in st.session_state:
                st.markdown("**🔍 새 파일 스캔 테스트 결과:**")
                st.json(st.session_state["debug_scan_test"])

def _render_body() -> None:
    if st is None:
        return

    # 1) 부팅 훅 - 항상 실행하도록 수정
    try:
        # 복원 상태 강제 리셋 (매번 실행)
        st.session_state["_BOOT_RESTORE_DONE"] = False
        st.session_state["_INDEX_LOCAL_READY"] = False
        st.session_state["_INDEX_IS_LATEST"] = False
        print(f"[DEBUG] Reset restore state - forcing restore")
        
        # persist 디렉토리 상태 확인
        persist_dir = effective_persist_dir()
        print(f"[DEBUG] Persist directory: {persist_dir}")
        print(f"[DEBUG] Persist exists: {persist_dir.exists()}")
        print(f"[DEBUG] Persist writable: {os.access(persist_dir.parent, os.W_OK) if persist_dir.parent.exists() else False}")
        
        print(f"[DEBUG] About to call _boot_auto_restore_index()")
        _boot_auto_restore_index()
        print(f"[DEBUG] _boot_auto_restore_index() completed")
        
        print(f"[DEBUG] About to call _boot_auto_scan_prepared()")
        _boot_auto_scan_prepared()  # 새로 추가: 자동 스캔
        print(f"[DEBUG] _boot_auto_scan_prepared() completed")
        
        print(f"[DEBUG] About to call _boot_autoflow_hook()")
        _boot_autoflow_hook()
        print(f"[DEBUG] _boot_autoflow_hook() completed")
    except Exception as e:
        _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)

    # 2) ✅ 상태 확정(자동 복원/READY 반영)을 헤더보다 먼저 수행
    try:
        _auto_start_once()
    except Exception as e:
        _errlog(f"auto_start_once failed: {e}", where="[render_body.autostart]", exc=e)

    # 3) 헤더 렌더링
    if _is_admin_view():
        # 관리자 모드에서는 헤더를 가장 먼저 렌더링
        try:
            from src.ui.header import render as _render_header
            _render_header()
        except Exception:
            pass
    else:
        # 일반 모드에서는 기본 헤더
        _header()

    # 4) 관리자 패널 (외부 모듈 호출: src.ui.ops.indexing_panel)
    if _is_admin_view():
        # 디버그 패널 추가
        _render_debug_panel()
        
        # 지연 import로 순환 참조 방지 및 오버헤드 최소화
        try:
            from src.ui.ops.indexing_panel import (
                render_orchestrator_header,
                render_prepared_scan_panel,
                render_index_panel,
                render_indexed_sources_panel,
            )
        except Exception as e:
            _errlog(f"admin panel import failed: {e}", where="[render_body.admin.import]", exc=e)
            render_orchestrator_header = render_prepared_scan_panel = None  # type: ignore
            render_index_panel = render_indexed_sources_panel = None        # type: ignore

        if callable(render_orchestrator_header):
            render_orchestrator_header()
        try:
            if callable(render_prepared_scan_panel):
                render_prepared_scan_panel()
        except Exception:
            pass
        try:
            if callable(render_index_panel):
                render_index_panel()
        except Exception:
            pass
        try:
            if callable(render_indexed_sources_panel):
                render_indexed_sources_panel()
        except Exception:
            pass

    # 5) 채팅 메시지 영역 (컨테이너 클래스 분리)
    _inject_chat_styles_once()
    with st.container(key="chat_messages_container"):
        st.markdown('<div class="chatpane-messages" data-testid="chat-messages"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    # 6) 채팅 입력 폼 (컨테이너 클래스 분리 + key 안정화)
    with st.container(border=True, key="chat_input_container"):
        st.markdown('<div class="chatpane-input" data-testid="chat-input">', unsafe_allow_html=True)
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
    
    # 관리자 모드일 때는 사이드바를 가장 먼저 렌더링 (헤더보다 먼저)
    try:
        adm = bool(st.session_state.get("admin_mode", False))
        if adm:
            from src.ui.utils.sider import render_sidebar
            render_sidebar(back_page="app.py", icon_only=True)
    except Exception:
        pass
    
    _render_body()


if __name__ == "__main__":
    main()
# ================================= [19] body & main — END =============================
