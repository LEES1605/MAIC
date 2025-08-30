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
# [10A] 학생 UI (Stable): 파스텔 하늘색 말풍선·작은 모드버튼·상단 우측 관리자 아이콘  # [10A] START
def _inject_chat_styles_once():
    if st.session_state.get("_chat_styles_injected"): return
    st.session_state["_chat_styles_injected"] = True
    st.markdown("""
    <style>
      /* 상태 배지 */
      .status-btn{display:inline-block;padding:6px 10px;border-radius:14px;
        font-size:12px;font-weight:700;color:#111;border:1px solid transparent}
      .status-btn.green{background:#daf5cb;border-color:#bfe5ac}
      .status-btn.yellow{background:#fff3bf;border-color:#ffe08a}

      /* 상단 우측 관리자 아이콘 */
      .topbar{display:flex;align-items:center;justify-content:flex-end;margin-top:-8px}
      .icon-btn{border:1px solid #e6e6e6;border-radius:10px;background:#fff;padding:6px 8px;
        cursor:pointer;font-size:16px}
      .icon-btn:hover{background:#f5f5f5}

      /* 모드: 수평 라디오(작게·균일, 아이콘 없음) */
      div[data-testid="stRadio"] > div[role="radiogroup"]{display:flex;gap:10px;flex-wrap:wrap}
      div[data-testid="stRadio"] [role="radio"]{
        border:2px solid #bcdcff;border-radius:12px;padding:6px 12px;background:#fff;color:#0a2540;
        font-weight:700;font-size:14px;line-height:1;
      }
      div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{
        background:#eaf6ff;border-color:#9fd1ff;color:#0a2540;   /* 선택: 색만 변경 */
      }
      div[data-testid="stRadio"] svg{display:none!important}

      /* 채팅 컨테이너(파스텔 하늘) */
      .chat-wrap{background:#eaf6ff !important;border:1px solid #cfe7ff !important;border-radius:18px;
                 padding:10px 10px 8px;margin-top:10px}
      .chat-box{min-height:240px;max-height:54vh;overflow-y:auto;padding:6px 6px 2px}

      /* 커스텀 말풍선 — 이 스타일이 st.chat_message 내부에서 적용됨 */
      .row{display:flex;margin:8px 0}
      .row.user{justify-content:flex-end}
      .row.ai{justify-content:flex-start}
      .bubble{
        max-width:88%;padding:12px 14px;border-radius:16px;line-height:1.6;font-size:15px;
        box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;position:relative;border:1px solid #e0eaff;
      }
      .bubble.user{                      /* ← 질문 = 파스텔 하늘색 */
        background:#dff0ff !important; color:#0a2540!important; border-color:#bfe2ff !important; border-top-right-radius:8px;
      }
      .bubble.ai{                         /* ← 답변 = 흰색 */
        background:#ffffff; color:#14121f; border-top-left-radius:8px;
      }
    </style>
    """, unsafe_allow_html=True)

_MODE_KEYS = ["문법","문장","지문"]

def _llm_callable_ok():
    try: return callable((_llm or {}).get("call_with_fallback"))
    except Exception: return False

def _render_llm_status_minimal():
    ok = _llm_callable_ok()
    st.markdown(
        f'<span class="status-btn {"green" if ok else "yellow"}">'
        f'{"🟢 준비완료" if ok else "🟡 준비중"}</span>', unsafe_allow_html=True)

def _render_top_right_admin_icon():
    cols = st.columns([1,1,1,1,1,1,1,1,1,1])  # 오른쪽 정렬용 간단 해크
    with cols[-1]:
        clicked = st.button("⚙️", key="admin_icon", help="관리자", use_container_width=False)
        if clicked:
            st.session_state["admin_panel_open"] = not st.session_state.get("admin_panel_open", False)

def _render_mode_controls_pills()->str:
    _inject_chat_styles_once()
    ss=st.session_state
    cur=ss.get("qa_mode_radio") or "문법"
    labels=["어법","문장","지문"]; map_to={"어법":"문법","문장":"문장","지문":"지문"}
    idx = labels.index({"문법":"어법","문장":"문장","지문":"지문"}[cur])
    sel = st.radio("질문 모드 선택", options=labels, index=idx, horizontal=True)
    new_key = map_to[sel]
    if new_key != cur: ss["qa_mode_radio"]=new_key; st.rerun()
    return ss.get("qa_mode_radio", new_key)

def _esc_html(s:str)->str:
    import html, re
    t = html.escape(s or "")
    t = t.replace("\n","<br/>")
    t = re.sub(r"  ","&nbsp;&nbsp;", t)
    return t

def _render_bubble(role:str, text:str):
    klass = "user" if role=="user" else "ai"
    st.markdown(f'<div class="row {klass}"><div class="bubble {klass}">{_esc_html(text)}</div></div>',
                unsafe_allow_html=True)

def _render_chat_log(messages:list[dict]):
    st.markdown('<div class="chat-wrap"><div class="chat-box">', unsafe_allow_html=True)
    for m in messages or []:
        with st.chat_message("user" if m.get("role")=="user" else "assistant"):
            _render_bubble(m.get("role","assistant"), m.get("text",""))
    st.markdown('</div></div>', unsafe_allow_html=True)

def _replace_assistant_text(aid:str,new_text:str):
    ss=st.session_state
    for m in ss.get("chat",[]):
        if m.get("id")==aid and m.get("role")=="assistant":
            m["text"]=new_text; return True
    return False
# [10A] END

# [10B] 학생 로직 (Streaming v1.4, GitHub prompts + 근거 우선순위 + 안내문)  # [10B] START
def _render_chat_panel():
    import time, inspect, base64, json, urllib.request
    try:
        import yaml
    except Exception:
        yaml = None  # PyYAML 없을 경우 GitHub YAML 파싱은 스킵됨 → Fallback 사용

    ss = st.session_state
    if "chat" not in ss: ss["chat"] = []

    # ── 상단 UI(아이콘/상태/모드) ───────────────────────────────────────────────
    _render_top_right_admin_icon()
    # (선택) 관리자 패널: 10C를 쓰는 경우에만 안전 호출
    if "_render_admin_prompts_panel" in globals():
        try: _render_admin_prompts_panel()
        except Exception: pass

    _inject_chat_styles_once()
    _render_llm_status_minimal()
    cur_label = _render_mode_controls_pills()     # "문법" / "문장" / "지문"
    MODE_TOKEN = {"문법":"문법설명","문장":"문장구조분석","지문":"지문분석"}[cur_label]

    # ── 증거(컨텍스트) 수집: 당분간 세션에서 주입(없으면 빈 문자열) ───────────────
    ev_notes  = ss.get("__evidence_class_notes", "")      # 1차: 수업자료(이유문법/깨알문법)
    ev_books  = ss.get("__evidence_grammar_books", "")    # 2차: 문법서 PDF 스니펫

    # ── GitHub prompts 로더 ────────────────────────────────────────────────────
    def _github_fetch_prompts_text():
        """GitHub Contents API로 prompts.yaml 텍스트 반환. 성공 시 캐시."""
        token  = st.secrets.get("GH_TOKEN")
        repo   = st.secrets.get("GH_REPO")
        branch = st.secrets.get("GH_BRANCH", "main")
        path   = st.secrets.get("GH_PROMPTS_PATH", "prompts.yaml")
        if not (token and repo and yaml):
            return None
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}",
                                                  "User-Agent": "maic-app"})
        try:
            with urllib.request.urlopen(req) as r:
                meta = json.loads(r.read().decode("utf-8"))
                content_b64 = meta.get("content") or ""
                text = base64.b64decode(content_b64.encode("utf-8")).decode("utf-8")
                ss["__gh_prompts_cache"] = {"sha": meta.get("sha"), "text": text}
                return text
        except Exception:
            return None

    def _build_prompt_from_github(mode_token: str, q: str, ev1: str, ev2: str):
        txt = _github_fetch_prompts_text()
        if not (txt and yaml): return None
        try:
            data = yaml.safe_load(txt) or {}
            node = (data.get("modes") or {}).get(mode_token)
            if not node: return None
            sys_p = node.get("system") if isinstance(node, dict) else None
            usr_p = node.get("user")   if isinstance(node, dict) else (node if isinstance(node, str) else None)
            if usr_p is None: return None
            # 플레이스홀더 치환
            usr_p = (usr_p
                     .replace("{QUESTION}", q)
                     .replace("{EVIDENCE_CLASS_NOTES}", ev1 or "")
                     .replace("{EVIDENCE_GRAMMAR_BOOKS}", ev2 or ""))
            return {"system": sys_p, "user": usr_p}
        except Exception:
            return None

    # ── Drive 모듈(있으면) ────────────────────────────────────────────────────
    def _build_prompt_from_drive(mode_token: str, q: str, ev1: str, ev2: str):
        _prompt_mod = _try_import("src.prompt_modes", ["build_prompt"]) or {}
        fn = _prompt_mod.get("build_prompt")
        if not callable(fn): return None
        try:
            parts = fn(mode_token, q) or {}
            sys_p = parts.get("system")
            usr_p = parts.get("user")
            if usr_p:
                usr_p = (usr_p
                         .replace("{QUESTION}", q)
                         .replace("{EVIDENCE_CLASS_NOTES}", ev1 or "")
                         .replace("{EVIDENCE_GRAMMAR_BOOKS}", ev2 or ""))
            return {"system": sys_p, "user": usr_p}
        except Exception:
            return None

    # ── Fallback(부드러운 안내 포함, 모드별 포맷 반영) ───────────────────────────
    def _fallback_prompts(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str):
        NOTICE = "안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요."
        BASE = "너는 한국의 영어학원 원장처럼 따뜻하고 명확하게 설명한다. 모든 출력은 한국어로 간결하게."
        if mode_token == "문법설명":
            # 요청 반영: 예문 1개, 흔한 오류 삭제, 출처 3종
            sys_p = BASE + " 주제에서 벗어난 장황한 배경설명은 금지한다."
            lines = []
            # 1·2차 근거가 모두 없으면 안내문으로 시작
            if not ev1 and not ev2:
                lines.append(NOTICE)
            lines += [
                "1) 한 줄 핵심",
                "2) 이미지/비유 (짧게)",
                "3) 핵심 규칙 3–5개 (• bullet)",
                "4) 예문 1개(+한국어 해석)",
                "5) 한 문장 리마인드",
                "6) 출처 1개: [출처: 이유문법] / [출처: 책제목(…)] / [출처: AI자체지식]",
            ]
            usr_p = f"[질문]\n{q}\n\n[작성 지침]\n- 형식을 지켜라.\n" + "\n".join(f"- {x}" for x in lines)
        elif mode_token == "문장구조분석":
            sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
            usr_p = (
                "[출력 형식]\n"
                "0) 모호성 점검\n"
                "1) 괄호 규칙 요약\n"
                "2) 핵심 골격 S–V–O–C–M 한 줄 개요\n"
                "3) 성분 식별: 표/리스트\n"
                "4) 구조/구문: 수식 관계·It-cleft·가주어/진주어·생략 복원 등 단계적 설명\n"
                "5) 핵심 포인트 2–3개\n"
                "6) 출처(보수): [규칙/자료/수업노트 등 ‘출처 유형’만]\n\n"
                f"[문장]\n{q}"
            )
        else:  # 지문분석
            sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
            usr_p = (
                "[출력 형식]\n"
                "1) 한 줄 요지(명사구)\n"
                "2) 구조 요약: (서론–본론–결론) 또는 단락별 핵심 문장\n"
                "3) 핵심어/표현 3–6개 + 이유\n"
                "4) 문제풀이 힌트(있다면)\n\n"
                f"[지문/질문]\n{q}"
            )
        ss["__prompt_source"] = "Fallback"
        return sys_p, usr_p

    # ── 최종 프롬프트 결합 로직: GitHub → Drive → Fallback + 안내문 지시 ──────────
    def _resolve_prompts(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str):
        # 1) GitHub
        gh = _build_prompt_from_github(mode_token, q, ev1, ev2)
        if gh and (gh.get("system") or gh.get("user")):
            ss["__prompt_source"] = "GitHub"
            sys_p = gh.get("system") or ""
            usr_p = gh.get("user") or f"[모드:{mode_token}]\n{q}"
            # 1·2차 근거가 비어 있으면 '안내문으로 시작' 지시를 추가(문법설명일 때 우선)
            if mode_token == "문법설명" and not ev1 and not ev2:
                usr_p += "\n\n[지시]\n- 답변 첫 줄을 다음 문장으로 시작: '안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요.'"
            return sys_p, usr_p

        # 2) Drive
        dv = _build_prompt_from_drive(mode_token, q, ev1, ev2)
        if dv and (dv.get("system") or dv.get("user")):
            ss["__prompt_source"] = "Drive"
            sys_p = dv.get("system") or ""
            usr_p = dv.get("user") or f"[모드:{mode_token}]\n{q}"
            if mode_token == "문법설명" and not ev1 and not ev2:
                usr_p += "\n\n[지시]\n- 답변 첫 줄을 다음 문장으로 시작: '안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요.'"
            return sys_p, usr_p

        # 3) Fallback
        return _fallback_prompts(mode_token, q, ev1, ev2, cur_label)

    # ── 입력 & 렌더(항상 chat-wrap 내부에서 유지) ────────────────────────────────
    user_q = st.chat_input("예) 분사구문이 뭐예요?  예) 이 문장 구조 분석해줘")
    qtxt = user_q.strip() if user_q and user_q.strip() else None
    do_stream = qtxt is not None
    if do_stream:
        ts = int(time.time()*1000); uid, aid = f"u{ts}", f"a{ts}"
        ss["chat"].append({"id": uid, "role": "user", "text": qtxt})

    with st.container():
        st.markdown('<div class="chat-wrap"><div class="chat-box">', unsafe_allow_html=True)
        # 과거 로그
        for m in ss["chat"]:
            _render_bubble(m.get("role","assistant"), m.get("text",""))

        text_final = ""
        if do_stream:
            # 준비중
            ph = st.empty()
            ph.markdown(
                f'<div class="row ai"><div class="bubble ai">{_esc_html("답변 준비중…")}</div></div>',
                unsafe_allow_html=True
            )
            # 프롬프트 해석
            system_prompt, user_prompt = _resolve_prompts(MODE_TOKEN, qtxt, ev_notes, ev_books, cur_label)

            # LLM 호출(스트리밍 지원 자동 탐지)
            call = (_llm or {}).get("call_with_fallback") if "_llm" in globals() else None
            if not callable(call):
                text_final = "(오류) LLM 어댑터를 사용할 수 없습니다."
                ph.markdown(f'<div class="row ai"><div class="bubble ai">{_esc_html(text_final)}</div></div>',
                            unsafe_allow_html=True)
            else:
                sig = inspect.signature(call); params = sig.parameters.keys(); kwargs = {}
                if "messages" in params:
                    kwargs["messages"] = [
                        {"role":"system","content":system_prompt or ""},
                        {"role":"user","content":user_prompt},
                    ]
                else:
                    if "prompt" in params: kwargs["prompt"] = user_prompt
                    elif "user_prompt" in params: kwargs["user_prompt"] = user_prompt
                    if "system_prompt" in params: kwargs["system_prompt"] = (system_prompt or "")
                    elif "system" in params: kwargs["system"] = (system_prompt or "")

                if "mode_token" in params: kwargs["mode_token"] = MODE_TOKEN
                elif "mode" in params:     kwargs["mode"] = MODE_TOKEN
                if "temperature" in params: kwargs["temperature"] = 0.2
                elif "temp" in params:      kwargs["temp"] = 0.2
                if "timeout_s" in params:   kwargs["timeout_s"] = 90
                elif "timeout" in params:   kwargs["timeout"] = 90
                if "extra" in params:       kwargs["extra"] = {"question": qtxt, "mode_key": cur_label}

                acc = ""
                def _emit(piece: str):
                    nonlocal acc
                    acc += str(piece)
                    ph.markdown(
                        f'<div class="row ai"><div class="bubble ai">{_esc_html(acc)}</div></div>',
                        unsafe_allow_html=True
                    )

                supports_stream = ("stream" in params) or ("on_token" in params) or \
                                  ("on_delta" in params) or ("yield_text" in params)
                try:
                    if supports_stream:
                        if "stream" in params:   kwargs["stream"] = True
                        if "on_token" in params: kwargs["on_token"] = _emit
                        if "on_delta" in params: kwargs["on_delta"] = _emit
                        if "yield_text" in params: kwargs["yield_text"] = _emit
                        res = call(**kwargs)
                        text_final = (res.get("text") if isinstance(res, dict) else acc) or acc
                    else:
                        res  = call(**kwargs)
                        text_final = res.get("text") if isinstance(res, dict) else str(res)
                        if not text_final: text_final = "(응답이 비어있어요)"
                        ph.markdown(
                            f'<div class="row ai"><div class="bubble ai">{_esc_html(text_final)}</div></div>',
                            unsafe_allow_html=True
                        )
                except Exception as e:
                    text_final = f"(오류) {type(e).__name__}: {e}"
                    ph.markdown(
                        f'<div class="row ai"><div class="bubble ai">{_esc_html(text_final)}</div></div>',
                        unsafe_allow_html=True
                    )
                    _errlog(f"LLM 예외: {e}", where="[qa_llm]", exc=e)

        st.markdown('</div></div>', unsafe_allow_html=True)

    if do_stream:
        ss["chat"].append({"id": f"a{int(time.time()*1000)}", "role": "assistant", "text": text_final})
        st.rerun()
# [10B] 학생 로직 (Streaming v1.4, GitHub prompts + 근거 우선순위 + 안내문)  # [10B] END

# [10C] 관리자: 모드별 prompts 편집 → GitHub 업로드(Contents API, 선택)  # [10C] START
def _render_admin_prompts_panel():
    if not st.session_state.get("admin_panel_open"): return
    st.subheader("관리자 · prompts 편집")
    tabs = st.tabs(["어법(문법)", "문장", "지문"])

    # 현재 캐시된 값 불러오기(없으면 빈값)
    cache = st.session_state.get("__admin_prompts_cache") or {"문법":"", "문장":"", "지문":""}

    with tabs[0]:
        cache["문법"] = st.text_area("어법 프롬프트", value=cache.get("문법",""), height=200)
    with tabs[1]:
        cache["문장"] = st.text_area("문장 프롬프트", value=cache.get("문장",""), height=200)
    with tabs[2]:
        cache["지문"] = st.text_area("지문 프롬프트", value=cache.get("지문",""), height=200)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 로컬 저장", use_container_width=True):
            import yaml
            from pathlib import Path
            y = {"modes":{"문법설명":cache["문법"],"문장구조분석":cache["문장"],"지문분석":cache["지문"]}}
            p = (PERSIST_DIR / "prompts.yaml"); p.write_text(yaml.safe_dump(y, allow_unicode=True), encoding="utf-8")
            st.session_state["__admin_prompts_cache"] = cache
            st.success(f"로컬에 저장됨: {p}")

    with col2:
        if st.button("⬆️ GitHub에 업로드", use_container_width=True):
            import base64, json, urllib.request
            token = st.secrets.get("GH_TOKEN"); repo = st.secrets.get("GH_REPO"); branch = st.secrets.get("GH_BRANCH","main")
            if not (token and repo):
                st.error("GH_TOKEN / GH_REPO (owner/repo) 가 필요합니다.")
            else:
                try:
                    # 1) 현재 SHA 조회
                    path = "prompts.yaml"
                    url_get = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
                    req = urllib.request.Request(url_get, headers={"Authorization": f"token {token}", "User-Agent": "maic-app"})
                    try:
                        with urllib.request.urlopen(req) as r:
                            meta = json.loads(r.read().decode("utf-8"))
                            sha = meta.get("sha")
                    except Exception:
                        sha = None  # 파일이 없을 수도 있음(첫 업로드)

                    # 2) 본문 생성
                    y = {"modes":{"문법설명":cache["문법"],"문장구조분석":cache["문장"],"지문분석":cache["지문"]}}
                    content_b64 = base64.b64encode(json.dumps(y, ensure_ascii=False).encode("utf-8")).decode("utf-8")

                    # 3) PUT (생성/갱신)
                    url_put = f"https://api.github.com/repos/{repo}/contents/{path}"
                    body = json.dumps({
                        "message": "chore: update prompts.yaml from admin panel",
                        "content": content_b64,
                        "branch": branch,
                        **({"sha": sha} if sha else {})
                    }).encode("utf-8")
                    req2 = urllib.request.Request(url_put, data=body, method="PUT",
                            headers={"Authorization": f"token {token}","User-Agent":"maic-app","Content-Type":"application/json"})
                    with urllib.request.urlopen(req2) as r2:
                        _ = r2.read()
                    st.success("GitHub 업로드 완료 (contents API)")
                    st.session_state["__prompt_source"] = "GitHub"  # 소스 표기
                except Exception as e:
                    st.error(f"업로드 실패: {type(e).__name__}: {e}")
# [10C] END


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
