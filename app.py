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
from typing import Any, Dict, List, Optional, Tuple

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

# =============================== [04] bootstrap env — START ===========================
def _bootstrap_env() -> None:
    try:
        _promote_env(
            keys=[
                "OPENAI_API_KEY", "OPENAI_MODEL",
                "GEMINI_API_KEY", "GEMINI_MODEL",
                "GH_TOKEN", "GITHUB_TOKEN",
                "GH_OWNER", "GH_REPO", "GITHUB_OWNER", "GITHUB_REPO_NAME", "GITHUB_REPO",
                "APP_MODE", "AUTO_START_MODE", "LOCK_MODE_FOR_STUDENTS",
                "APP_ADMIN_PASSWORD", "DISABLE_BG",
                "MAIC_PERSIST_DIR",
                "GDRIVE_PREPARED_FOLDER_ID", "GDRIVE_BACKUP_FOLDER_ID",
            ]
        )
    except Exception:
        pass

    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")


_bootstrap_env()
if st:
    try:
        st.set_page_config(page_title="LEES AI Teacher", layout="wide")
    except Exception:
        pass
# ================================ [04] bootstrap env — END ============================

# =============================== [05] path & logger — START ===========================
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
# ================================= [05] path & logger — END ===========================

# =============================== [06] admin gate — START ==============================
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
# ================================= [06] admin gate — END ==============================

# =============================== [07] rerun guard — START =============================
def _safe_rerun(tag: str, ttl: int = 1) -> None:
    s = globals().get("st", None)
    if s is None:
        return
    try:
        ss = getattr(s, "session_state", None)
        if ss is None:
            return
        tag = str(tag or "rerun")
        try:
            ttl_int = int(ttl)
        except Exception:
            ttl_int = 1
        if ttl_int <= 0:
            ttl_int = 1

        key = "__rerun_counts__"
        counts = ss.get(key, {})
        if not isinstance(counts, dict):
            try:
                counts = dict(counts)
            except Exception:
                counts = {}
        try:
            cnt = int(counts.get(tag, 0))
        except Exception:
            cnt = 0
        if cnt >= ttl_int:
            return

        counts[tag] = cnt + 1
        ss[key] = counts
        try:
            s.rerun()
        except Exception:
            try:
                s.experimental_rerun()
            except Exception:
                pass
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
    try:
        if "st" in globals() and st is not None:
            if st.session_state.get("_BOOT_RESTORE_DONE"):
                return
    except Exception:
        pass

    p = effective_persist_dir()
    cj = p / "chunks.jsonl"
    ready = (p / ".ready").exists()
    if cj.exists() and cj.stat().st_size > 0 and ready:
        try:
            if "st" in globals() and st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
        except Exception:
            pass
        return

    try:
        from src.core.secret import token as _gh_token, resolve_owner_repo as _resolve_owner_repo
        token = _gh_token() or ""
        owner, repo = _resolve_owner_repo()
    except Exception:
        token, owner, repo = "", "", ""

    if not (token and owner and repo):
        return

    from urllib import request as _rq
    import zipfile as _zf
    import json as _json

    api_latest = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        req = _rq.Request(api_latest, headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        })
        with _rq.urlopen(req, timeout=20) as resp:
            data = _json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return

    asset = None
    for a in data.get("assets") or []:
        n = str(a.get("name") or "")
        if n.startswith("index_") and n.endswith(".zip"):
            asset = a
            break
    if not asset:
        return
    dl = asset.get("browser_download_url")
    if not dl:
        return

    try:
        p.mkdir(parents=True, exist_ok=True)
        tmp = p / f"__restore_{int(time.time())}.zip"
        _rq.urlretrieve(dl, tmp)
        with _zf.ZipFile(tmp, "r") as zf:
            zf.extractall(p)
        try:
            tmp.unlink()
        except Exception:
            pass

        cj = p / "chunks.jsonl"
        if not (cj.exists() and cj.stat().st_size > 0):
            try:
                cand = next(p.glob("**/chunks.jsonl"))
                p = cand.parent
                cj = cand
            except StopIteration:
                pass

        # ✅ 표준화: 항상 .ready = "ready"
        try:
            core_mark_ready(p)  # SSOT API
        except Exception:
            try:
                (p / ".ready").write_text("ready", encoding="utf-8")
            except Exception:
                pass

        try:
            if "st" in globals() and st is not None:
                st.session_state["_PERSIST_DIR"] = p.resolve()
                st.session_state["_BOOT_RESTORE_DONE"] = True
        except Exception:
            pass
    except Exception:
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


# =============================== [12] diag header — START =============================
def _render_index_orchestrator_header() -> None:
    if "st" not in globals() or st is None:
        return

    st.markdown("### 🧪 인덱스 오케스트레이터")
    persist = _persist_dir_safe()
    with st.container():
        st.caption("Persist Dir")
        st.code(str(persist), language="text")

    # 상태 뱃지
    status_text = "MISSING"
    try:
        from src.rag.index_status import get_index_summary
        s = get_index_summary(persist)
        status_text = "READY" if getattr(s, "ready", False) else "MISSING"
    except Exception:
        status_text = "MISSING"
    badge = "🟩 READY" if status_text == "READY" else "🟨 MISSING"
    st.markdown(f"**상태**\n\n{badge}")

    # 액션들
    cols = st.columns([1, 1, 2]) if _is_admin_view() else [None, None, None]
    if _is_admin_view():
        act_restore = cols[0].button("⬇️ Release에서 최신 인덱스 복원", use_container_width=True)
        act_verify = cols[1].button("✅ 복원 결과 검증", use_container_width=True)
        if act_restore:
            try:
                _boot_auto_restore_index()
                st.success("Release 복원을 시도했습니다. 아래 '최근 복원 결과'와 상태를 확인하세요.")
            except Exception as e:
                st.error(f"복원 실행 실패: {e}")
        if act_verify:
            # 파일시스템 READY 즉시 검증
            cj = persist / "chunks.jsonl"
            rdy = persist / ".ready"
            txt = ""
            try:
                txt = rdy.read_text(encoding="utf-8").strip().lower()
            except Exception:
                txt = ""
            if cj.exists() and cj.stat().st_size > 0 and txt == "ready":
                st.success("검증 성공: chunks.jsonl 존재 & .ready='ready'")
            else:
                st.error("검증 실패: 산출물/ready 상태가 불일치합니다.")

    # 최근 복원 결과 표시
    with st.expander("최근 복원 결과(Release)", expanded=False):
        info = {}
        try:
            info = json.loads((persist / "restore_status.json").read_text(encoding="utf-8"))
        except Exception:
            info = {}
        if info:
            ok = bool(info.get("ok"))
            mark = "🟢 성공" if ok else "🔴 실패"
            tag = info.get("tag") or "-"
            asset = info.get("asset") or "-"
            when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(info.get("ts", 0) or 0)))
            st.write(
                {
                    "결과": mark,
                    "사유": info.get("why", ""),
                    "tag": tag,
                    "asset": asset,
                    "시각": when,
                    "persist": info.get("persist", str(persist)),
                }
            )
        else:
            st.caption("복원 기록이 없습니다. 위의 복원 버튼을 눌러 시도해 보세요.")

    st.info(
        "강제 인덱싱(HQ, 느림)·백업과 인덱싱 파일 미리보기는 **관리자 인덱싱 패널**에서 합니다. "
        "관리자 모드 진입 후 아래 섹션으로 이동하세요.",
        icon="ℹ️",
    )
    st.markdown("<span id='idx-admin-panel'></span>", unsafe_allow_html=True)
# ================================= [12] diag header — END =============================


# =============================== [13] admin index — START =============================
def _render_admin_index_panel() -> None:
    if "st" not in globals() or st is None or not _is_admin_view():
        return

    import datetime as _dt

    st.markdown("<h3>🧭 인덱싱(관리자: prepared 전용)</h3>", unsafe_allow_html=True)

    def _stamp_persist(p: Path) -> None:
        try:
            st.session_state["_PERSIST_DIR"] = p.resolve()
        except Exception:
            pass

    if "_IDX_PH_STEPS" not in st.session_state:
        st.session_state["_IDX_PH_STEPS"] = st.empty()
    if "_IDX_PH_STATUS" not in st.session_state:
        st.session_state["_IDX_PH_STATUS"] = st.empty()
    if "_IDX_PH_BAR" not in st.session_state:
        st.session_state["_IDX_PH_BAR"] = st.empty()
    if "_IDX_PH_LOG" not in st.session_state:
        st.session_state["_IDX_PH_LOG"] = st.empty()
    if "_IDX_PH_S6" not in st.session_state:
        st.session_state["_IDX_PH_S6"] = st.empty()

    step_names: List[str] = ["스캔", "Persist확정", "인덱싱", "prepared소비", "요약/배지", "ZIP/Release"]
    stall_threshold_sec = 60

    def _now_hms_kst() -> str:
        off = int(os.getenv("APP_TZ_OFFSET_HOURS", "9"))
        return (_dt.datetime.utcnow() + _dt.timedelta(hours=off)).strftime("%H:%M:%S")

    def _step_reset(names: List[str]) -> None:
        st.session_state["_IDX_STEPS"] = [{"name": n, "state": "idle", "note": ""} for n in names]
        st.session_state["_IDX_LOG"] = []
        st.session_state["_IDX_PROG"] = 0.0
        st.session_state["_IDX_START_TS"] = time.time()
        st.session_state["_IDX_LAST_TS"] = time.time()
        st.session_state["_IDX_PH_S6"].empty()
        st.session_state["_IDX_S6_BAR"] = None

    def _steps() -> List[Dict[str, str]]:
        if "_IDX_STEPS" not in st.session_state:
            _step_reset(step_names)
        return list(st.session_state["_IDX_STEPS"])

    def _icon(state: str) -> str:
        return {"idle": "⚪", "run": "🔵", "ok": "🟢", "fail": "🔴", "skip": "⚪"}.get(state, "⚪")

    def _render_stepper() -> None:
        lines: List[str] = []
        for i, s in enumerate(_steps(), start=1):
            note = f" — {s.get('note','')}" if s.get("note") else ""
            lines.append(f"{_icon(s['state'])} {i}. {s['name']}{note}")
        st.session_state["_IDX_PH_STEPS"].markdown("\n".join(f"- {ln}" for ln in lines))

    def _update_progress() -> None:
        steps = _steps()
        done = sum(1 for s in steps if s["state"] in ("ok", "skip"))
        prog = done / len(steps)
        bar = st.session_state.get("_IDX_BAR")
        if bar is None:
            st.session_state["_IDX_BAR"] = st.session_state["_IDX_PH_BAR"].progress(prog, text="진행률")
        else:
            try:
                bar.progress(prog)
            except Exception:
                st.session_state["_IDX_BAR"] = st.session_state["_IDX_PH_BAR"].progress(prog, text="진행률")

    def _render_status() -> None:
        now = time.time()
        last = float(st.session_state.get("_IDX_LAST_TS", now))
        start = float(st.session_state.get("_IDX_START_TS", now))
        since_last = int(now - last)
        since_start = int(now - start)
        running = any(s["state"] == "run" for s in _steps())
        stalled = running and since_last >= stall_threshold_sec

        if running:
            text = f"🟦 RUNNING · 마지막 업데이트 {since_last}s 전 · 총 경과 {since_start}s (KST { _now_hms_kst() })"
            st.session_state["_IDX_PH_STATUS"].markdown(text)
            # 1초마다 부드럽게 새로고침(간단한 타이머)
            time.sleep(1.0)
            _safe_rerun("idx_status_tick", ttl=600)
        elif stalled:
            st.session_state["_IDX_PH_STATUS"].markdown(
                f"🟥 STALLED · 마지막 업데이트 {since_last}s 전 · 총 경과 {since_start}s (KST { _now_hms_kst() })"
            )
        else:
            st.session_state["_IDX_PH_STATUS"].markdown("🟩 IDLE/COMPLETE")

    def _step_set(idx: int, state: str, note: str = "") -> None:
        steps = _steps()
        if 0 <= idx < len(steps):
            steps[idx]["state"] = state
            if note:
                steps[idx]["note"] = note
            st.session_state["_IDX_STEPS"] = steps
            st.session_state["_IDX_LAST_TS"] = time.time()
            _render_stepper()
            _update_progress()
            _render_status()

    def _log(msg: str, level: str = "info") -> None:
        buf: List[str] = st.session_state.get("_IDX_LOG", [])
        prefix = {"info": "•", "warn": "⚠", "err": "✖"}.get(level, "•")
        ts = _now_hms_kst()
        line = f"[{ts}] {prefix} {msg}"
        buf.append(line)
        if len(buf) > 200:
            buf = buf[-200:]
        st.session_state["_IDX_LOG"] = buf
        st.session_state["_IDX_PH_LOG"].text("\n".join(buf))
        st.session_state["_IDX_LAST_TS"] = time.time()
        _render_status()

    # prepared 목록
    files_list: List[Dict[str, Any]] = []
    lister, dbg1 = _load_prepared_lister()
    if lister:
        try:
            files_list = lister() or []
        except Exception as e:
            _log(f"prepared list failed: {e}", "err")
    else:
        for m in dbg1:
            _log("• " + m, "warn")
    prepared_count = len(files_list)
    _step_set(0, "ok", f"{prepared_count}건")

    with st.expander("이번에 인덱싱할 prepared 파일(예상)", expanded=False):
        st.write(f"총 {prepared_count}건 (표시는 최대 400건)")
        if prepared_count:
            rows = []
            for rec in files_list[:400]:
                name = str(rec.get("name") or rec.get("path") or rec.get("file") or "")
                fid = str(rec.get("id") or rec.get("fileId") or "")
                rows.append({"name": name, "id": fid})
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("일치하는 파일이 없습니다.")

    with st.form("idx_actions_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        submit_reindex = c1.form_submit_button("🔁 강제 재인덱싱(HQ, prepared)", use_container_width=True)
        show_after = c2.toggle("인덱싱 결과 표시", key="IDX_SHOW_AFTER", value=True)
        auto_up = c3.toggle("인덱싱 후 자동 ZIP 업로드", key="IDX_AUTO_UP", value=False,
                            help="GH/GITHUB 시크릿이 모두 있으면 켜짐")
        reset_view = c4.form_submit_button("🧹 화면 초기화")

        if reset_view:
            _step_reset(step_names)
            st.session_state["_IDX_BAR"] = None
            st.session_state["_IDX_PH_BAR"].empty()
            st.session_state["_IDX_PH_LOG"].empty()
            _log("화면 상태를 초기화했습니다.")

        if submit_reindex:
            st.session_state["_IDX_REQ"] = {
                "ts": time.time(),
                "auto_up": auto_up,
                "show_after": show_after,
            }
            _log("인덱싱 요청 접수")
            _safe_rerun("idx_submit", ttl=1)

    req = st.session_state.pop("_IDX_REQ", None)
    if req:
        used_persist = _persist_dir_safe()
        _step_reset(step_names)
        _render_stepper()
        _render_status()
        st.session_state["_IDX_PH_BAR"].empty()
        st.session_state["_IDX_BAR"] = None
        _log("인덱싱 시작")
        try:
            from src.rag import index_build as _idx
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
                    (used_persist / ".ready").write_text("ready", encoding="utf-8")  # 표준화
                except Exception:
                    pass
                _stamp_persist(used_persist)

            _step_set(3, "run", "prepared 소비 중")
            try:
                chk, mark, dbg2 = _load_prepared_api()
                info: Dict[str, Any] = {}
                new_files: List[str] = []
                cause = "모듈 없음"
                if callable(chk):
                    cause = "새 파일 없음"
                    try:
                        info = chk(used_persist, files_list) or {}
                    except TypeError:
                        info = chk(used_persist) or {}
                    new_files = list(info.get("files") or [])
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
                else:
                    # 문구 명확화
                    _step_set(3, "skip" if cause == "모듈 없음" else "ok", f"0건 ({cause})")
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
                    from urllib import request as _rq, parse as _ps
                    import zipfile

                    def _upload_release_zip(owner: str, repo: str, token: str,
                                            tag: str, zip_path: Path,
                                            name: Optional[str] = None,
                                            body: str = "") -> Dict[str, Any]:
                        api = "https://api.github.com"
                        # release get/create
                        get_url = f"{api}/repos/{owner}/{repo}/releases/tags/{_ps.quote(tag)}"
                        req = _rq.Request(get_url, headers={
                            "Authorization": f"token {token}",
                            "Accept": "application/vnd.github+json"})
                        try:
                            with _rq.urlopen(req, timeout=15) as resp:
                                j = json.loads(resp.read().decode("utf-8", "ignore"))
                        except Exception:
                            payload = json.dumps({"tag_name": tag, "name": name or tag,
                                                  "body": body}).encode("utf-8")
                            req = _rq.Request(f"{api}/repos/{owner}/{repo}/releases",
                                              data=payload, method="POST",
                                              headers={"Authorization": f"token {token}",
                                                       "Accept": "application/vnd.github+json",
                                                       "Content-Type": "application/json"})
                            with _rq.urlopen(req, timeout=15) as resp:
                                j = json.loads(resp.read().decode("utf-8", "ignore"))
                        rid = j.get("id")
                        if not rid:
                            return {"_error": "no_release_id"}

                        # upload
                        up_url = ("https://uploads.github.com/repos/"
                                  f"{owner}/{repo}/releases/{rid}/assets"
                                  f"?name={_ps.quote(zip_path.name)}")
                        data = zip_path.read_bytes()
                        req = _rq.Request(up_url, data=data, method="POST")
                        req.add_header("Authorization", f"token {token}")
                        req.add_header("Content-Type", "application/zip")
                        req.add_header("Accept", "application/vnd.github+json")
                        with _rq.urlopen(req, timeout=180) as resp:
                            try:
                                return json.loads(resp.read().decode("utf-8", "ignore"))
                            except Exception:
                                return {"_raw": "uploaded"}

                    backup_dir = used_persist / "backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    z = backup_dir / f"index_{int(time.time())}.zip"
                    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
                        for root, _d, _f in os.walk(str(used_persist)):
                            for fn in _f:
                                pth = Path(root) / fn
                                zf.write(str(pth), arcname=str(pth.relative_to(used_persist)))

                    tag = f"index-{int(time.time())}"
                    res = _upload_release_zip(ow, rp, tok, tag, z, name=tag, body="MAIC index")
                    if "_error" in res:
                        _step_set(5, "fail", res.get("_error", "error"))
                    else:
                        _step_set(5, "ok", "업로드 완료")
                else:
                    # 분기 명확화
                    reason = "토글 꺼짐" if not req.get("auto_up") else "시크릿 없음"
                    _step_set(5, "skip", reason)
            else:
                _step_set(5, "skip", "토글 꺼짐")

            st.success("강제 재인덱싱 완료 (prepared 전용)")
        except Exception as e:
            _step_set(2, "fail", "인덱싱 실패")
            _log(f"인덱싱 실패: {e}", "err")

    if bool(st.session_state.get("IDX_SHOW_AFTER", True)):
        idx_persist = _persist_dir_safe()
        glb_persist = _persist_dir_safe()
        st.write(f"**Persist(Indexer):** `{str(idx_persist)}`")
        st.write(f"**Persist(Global):** `{str(glb_persist)}`")
        try:
            from src.rag.index_status import get_index_summary
            s = get_index_summary(idx_persist)
            ready_txt = "Yes" if s.ready else "No"
            st.caption(f"요약: ready={ready_txt} · files={s.total_files} · chunks={s.total_chunks}")
            if s.sample_files:
                with st.expander("샘플 파일(최대 3개)", expanded=False):
                    rows = [{"path": x} for x in s.sample_files]
                    st.dataframe(rows, hide_index=True, use_container_width=True)
        except Exception:
            cj = idx_persist / "chunks.jsonl"
            if cj.exists():
                st.caption("요약 모듈 없음: chunks.jsonl 존재")
                if not (idx_persist / ".ready").exists():
                    st.info(".ready 파일이 없어 준비 상태가 미완성입니다.")
            else:
                st.info("`chunks.jsonl`이 아직 없어 결과를 표시할 수 없습니다.")

    with st.expander("실시간 로그 (최근 200줄)", expanded=False):
        buf = st.session_state.get("_IDX_LOG", [])
        if buf:
            st.text("\n".join(buf))
        else:
            st.caption("표시할 로그가 없습니다.")
# ================================= [13] admin index — END =============================

# =============================== [14] admin legacy — START ============================
def _render_admin_panels() -> None:
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

    if not st.session_state.get("_boot_checked"):
        try:
            _boot_auto_restore_index()
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            st.session_state["_boot_checked"] = True

    # ✅ 헤더 렌더링보다 먼저 상태 확정(자동 복원/READY 반영)
    _auto_start_once()

    _mount_background()

    _header()

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

    _inject_chat_styles_once()
    with st.container():
        st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        submitted: bool = False
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요...", key="q_text")
            submitted = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

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
