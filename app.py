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
# ================================ [03] helpers(persist) — END =========================

# ===== [04] bootstrap env — START =====
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
    try:
        st.set_page_config(page_title="LEES AI Teacher",
                           layout="wide", initial_sidebar_state="collapsed")
    except Exception:
        pass

    # 기본 멀티페이지 네비 전역 숨김(학생/관리자 공통)
    try:
        st.markdown(
            "<style>"
            "nav[data-testid='stSidebarNav']{display:none!important;}"
            "div[data-testid='stSidebarNav']{display:none!important;}"
            "</style>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass
# ===== [04] bootstrap env — END =====

# ======================= [05] logger — START =======================
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
# ===================== [05] logger — END ========================

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
def _safe_rerun(tag: str, ttl: float = 0.3) -> None:

    """
    Debounced rerun. One rerun per 'tag' within TTL seconds.
    """
    s = globals().get("st", None)
    if s is None:
        return
    try:
        ss = getattr(s, "session_state", None)
        if ss is None:
            return
        tag = str(tag or "rerun")
        ttl_s = 0.3 if not isinstance(ttl, (int, float)) or ttl <= 0 else float(ttl)
        key = "__rerun_counts__"
        counts = ss.get(key)
        if not isinstance(counts, dict):
            counts = {}
        rec = counts.get(tag) or {}
        cnt = int(rec.get("count", 0)) if isinstance(rec, dict) else int(rec or 0)
        exp = float(rec.get("expires_at", 0.0)) if isinstance(rec, dict) else 0.0
        now = time.time()
        if exp and now >= exp:
            try:
                counts.pop(tag, None)
            except Exception:
                counts = {}
            cnt = 0
            exp = 0.0

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
        pass
# ================================= [07] rerun guard — END =============================

# =============================== [08] header — START ==================================
def _header() -> None:
    """
    헤더 배지: src.ui.header.render가 있으면 그걸 사용(3단계 규칙),
    없으면 파일시스템 READY로 폴백.
    """
    try:
        from src.ui.header import render as _render_header
        _render_header()  # C)를 충족 (H1 합의)
        return
    except Exception:
        pass

    # 폴백
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

# =============================== [10] auto-restore — START ============================
def _boot_auto_restore_index() -> None:
    """
    최신 릴리스 자동 복원 훅.
    - 진행표시: src.services.index_state(step/log/stepper) 안전호출
    - 세션 플래그: _INDEX_IS_LATEST / _INDEX_LOCAL_READY / _BOOT_RESTORE_DONE
    """
    # 멱등
    try:
        if st is not None and st.session_state.get("_BOOT_RESTORE_DONE"):
            return
    except Exception:
        pass

    # 진행표시 안전 호출자
    def _idx(name: str, *args, **kwargs):
        try:
            mod = importlib.import_module("src.services.index_state")
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        except Exception:
            return None

    # placeholder/첫 렌더
    _idx("ensure_index_state")
    if _is_admin_view():
        _idx("render_index_steps")
    else:
        _idx("render_stepper_safe", True)   # 학생: 미니멀

    _idx("log", "부팅: 인덱스 복원 준비 중...")

    p = effective_persist_dir()
    cj = p / "chunks.jsonl"
    rf = p / ".ready"

    # 공용 판정기
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

    # 로컬 준비 기록
    _idx("step_set", 1, "run", "로컬 준비 상태 확인")
    try:
        ready_txt = rf.read_text(encoding="utf-8") if rf.exists() else ""
    except Exception:
        ready_txt = ""
    local_ready = cj.exists() and cj.stat().st_size > 0 and is_ready_text(ready_txt)
    try:
        if st is not None:
            st.session_state["_INDEX_LOCAL_READY"] = bool(local_ready)
            st.session_state.setdefault("_INDEX_IS_LATEST", False)
    except Exception:
        pass
    _idx("step_set", 1, "ok" if local_ready else "wait", "로컬 준비 기록")

    # GH 최신 조회
    _idx("step_set", 2, "run", "원격 릴리스 조회")
    repo_full = os.getenv("GITHUB_REPO", "")
    token = os.getenv("GITHUB_TOKEN", None)
    try:
        if st is not None:
            repo_full = st.secrets.get("GITHUB_REPO", repo_full)
            token = st.secrets.get("GITHUB_TOKEN", token)
    except Exception:
        pass
    if not repo_full or "/" not in str(repo_full):
        _idx("log", "GITHUB_REPO 미설정 → 원격 확인 불가", "warn")
        _idx("step_set", 2, "wait", "원격 확인 불가")
        try:
            if st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
        except Exception:
            pass
        return

    owner, repo = str(repo_full).split("/", 1)
    try:
        from src.runtime.gh_release import GHConfig as _GHConfig, GHReleases as _GHReleases  # primary
        GHConfig, GHReleases = _GHConfig, _GHReleases
    except Exception:
        _idx("log", "GH 모듈 불가 → 최신 판정 보류", "warn")
        _idx("step_set", 2, "wait", "원격 확인 불가")
        try:
            if st is not None:
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
        remote_release_id = int(raw_id) if isinstance(raw_id, (int, float, str)) else None
        _idx("log", f"원격 최신 태그: {remote_tag or '없음'}")
    except Exception:
        _idx("log", "원격 최신 릴리스 조회 실패", "warn")
    finally:
        try:
            if st is not None:
                st.session_state["_LATEST_RELEASE_TAG"] = remote_tag
                st.session_state["_LATEST_RELEASE_ID"] = remote_release_id
        except Exception:
            pass

    # 메타 일치→생략
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
    if local_ready and remote_tag and _safe_meta_matches(stored_meta, remote_tag):
        _idx("log", "메타 일치: 복원 생략(이미 최신)")
        _idx("step_set", 2, "ok", "메타 일치")
        try:
            if st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = True
        except Exception:
            pass
        return

    # 강제 복원
    try:
        import datetime as _dt
        this_year = _dt.datetime.utcnow().year
        dyn_tags = [f"index-{y}-latest" for y in range(this_year, this_year - 5, -1)]
    except Exception:
        dyn_tags = []
    tag_candidates = ["indices-latest", "index-latest"] + dyn_tags + ["latest"]
    asset_candidates = ["indices.zip", "persist.zip", "hq_index.zip", "prepared.zip"]

    _idx("step_set", 2, "run", "최신 인덱스 복원 중...")
    try:
        result = gh.restore_latest_index(
            tag_candidates=tag_candidates,
            asset_candidates=asset_candidates,
            dest=p,
            clean_dest=True,
        )
        _idx("step_set", 2, "ok", "복원 완료")
        _idx("step_set", 3, "run", "메타 저장/정리...")
        normalize_ready_file(p)
        saved_meta = _safe_save_meta(
            p,
            tag=(getattr(result, "tag", None) or remote_tag),
            release_id=(getattr(result, "release_id", None) or remote_release_id),
        )

        try:
            if st is not None:
                st.session_state["_PERSIST_DIR"] = p.resolve()
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state["_INDEX_IS_LATEST"] = True
                st.session_state["_INDEX_LOCAL_READY"] = True
                if saved_meta is not None:
                    st.session_state["_LAST_RESTORE_META"] = getattr(saved_meta, "to_dict", lambda: {})()
        except Exception:
            pass
        _idx("step_set", 3, "ok", "메타 저장 완료")
        _idx("step_set", 4, "ok", "마무리 정리")
        _idx("log", "✅ 최신 인덱스 복원 완료")
    except Exception as exc:
        _idx("step_set", 2, "err", f"복원 실패: {exc}")
        _idx("log", f"❌ 최신 인덱스 복원 실패: {exc}", "err")
        try:
            if st is not None:
                st.session_state["_BOOT_RESTORE_DONE"] = True
                st.session_state.setdefault("_PERSIST_DIR", p.resolve())
                st.session_state["_INDEX_IS_LATEST"] = False
        except Exception:
            pass
        return
# ================================= [10] auto-restore — END ============================

# =============================== [12] progress stepper — START =========================
def _render_stepper(*, force: bool = False) -> None:
    """
    학생용: 미니멀 퍼센트 바 + 상태 문구.
    - 데이터 소스: st.session_state["_IDX_STEPS"]
      각 스텝 status: wait/run/ok/err
    - 퍼센트: ok=1.0, run=0.5, wait=0.0, err=1.0(빨간 표시)
    """
    if st is None:
        return
    ss = st.session_state
    steps: List[Dict[str, Any]] = list(ss.get("_IDX_STEPS") or [])
    if not steps and not force:
        return

    # 진행도 계산
    status_val = {"ok": 1.0, "run": 0.5, "wait": 0.0, "err": 1.0}
    vals = [status_val.get(str(s.get("status")), 0.0) for s in steps] or [0.0]
    pct = int(round(100 * sum(vals) / max(1, len(vals))))

    # 가장 최근 활성/오류 메시지
    last_msg = ""
    for s in reversed(steps):
        d = str(s.get("detail") or "").strip()
        if d:
            last_msg = d
            break
    if not last_msg:
        last_msg = "릴리스 확인 중..."

    # 스타일
    st.markdown(
        """
        <style>
          .mini-bar{border:1px solid #E5E7EB;border-radius:12px;background:#F9FAFB;height:14px;overflow:hidden;}
          .mini-bar > div{height:100%;transition:width .25s ease;}
          .mini-bar.ok > div{background:#16a34a;}
          .mini-bar.run > div{background:#f59e0b;}
          .mini-bar.err > div{background:#ef4444;}
          .mini-line{display:flex;align-items:center;gap:10px;}
          .mini-label{font-weight:700;color:#111827;}
          .mini-pct{font-weight:800;min-width:3ch;text-align:right;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 현재 상태 클래스
    cls = "ok"
    if any(s.get("status") == "err" for s in steps):
        cls = "err"
    elif any(s.get("status") == "run" for s in steps):
        cls = "run"

    with st.container(border=True):
        st.markdown(f"<div class='mini-line'><span class='mini-label'>{last_msg}</span>"
                    f"<span class='mini-pct'>{pct}%</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='mini-bar {cls}'><div style='width:{pct}%;'></div></div>",
                    unsafe_allow_html=True)
# =============================== [12] progress stepper — END ===========================


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
  .chatpane-messages{position:relative;background:#EDF4FF;border:1px solid #D5E6FF;border-radius:18px;padding:10px;margin-top:12px;}
  .chatpane-messages .messages{ max-height:60vh; overflow-y:auto; padding:8px; }
  .chatpane-input{position:relative;background:#EDF4FF;border:1px solid #D5E6FF;border-radius:18px;padding:8px 10px 10px 10px;margin-top:12px;}
  .chatpane-input div[data-testid="stRadio"]{ background:#EDF4FF; padding:8px 10px 0 10px; margin:0; }
  .chatpane-input div[data-testid="stRadio"] [role="radio"]{border:2px solid #bcdcff;border-radius:12px;padding:6px 12px;background:#fff;color:#0a2540;font-weight:700;font-size:14px;line-height:1;}
  .chatpane-input form[data-testid="stForm"] .stButton > button{width:38px;height:38px;border-radius:50%;border:0;background:#0a2540;color:#fff;font-size:18px;line-height:1;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.15);padding:0;min-height:0;}
  .msg-row{ display:flex; margin:8px 0; }
  .msg-row.left{ justify-content:flex-start; }
  .msg-row.right{ justify-content:flex-end; }
  .bubble{ max-width:88%; padding:10px 12px; border-radius:16px; line-height:1.6; font-size:15px;
           box-shadow:0 1px 1px rgba(0,0,0,.05); white-space:pre-wrap; position:relative; }
  .bubble.user{ border-top-right-radius:8px; border:1px solid #F2E4A2; background:#FFF8CC; color:#333; }
  .bubble.ai  { border-top-left-radius:8px;  border:1px solid #BEE3FF; background:#EAF6FF; color:#0a2540; }
  .chip{display:inline-block;margin:-2px 0 6px 0;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;line-height:1;}
  .chip.me{ background:#059669; } .chip.pt{ background:#2563eb; } .chip.mn{ background:#7c3aed; }
  .chip-src{display:inline-block;margin-left:6px;padding:2px 8px;border-radius:10px;background:#eef2ff;color:#3730a3;font-size:12px;font-weight:600;line-height:1;border:1px solid #c7d2fe;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle;}
  @media (max-width:480px){ .bubble{ max-width:96%; } .chip-src{ max-width:160px; } }
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
    import html, re
    from typing import Optional, Callable
    from src.agents.responder import answer_stream
    from src.agents.evaluator import evaluate_stream
    from src.llm.streaming import BufferOptions, make_stream_handler

    # 라벨링 유틸(선택적)
    try:
        try:
            _label_mod = _imp.import_module("src.rag.label")
        except Exception:
            _label_mod = _imp.import_module("label")
        _decide_label = getattr(_label_mod, "decide_label", None)
        _search_hits = getattr(_label_mod, "search_hits", None)
        _make_chip = getattr(_label_mod, "make_source_chip", None)
    except Exception:
        _decide_label = _search_hits = _make_chip = None

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

    def _emit_bubble(ph, who: str, acc_text: str, *, source: Optional[str], align_right: bool) -> None:
        side_cls = "right" if align_right else "left"
        klass = "user" if align_right else "ai"
        chips = _chip_html(who) + (_src_html(source) if not align_right else "")
        html_block = (
            f'<div class="msg-row {side_cls}">'
            f'  <div class="bubble {klass}">{chips}<br/>{_esc(acc_text)}</div>'
            f"</div>"
        )
        ph.markdown(html_block, unsafe_allow_html=True)

    if st is None:
        return
    ss = st.session_state
    question = str(ss.get("inpane_q", "") or "").strip()
    if not question:
        return

    # 출처 라벨(지연 갱신 가능)
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

    chip_text = src_label
    if callable(_make_chip):
        try:
            chip_text = _make_chip(hits, src_label)
        except Exception:
            chip_text = src_label

    # 0) 유저 버블
    ph_user = st.empty()
    _emit_bubble(ph_user, "나", question, source=None, align_right=True)

    # 1) 타이핑 버블(즉시)
    ph_typing = st.empty()
    _emit_bubble(ph_typing, "피티쌤", "...", source=chip_text, align_right=False)

    # 2) 답변 스트리밍
    ph_ans = st.empty()
    acc_ans = ""
    first_chunk = {"seen": False}

    def _on_emit_ans(chunk: str) -> None:
        nonlocal acc_ans
        acc_ans += str(chunk or "")
        # 첫 청크에서 타이핑 버블 치환
        if not first_chunk["seen"]:
            try:
                ph_typing.empty()
            except Exception:
                pass
            first_chunk["seen"] = True
        _emit_bubble(ph_ans, "피티쌤", acc_ans, source=chip_text, align_right=False)

    emit_chunk_ans, close_stream_ans = make_stream_handler(
        on_emit=_on_emit_ans,
        opts=BufferOptions(min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
                           flush_on_strong_punct=True, flush_on_newline=True),
    )
    for piece in answer_stream(question=question, mode=ss.get("__mode", "")):
        emit_chunk_ans(str(piece or ""))
    close_stream_ans()
    full_answer = acc_ans.strip()

    # 3) 평가 스트리밍
    ph_eval = st.empty()
    acc_eval = ""
    def _on_emit_eval(chunk: str) -> None:
        nonlocal acc_eval
        acc_eval += str(chunk or "")
        _emit_bubble(ph_eval, "미나쌤", acc_eval, source=chip_text, align_right=False)

    emit_chunk_eval, close_stream_eval = make_stream_handler(
        on_emit=_on_emit_eval,
        opts=BufferOptions(min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
                           flush_on_strong_punct=True, flush_on_newline=True),
    )
    for piece in evaluate_stream(question=question, mode=ss.get("__mode", ""), answer=full_answer,
                                 ctx={"answer": full_answer}):
        emit_chunk_eval(str(piece or ""))
    close_stream_eval()

    ss["last_q"] = question
    ss["inpane_q"] = ""
# ================================= [18] chat panel — END ==============================

# =============================== [19] body & main — START =============================
def _render_body() -> None:
    if st is None:
        return

    ss = st.session_state

    # 1) 부팅 2-Phase: (A) 헤더/스켈레톤 선렌더 → (B) 복원 → 재실행 1회
    boot_pending = not bool(ss.get("_boot_checked"))
    if boot_pending:
        # (A) 헤더 우선: 복원 전 초록 금지 세션 초기화
        try:
            local_ok = core_is_ready(effective_persist_dir())
        except Exception:
            local_ok = False
        ss["_INDEX_LOCAL_READY"] = bool(local_ok)
        ss["_INDEX_IS_LATEST"] = False
        ss["_RESTORE_IN_PROGRESS"] = True

        _header()  # 헤더 먼저(노란/주황 노출)

        # 간이 스텝퍼 placeholder/로그
        try:
            mod = importlib.import_module("src.services.index_state")
            getattr(mod, "step_reset", lambda *_a, **_k: None)()
            getattr(mod, "log", lambda *_a, **_k: None)("🔎 릴리스 확인 중...")
            getattr(mod, "render_index_steps", lambda *_a, **_k: None)()
        except Exception:
            pass

        # (B) 자동 복원 실행 → 상태 표준화 → 1회 재실행
        try:
            _boot_auto_restore_index()
            try:
                core_mark_ready(effective_persist_dir())
            except Exception:
                pass
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            ss["_RESTORE_IN_PROGRESS"] = False
            ss["_boot_checked"] = True

        try:
            _safe_rerun("boot_init", ttl=0.5)
        except Exception:
            pass
        return

    # 2) 헤더
    _header()

    # 3) 관리자 패널(오케스트레이터/인덱싱)
    if _is_admin_view():
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
        for fn in (render_prepared_scan_panel, render_index_panel, render_indexed_sources_panel):
            try:
                if callable(fn):
                    fn()
            except Exception:
                pass

    # 4) 채팅 메시지 영역
    _inject_chat_styles_once()
    with st.container(key="chat_messages_container"):
        st.markdown('<div class="chatpane-messages" data-testid="chat-messages"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown("</div></div>", unsafe_allow_html=True)

    # 5) 입력 폼
    with st.container(border=True, key="chat_input_container"):
        st.markdown('<div class="chatpane-input" data-testid="chat-input">', unsafe_allow_html=True)
        ss["__mode"] = _render_mode_controls_pills() or ss.get("__mode", "")
        submitted: bool = False
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요...", key="q_text")
            submitted = st.form_submit_button("➤")
        st.markdown("</div>", unsafe_allow_html=True)

    # 6) 전송 처리
    if submitted and isinstance(q, str) and q.strip():
        ss["inpane_q"] = q.strip()
        _safe_rerun("chat_submit", ttl=1)
    else:
        ss.setdefault("inpane_q", "")


def main() -> None:
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()

if __name__ == "__main__":
    main()
# ================================= [19] body & main — END =============================
