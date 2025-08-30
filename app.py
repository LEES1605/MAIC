# [01] future import ==========================================================
from __future__ import annotations

# [02] bootstrap & imports ====================================================
import os, io, json, time, traceback, importlib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except Exception:
    st = None  # 로컬/테스트 환경 방어

# [03] secrets → env 승격 & 서버 안정 옵션 ====================================
def _from_secrets(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if st is None or not hasattr(st, "secrets"):
            return os.getenv(name, default)
        val = st.secrets.get(name, None)  # type: ignore[attr-defined]
        if val is None:
            return os.getenv(name, default)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)

def _bootstrap_env() -> None:
    keys = [
        "OPENAI_API_KEY","OPENAI_MODEL","GEMINI_API_KEY","GEMINI_MODEL",
        "GITHUB_TOKEN","GITHUB_REPO",
        "GDRIVE_PREPARED_FOLDER_ID","GDRIVE_BACKUP_FOLDER_ID",
        "APP_MODE","AUTO_START_MODE","LOCK_MODE_FOR_STUDENTS","APP_ADMIN_PASSWORD",
    ]
    for k in keys:
        v = _from_secrets(k)
        if v and not os.getenv(k):
            os.environ[k] = str(v)
    # Streamlit 안정화
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")

_bootstrap_env()

# [04] 경로/상태 & 에러로그 =====================================================
def _persist_dir() -> Path:
    try:
        from src.config import PERSIST_DIR as CFG
        return Path(CFG).expanduser()
    except Exception:
        return Path.home() / ".maic" / "persist"

PERSIST_DIR = _persist_dir()
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

def _is_brain_ready() -> bool:
    p = PERSIST_DIR
    if not p.exists():
        return False
    signals = ["chunks.jsonl","manifest.json",".ready","faiss.index","index.faiss","chroma.sqlite","docstore.json"]
    for s in signals:
        fp = p / s
        try:
            if fp.exists() and fp.stat().st_size > 0:
                return True
        except Exception:
            pass
    return False

def _mark_ready() -> None:
    try:
        (PERSIST_DIR / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass

def _errlog(msg: str, *, where: str = "", exc: BaseException | None = None) -> None:
    if st is None:
        return
    ss = st.session_state
    ss.setdefault("_error_log", [])
    ss["_error_log"].append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "where": where,
        "msg": str(msg),
        "trace": traceback.format_exc() if exc else "",
    })

def _errlog_text() -> str:
    if st is None:
        return ""
    out = io.StringIO()
    for i, r in enumerate(st.session_state.get("_error_log", []), 1):
        out.write(f"[{i}] {r['ts']} {r.get('where','')}\n{r['msg']}\n")
        if r.get("trace"):
            out.write(r["trace"] + "\n")
        out.write("-" * 60 + "\n")
    return out.getvalue()

# [05] 동적 임포트 바인딩 =======================================================
_import_warns: List[str] = []

def _try_import(mod: str, attrs: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        m = importlib.import_module(mod)
    except Exception as e:
        _import_warns.append(f"{mod}: {type(e).__name__}: {e}")
        return out
    for a in attrs:
        try:
            out[a] = getattr(m, a)
        except Exception:
            pass
    return out

_ui_admin = _try_import("src.ui_admin", [
    "ensure_admin_session_keys", "render_admin_controls", "render_role_caption", "render_mode_radio_admin"
])
_ui_orch = _try_import("src.ui_orchestrator", ["render_index_orchestrator_panel"])
_gh      = _try_import("src.backup.github_release", ["restore_latest"])
_rag     = _try_import("src.rag.index_build", ["build_index_with_checkpoint"])
_llm     = _try_import("src.llm.providers", ["call_with_fallback"])
_prompt = _try_import("src.prompt_modes", ["build_prompt"])


# [06] 페이지 설정 & 헤더(인라인 로그인만 사용, Enter 제출 지원) ================
if st:
    st.set_page_config(page_title="LEES AI Teacher", layout="wide")

def _is_admin_view() -> bool:
    env = (os.getenv("APP_MODE") or _from_secrets("APP_MODE", "student") or "student").lower()
    return bool(env == "admin" or (st and (st.session_state.get("is_admin") or st.session_state.get("admin_mode"))))

def _toggle_login_flag():
    st.session_state["_show_admin_login"] = not st.session_state.get("_show_admin_login", False)

def _llm_health() -> tuple[str, str]:
    has_cb = bool(_llm.get("call_with_fallback"))
    has_g  = bool(os.getenv("GEMINI_API_KEY") or _from_secrets("GEMINI_API_KEY"))
    has_o  = bool(os.getenv("OPENAI_API_KEY") or _from_secrets("OPENAI_API_KEY"))
    if not has_cb: return ("미탑재", "⚠️")
    if not (has_g or has_o): return ("키없음", "⚠️")
    if has_g and has_o: return ("Gemini/OpenAI", "✅")
    return ("Gemini", "✅") if has_g else ("OpenAI", "✅")

def _header():
    if st is None:
        return
    ss = st.session_state
    ss.setdefault("_show_admin_login", False)

    left, right = st.columns([0.78, 0.22])
    with left:
        st.markdown("### LEES AI Teacher")
    with right:
        if _is_admin_view():
            st.markdown("**🟢 준비완료**" if _is_brain_ready() else "**🟡 준비중**")
        label, icon = _llm_health()
        st.caption(f"LLM: {icon} {label}")

        if _is_admin_view():
            # ✅ 관리자 모드: '관리자 해제'만 노출
            if st.button("관리자 해제", use_container_width=True):
                ss["admin_mode"] = False
                ss["_show_admin_login"] = False
                st.rerun()
        else:
            # ✅ 학생 모드: '관리자' 버튼 → 인라인 로그인 폼 토글
            if st.button("관리자", use_container_width=True):
                _toggle_login_flag()

            # 인라인 로그인 폼 (Enter 제출: st.form)
            if ss.get("_show_admin_login", False):
                pwd_set = os.getenv("APP_ADMIN_PASSWORD") or _from_secrets("APP_ADMIN_PASSWORD", "0000") or "0000"
                with st.container(border=True):
                    with st.form("admin_login_form", clear_on_submit=True):
                        pw = st.text_input("관리자 비밀번호", type="password", label_visibility="collapsed")
                        c1, c2 = st.columns([0.5, 0.5])
                        with c1:
                            submit = st.form_submit_button("로그인", use_container_width=True)
                        with c2:
                            close  = st.form_submit_button("닫기",   use_container_width=True)
                    if submit:
                        if pw and pw == str(pwd_set):
                            ss["admin_mode"] = True
                            ss["_show_admin_login"] = False
                            st.success("로그인 성공")
                            st.rerun()
                        else:
                            st.error("비밀번호가 올바르지 않습니다.")
                    elif close:
                        ss["_show_admin_login"] = False
                        st.rerun()

    if _import_warns:
        with st.expander("임포트 경고", expanded=False):
            for w in _import_warns:
                st.code(w, language="text")
    st.divider()

# ✅ 본문 로그인 패널은 완전 제거(호환용 NOP). 호출도 더 이상 하지 않음.
def _login_panel_if_needed():
    return

# [07] MAIN: 자동 연결(attach) / 변경 없으면 릴리스 복구 / 변경 있으면 선택대기 =======  # [07] START
def _auto_attach_or_build_index():
    """
    우선순위:
    1) 로컬 인덱스(chunks.jsonl/.ready) 존재 → Drive diff 검사
       - 변경 없음(False) 또는 판단 불가(None): 곧바로 attach(READY)
       - 변경 있음(True): 현재 로컬로 attach(READY) + 관리자 선택 대기(index_decision_needed=True)
    2) 로컬 없으면 → GitHub Releases에서 복구(restore) → diff 검사
       - 변경 없음(False) 또는 판단 불가(None): attach(READY)
       - 변경 있음(True): Releases로 attach(READY) + 관리자 선택 대기(index_decision_needed=True)
    3) 빌드는 관리자가 명시적으로 요청할 때만 수행(재빌드/인덱싱하기 버튼)
    모든 성공 경로에서 UI 상태 플래그와 `.ready` 파일을 보장한다.
    """
    import json, pathlib
    ss = st.session_state
    if ss.get("_index_boot_ran_v5"):
        return
    ss["_index_boot_ran_v5"] = True

    # 상태 기본값
    ss.setdefault("brain_attached", False)
    ss.setdefault("brain_status_msg", "초기화 중…")
    ss.setdefault("index_status_code", "INIT")
    ss.setdefault("index_source", "")
    ss.setdefault("restore_recommend", False)
    ss.setdefault("index_decision_needed", False)
    ss.setdefault("index_change_stats", {})

    # 필요한 모듈(동적 임포트)
    idx = _try_import("src.rag.index_build", [
        "quick_precheck", "diff_with_manifest"
    ]) or {}
    rel = _try_import("src.backup.github_release", ["restore_latest"]) or {}

    quick = idx.get("quick_precheck")
    diff  = idx.get("diff_with_manifest")
    restore_latest = rel.get("restore_latest")

    # 표준 경로
    persist_path = PERSIST_DIR
    chunks_path  = persist_path / "chunks.jsonl"
    ready_flag   = persist_path / ".ready"

    def _touch_ready():
        try:
            persist_path.mkdir(parents=True, exist_ok=True)
            ready_flag.write_text("ok", encoding="utf-8")
        except Exception:
            pass

    def _attach_success(source: str, msg: str):
        _touch_ready()
        ss["brain_attached"] = True
        ss["brain_status_msg"] = msg
        ss["index_status_code"] = "READY"
        ss["index_source"] = source
        ss["restore_recommend"] = False

    def _set_decision(wait: bool, stats: dict | None = None):
        ss["index_decision_needed"] = bool(wait)
        ss["index_change_stats"] = stats or {}

    def _try_diff() -> tuple[bool|None, dict]:
        """(changed_flag, stats_dict) 반환. 실패 시 (None, {})."""
        if not callable(diff):
            return None, {}
        try:
            d = diff() or {}
            if not d.get("ok"):
                return None, {}
            stts = d.get("stats") or {}
            changed_total = int(stts.get("added", 0)) + int(stts.get("changed", 0)) + int(stts.get("removed", 0))
            return (changed_total > 0), stts
        except Exception as e:
            _errlog(f"diff 실패: {e}", where="[index_boot]")
            return None, {}

    # 0) 로컬 인덱스 빠른 점검
    if not callable(quick):
        ss["index_status_code"] = "MISSING"
        return

    try:
        pre = quick() or {}
    except Exception as e:
        _errlog(f"precheck 예외: {e}", where="[index_boot]")
        pre = {}

    # 1) 로컬 인덱스가 이미 있으면: attach 후 diff 판단
    if pre.get("ok") and pre.get("ready"):
        ch, stts = _try_diff()
        if ch is True:
            _attach_success("local", "로컬 인덱스 연결됨(신규/변경 감지)")
            _set_decision(True, stts)
            return
        else:
            _attach_success("local", "로컬 인덱스 연결됨(변경 없음/판단 불가)")
            _set_decision(False, stts)
            return

    # 2) 로컬이 없으면: Releases에서 복구(자동)
    restored = False
    if callable(restore_latest):
        try:
            restored = bool(restore_latest(persist_path))
        except Exception as e:
            _errlog(f"restore 실패: {e}", where="[index_boot]")

    if restored and chunks_path.exists():
        ch2, stts2 = _try_diff()
        if ch2 is True:
            _attach_success("release", "Releases에서 복구·연결(신규/변경 감지)")
            _set_decision(True, stts2)
            return
        else:
            _attach_success("release", "Releases에서 복구·연결(변경 없음/판단 불가)")
            _set_decision(False, stts2)
            return

    # 3) 여기까지 왔으면 로컬/릴리스 모두 실패 — 상태만 남김(관리자 재빌드 버튼으로 해결)
    ss["brain_attached"] = False
    ss["brain_status_msg"] = "인덱스 없음(관리자에서 재빌드 필요)"
    ss["index_status_code"] = "MISSING"
    _set_decision(False, {})
    return

# 모듈 초기화 시 1회 자동 실행
_auto_attach_or_build_index()
# [07] MAIN: 자동 연결(attach) / 변경 없으면 릴리스 복구 / 변경 있으면 선택대기 =======  # [07] END

# [08] 자동 시작(선택) =========================================================
def _auto_start_once():
    if st is None or st.session_state.get("_auto_started"):
        return
    st.session_state["_auto_started"] = True
    if _is_brain_ready():
        return
    mode = (os.getenv("AUTO_START_MODE") or _from_secrets("AUTO_START_MODE", "off") or "off").lower()
    if mode in ("restore", "on") and _gh.get("restore_latest"):
        try:
            if _gh["restore_latest"](dest_dir=PERSIST_DIR):
                _mark_ready()
                st.toast("자동 복원 완료", icon="✅")
                st.rerun()
        except Exception as e:
            _errlog(f"auto restore failed: {e}", where="[auto_start]", exc=e)

# [09] 설명 모드 허용/기본값 & 관리자 패널 정의(이름 오류 방지) ==================
def _modes_cfg_path() -> Path:
    return PERSIST_DIR / "explain_modes.json"

def _load_modes_cfg() -> Dict[str, Any]:
    try:
        p = _modes_cfg_path()
        if not p.exists():
            return {"allowed": ["문법", "문장", "지문"], "default": "문법"}
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"allowed": ["문법", "문장", "지문"], "default": "문법"}

def _save_modes_cfg(cfg: Dict[str, Any]) -> None:
    try:
        _modes_cfg_path().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _errlog(f"save modes cfg failed: {e}", where="[modes_save]", exc=e)

def _sanitize_modes_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    modes = ["문법", "문장", "지문"]
    allowed = [m for m in (cfg.get("allowed") or []) if m in modes]
    default = cfg.get("default") or "문법"
    if default not in modes:
        default = "문법"
    return {"allowed": allowed, "default": default}

_LABELS    = {"문법": "어법", "문장": "문장", "지문": "지문"}             # 표시 라벨
_LLM_TOKEN = {"문법": "문법설명", "문장": "문장구조분석", "지문": "지문분석"}  # LLM 호출 토큰

# 토큰↔메뉴 키 변환(호환 어댑터)
def _mode_to_token(m: str) -> str:
    return {"문법":"문법설명","문장":"문장구조분석","지문":"지문분석"}.get(m, m)

def _token_to_mode(t: str) -> str:
    inv = {"문법설명":"문법","문장구조분석":"문장","지문분석":"지문"}
    return inv.get(t, t)

def _render_admin_panels() -> None:
    """관리자 패널(정의 보장 + ui_admin과 키 호환)"""
    if st is None or not _is_admin_view():
        return

    # 외부 모듈 패널
    if _ui_admin.get("ensure_admin_session_keys"): _ui_admin["ensure_admin_session_keys"]()
    if _ui_admin.get("render_admin_controls"):     _ui_admin["render_admin_controls"]()
    if _ui_admin.get("render_role_caption"):       _ui_admin["render_role_caption"]()
    st.divider()

    st.markdown("## 관리자: 자료/인덱스 관리")
    if _ui_orch.get("render_index_orchestrator_panel"):
        try:
            _ui_orch["render_index_orchestrator_panel"]()
        except Exception as e:
            st.error(f"오케스트레이터 패널 오류: {type(e).__name__}: {e}")
            _errlog(f"ui_orchestrator error: {e}", where="[admin_panel]", exc=e)
    else:
        st.info("오케스트레이터 모듈이 없습니다: src.ui_orchestrator")

    st.markdown("### 설명 모드 허용 설정")
    cfg = _sanitize_modes_cfg(_load_modes_cfg())
    a = set(cfg["allowed"])
    c1, c2, c3 = st.columns(3)
    with c1: g = st.checkbox("문법", value=("문법" in a))
    with c2: s = st.checkbox("문장", value=("문장" in a))
    with c3: p = st.checkbox("지문", value=("지문" in a))
    base_modes = ["문법", "문장", "지문"]
    default_sel = st.selectbox("기본 모드(학생 초기값)", base_modes, index=base_modes.index(cfg["default"]))
    if st.button("허용 설정 저장", type="primary"):
        new_cfg = _sanitize_modes_cfg({
            "allowed": [m for m, v in [("문법", g), ("문장", s), ("지문", p)] if v],
            "default": default_sel
        })
        _save_modes_cfg(new_cfg)
        st.success("저장 완료")
        st.rerun()

    # ---- ui_admin 라디오와의 키 호환 래핑 ------------------------------------
    if _ui_admin.get("render_mode_radio_admin"):
        st.markdown("#### (관리자 전용) 미리보기용 모드 선택")
        ss = st.session_state
        cur_mode = ss.get("qa_mode_radio") or cfg["default"]
        ss["_qa_mode_backup"] = cur_mode
        ss["qa_mode_radio"] = _mode_to_token(cur_mode)
        try:
            _ui_admin["render_mode_radio_admin"]()
        except Exception as e:
            st.warning(f"관리자 미리보기 패널 경고: {type(e).__name__}: {e}")
        finally:
            sel_token = ss.get("qa_mode_radio", _mode_to_token(cur_mode))
            ss["qa_mode_radio"] = _token_to_mode(sel_token)
            ss.pop("_qa_mode_backup", None)
    # -------------------------------------------------------------------------

    with st.expander("오류 로그", expanded=False):
        txt = _errlog_text()
        st.text_area("최근 오류", value=txt, height=180)
        st.download_button("로그 다운로드", data=txt.encode("utf-8"), file_name="app_error_log.txt")

# [10] 학생 UI (Stable Chatbot v2): 파스텔 하늘 배경 + 말풍선 + 모드(Pill) + 2스텝 렌더  # [10] START
# ──────────────────────────────────────────────────────────────────────────────
# [10A] UI(고정): 스타일 / 모드(Pill) / 말풍선 렌더러 / 헬퍼
def _inject_chat_styles_once():
    if st.session_state.get("_chat_styles_injected"):
        return
    st.session_state["_chat_styles_injected"] = True
    st.markdown("""
    <style>
      /* 상태 배지 */
      .status-btn{display:inline-block; padding:6px 10px; border-radius:14px;
        font-size:12px; font-weight:700; color:#111; border:1px solid transparent;}
      .status-btn.green{ background:#daf5cb; border-color:#bfe5ac; }
      .status-btn.yellow{ background:#fff3bf; border-color:#ffe08a; }

      /* 모드 선택: 파스텔 하늘색 Pill */
      .mode-zone{ margin:6px 0 2px 0; }
      .mode-pill{
        display:block; width:100%; text-align:center; padding:10px 12px;
        border:2px solid #bcdcff; border-radius:16px; background:#ffffff;
        color:#0a2540; font-weight:700;
      }
      .mode-pill.active{
        background:#eaf6ff;  /* 파스텔 하늘 */
        border-color:#9fd1ff;
      }
      .mode-pill:hover{ background:#f5fbff; }

      /* 채팅 컨테이너 (파스텔 하늘 배경) */
      .chat-wrap{
        background:#eaf6ff; border:1px solid #cfe7ff; border-radius:18px;
        padding:10px 10px 8px; margin-top:10px;
      }
      .chat-box{
        min-height:240px; max-height:54vh; overflow-y:auto; padding:6px 6px 2px;
        display:flex; flex-direction:column; justify-content:flex-end; /* 아래 정렬 */
      }

      /* 챗봇 말풍선 */
      .row{ display:flex; margin:8px 0; gap:10px; }
      .row.user{ justify-content:flex-end; }   /* 학생 → 오른쪽 */
      .row.ai{   justify-content:flex-start; } /* AI   → 왼쪽  */
      .bubble{
        max-width:88%; padding:12px 14px; border-radius:16px; line-height:1.6; font-size:15px;
        box-shadow:0 1px 1px rgba(0,0,0,0.05); white-space:pre-wrap;
        border:1px solid #e0eaff; position:relative;
      }
      .bubble.user{
        background:#ffffff; color:#0a2540; border-color:#d9eaff; border-top-right-radius:8px;
      }
      .bubble.ai{
        background:#f7faff; color:#14121f; border-color:#e0eaff; border-top-left-radius:8px;
      }
      .row.user .bubble:after{
        content:""; position:absolute; right:-8px; top:10px;
        border-width:8px 0 8px 8px; border-style:solid;
        border-color:transparent transparent transparent #d9eaff;
      }
      .row.ai .bubble:before{
        content:""; position:absolute; left:-8px; top:10px;
        border-width:8px 8px 8px 0; border-style:solid;
        border-color:transparent #e0eaff transparent transparent;
      }
    </style>
    """, unsafe_allow_html=True)

def _llm_callable_ok() -> bool:
    try:
        return callable((_llm or {}).get("call_with_fallback"))
    except Exception:
        return False

def _render_llm_status_minimal():
    ok = _llm_callable_ok()
    html = '<span class="status-btn green">🟢 준비완료</span>' if ok else \
           '<span class="status-btn yellow">🟡 준비중</span>'
    st.markdown(html, unsafe_allow_html=True)

def _render_mode_controls_pills() -> str:
    """파스텔 하늘색 Pill UI로 모드 강조(세그먼트 대신)."""
    _inject_chat_styles_once()
    ss = st.session_state
    cfg = _sanitize_modes_cfg(_load_modes_cfg())
    cur = ss.get("qa_mode_radio") or (cfg.get("default") or "문법")
    st.markdown("#### 질문 모드 선택")
    c1, c2, c3 = st.columns(3, gap="small")
    def pill(col, mode, icon_label):
        with col:
            if cur == mode:
                st.markdown(f'<div class="mode-zone"><div class="mode-pill active">{icon_label}</div></div>',
                            unsafe_allow_html=True)
            else:
                if st.button(icon_label, key=f"mode_btn_{mode}", use_container_width=True):
                    ss["qa_mode_radio"] = mode; st.rerun()
    pill(c1, "문법", "🧩 어법")
    pill(c2, "문장", "🧱 문장")
    pill(c3, "지문", "📖 지문")
    if cur not in ["문법","문장","지문"]:
        cur = cfg.get("default") or "문법"
    ss["qa_mode_radio"] = cur
    return cur

def _htmlize_text(s: str) -> str:
    import html, re
    t = html.escape(s or "")
    t = t.replace("\n", "<br/>")
    t = re.sub(r"  ", "&nbsp;&nbsp;", t)
    return t

def _render_chat_log(messages: list[dict]):
    """파스텔 하늘색 영역에 챗봇 말풍선 렌더."""
    st.markdown('<div class="chat-wrap"><div class="chat-box">', unsafe_allow_html=True)
    for m in messages or []:
        role = m.get("role","ai"); text = _htmlize_text(m.get("text",""))
        klass = "user" if role == "user" else "ai"
        st.markdown(f'<div class="row {klass}"><div class="bubble {klass}">{text}</div></div>',
                    unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)

def _replace_assistant_text(aid: str, new_text: str):
    ss = st.session_state
    for m in ss.get("chat", []):
        if m.get("id") == aid and m.get("role") == "assistant":
            m["text"] = new_text
            return True
    return False

# ──────────────────────────────────────────────────────────────────────────────
# [10B] 로직(가변): 입력 → 즉시 말풍선 → 자동 재실행 → LLM 호출/치환
def _render_chat_panel():
    import time, inspect
    ss = st.session_state
    if "chat" not in ss:
        ss["chat"] = []

    # 상단 상태/모드
    _render_llm_status_minimal()
    cur = _render_mode_controls_pills()

    # 현재까지 대화 로그 먼저 그림(언제나 보이도록)
    _render_chat_log(ss["chat"])

    # 새 입력(엔터/화살표 자동)
    user_q = st.chat_input("예) 분사구문이 뭐예요?  예) 이 문장 구조 분석해줘")

    # 1단계: 내 말풍선 → '답변 준비중…' 말풍선 추가 후 'show' 단계로 전환
    if user_q and user_q.strip():
        uid = f"u{int(time.time()*1000)}"
        aid = f"a{uid}"  # 페어링 ID
        ss["chat"].append({"id": uid, "role":"user", "text": user_q.strip()})
        ss["chat"].append({"id": aid, "role":"assistant", "text": "답변 준비중…"})
        ss["_pending_call"] = {
            "q": user_q.strip(),
            "mode_key": cur,
            "mode_token": _LLM_TOKEN.get(cur, "문법설명"),
            "aid": aid,
        }
        ss["_llm_phase"] = "show"
        st.rerun()

    # 1차 런: 화면을 먼저 그린 뒤 짧은 지연 후 자동 재실행 → 2차 런에서 LLM 호출
    if ss.get("_pending_call") and ss.get("_llm_phase") == "show":
        st.markdown("<script>setTimeout(()=>window.location.reload(),120);</script>",
                    unsafe_allow_html=True)
        ss["_llm_phase"] = "call"
        return

    # 2차 런: LLM 호출 → 같은 말풍선 텍스트 교체
    pending = ss.get("_pending_call")
    if pending and ss.get("_llm_phase") == "call":
        try:
            q   = pending["q"]; mode_token = pending["mode_token"]; aid = pending["aid"]; mkey = pending["mode_key"]
            # prompts.yaml(Drive) → 실패 시 폴백 시스템 프롬프트
            build_prompt = (_prompt or {}).get("build_prompt")
            DEF_SYS = ("너는 한국의 영어학원 원장처럼 따뜻하고 명확하게 설명한다. "
                       "질문과 선택된 모드에 직접 관련된 내용만 한국어로 간결하게 답한다. "
                       "예문과 단계별 설명을 포함하되 탈선 금지.")
            if callable(build_prompt):
                try:
                    parts = build_prompt(mode_token, q) or {}
                    system_prompt = parts.get("system") or DEF_SYS
                    prompt        = parts.get("user")   or f"[모드:{mode_token}]\n{q}"
                except Exception:
                    system_prompt, prompt = DEF_SYS, f"[모드:{mode_token}]\n{q}"
            else:
                system_prompt, prompt = DEF_SYS, f"[모드:{mode_token}]\n{q}"

            call = (_llm or {}).get("call_with_fallback") if "_llm" in globals() else None
            if not callable(call):
                raise RuntimeError("LLM 어댑터(call_with_fallback)를 사용할 수 없습니다.")

            sig = inspect.signature(call); params = sig.parameters.keys(); kwargs = {}
            if "messages" in params:
                kwargs["messages"] = [
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":prompt}
                ]
            else:
                if "prompt" in params: kwargs["prompt"] = prompt
                elif "user_prompt" in params: kwargs["user_prompt"] = prompt
                if "system_prompt" in params: kwargs["system_prompt"] = system_prompt
                elif "system" in params: kwargs["system"] = system_prompt
            if "mode_token" in params: kwargs["mode_token"] = mode_token
            elif "mode" in params: kwargs["mode"] = mode_token
            if "timeout_s" in params: kwargs["timeout_s"] = 90
            elif "timeout" in params: kwargs["timeout"] = 90
            if "extra" in params: kwargs["extra"] = {"question": q, "mode_key": mkey}

            with st.spinner("답변 생성 중..."):
                res = call(**kwargs)
                text = res.get("text") if isinstance(res, dict) else str(res)
                if not text: text = "(응답이 비어있어요)"
                _replace_assistant_text(aid, text)
        except Exception as e:
            _replace_assistant_text(pending.get("aid",""), f"(오류) {type(e).__name__}: {e}")
            _errlog(f"LLM 예외: {e}", where="[qa_llm]", exc=e)
        finally:
            ss["_pending_call"] = None
            ss["_llm_phase"] = None
            st.rerun()
# [10] 학생 UI (Stable Chatbot v2) ────────────────────────────────────────────  # [10] END



# [11] 본문 렌더 ===============================================================
def _render_body() -> None:
    if st is None:
        return
    _header()            # ✅ 인라인 로그인만 사용
    _auto_start_once()
    if _is_admin_view():
        _render_admin_panels()
    st.markdown("## 질문은 천재들의 공부 방법이다.")
    _render_chat_panel()

# [12] main ===================================================================
def main():
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()

if __name__ == "__main__":
    main()
# =============================== [END] =======================================
