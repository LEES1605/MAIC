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

# [07] 두뇌 수동 복원 CTA(관리자 전용) =========================================
def _manual_restore_cta():
    if st is None or not _is_admin_view() or _is_brain_ready():
        return
    with st.container(border=True):
        c1, c2 = st.columns([0.65, 0.35])
        with c1:
            st.info("두뇌가 아직 준비되지 않았어요. 최신 GitHub Releases에서 복원할 수 있어요.")
        with c2:
            if st.button("최신 릴리스에서 복원", type="primary", use_container_width=True):
                try:
                    ok = bool(_gh.get("restore_latest") and _gh["restore_latest"](dest_dir=PERSIST_DIR))
                    if ok:
                        _mark_ready()
                        st.success("복원 완료! 잠시 후 새로고침됩니다.")
                        st.rerun()
                    else:
                        st.error("복원 실패: Releases의 manifest/chunks를 확인하세요.")
                except Exception as e:
                    _errlog(f"manual restore failed: {e}", where="[manual_restore]", exc=e)
                    st.error(f"예외: {type(e).__name__}: {e}")

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


# [10] 학생 UI: 모드 버튼 + 파스텔 채팅(지연해결/생각중/말풍선 꼬리/간격) ==========
def _inject_minimal_styles_once():
    if st.session_state.get("_minimal_styles_injected"):
        return
    st.session_state["_minimal_styles_injected"] = True
    st.markdown("""
    <style>
      .seg-zone .stButton>button{
        width:100%; border:2px solid #bcdcff; border-radius:16px;
        background:#fff; color:#111; font-weight:700; padding:10px 12px;
      }
      .seg-zone .stButton>button:hover{ background:#f5fbff; }
      .seg-zone .stButton>button:disabled{
        background:#eeeeee !important; color:#888 !important; border-color:#ddd !important;
      }
      .chat-box{ border:2px solid #bcdcff; background:#e6f7ff; padding:16px; border-radius:16px; min-height:360px; }
      .bubble{ position:relative; max-width:92%; padding:10px 12px; border-radius:14px; margin:10px 0; line-height:1.55; font-size:1rem; }
      .user{ background:#fff7cc; margin-left:auto; }    /* 학생: 연노랑 */
      .ai{   background:#d9f7d9;  margin-right:auto; }  /* AI: 연초록 */
      .row{ display:flex; }
      .row.user{ justify-content:flex-end; }
      .row.ai{   justify-content:flex-start; }
      /* 꼬리 */
      .bubble.user:after{
        content:""; position:absolute; right:-8px; top:14px; border-width:8px 0 8px 8px; border-style:solid;
        border-color:transparent transparent transparent #fff7cc;
      }
      .bubble.ai:after{
        content:""; position:absolute; left:-8px; top:14px; border-width:8px 8px 8px 0; border-style:solid;
        border-color:transparent #d9f7d9 transparent transparent;
      }
      /* chat_input 테두리/배경 */
      div[data-testid="stChatInput"]{
        border:2px solid #bcdcff !important;
        background:#e6f7ff !important;
        border-radius:16px !important;
        padding:8px 10px !important;
      }
    </style>
    """, unsafe_allow_html=True)

_MODE_KEYS = ["문법", "문장", "지문"]
_LABELS    = {"문법":"어법","문장":"문장","지문":"지문"}
_LLM_TOKEN = {"문법":"문법설명","문장":"문장구조분석","지문":"지문분석"}

def _render_mode_controls_minimal(*, admin: bool) -> str:
    _inject_minimal_styles_once()
    ss = st.session_state
    cfg = _sanitize_modes_cfg(_load_modes_cfg())
    allowed: set[str] = set(cfg["allowed"])
    default_mode = cfg["default"]
    cur = ss.get("qa_mode_radio") or default_mode
    if (not admin) and (cur not in allowed) and allowed:
        cur = default_mode; ss["qa_mode_radio"] = cur

    with st.container():
        st.markdown('<div class="seg-zone"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        for col, key in zip([c1, c2, c3], _MODE_KEYS):
            disabled = False if admin else (key not in allowed)
            with col:
                btn = st.button(_LABELS[key], key=f"mode_btn_{key}", disabled=disabled,
                                type=("primary" if cur == key else "secondary"))
                if btn and (admin or (key in allowed)):
                    ss["qa_mode_radio"] = key; cur = key; st.rerun()
    return cur

def _llm_call(prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    if _llm.get("call_with_fallback"):
        return _llm["call_with_fallback"](prompt=prompt, system=system,
                                          primary="gemini", secondary="openai",
                                          temperature=0.3, max_tokens=800)
    return {"ok": False, "error": "LLM providers 모듈 미탑재"}

def _render_chat_panel() -> None:
    if st is None: return
    ss = st.session_state
    ss.setdefault("chat", []); ss.setdefault("_chat_next_id", 1)

    ready = _is_brain_ready(); admin = _is_admin_view()

    with st.container(border=True):
        c1, c2 = st.columns([0.65, 0.35])
        with c1: st.markdown(f"**{'🟢 준비완료' if ready else '🟡 준비중'}**")
        with c2: _ = _render_mode_controls_minimal(admin=admin)

    if not ready:
        _manual_restore_cta()

    # ✅ 1) 입력 먼저 처리(같은 프레임에서 '생각중'→응답까지 반영)
    user_q = st.chat_input("질문을 입력하세요")
    if user_q:
        uid = ss["_chat_next_id"]; ss["_chat_next_id"] += 1
        ss["chat"].append({"id": uid, "role":"user", "text": user_q})

        # '생각중…' 플레이스홀더
        aid = ss["_chat_next_id"]; ss["_chat_next_id"] += 1
        thinking_idx = len(ss["chat"])
        ss["chat"].append({"id": aid, "role":"assistant", "text": "생각중…"})

        cfg = _sanitize_modes_cfg(_load_modes_cfg())
        cur = ss.get("qa_mode_radio") or cfg["default"]
        system_prompt = "너는 한국의 영어학원 원장처럼, 따뜻하고 명확하게 설명한다."
        prompt = f"[모드:{_LLM_TOKEN.get(cur,'문법설명')}]\n{user_q}"

        try:
            with st.spinner("답변 생성 중..."):
                res = _llm_call(prompt, system_prompt)
            text = (res.get("text") or f"생성 실패: {res.get('error')}").strip() if res.get("ok") \
                   else (res.get("error") or "생성 실패")
            ss["chat"][thinking_idx] = {"id": aid, "role":"assistant", "text": text, "provider": res.get("provider")}
        except Exception as e:
            err_txt = f"예외: {type(e).__name__}: {e}"
            ss["chat"][thinking_idx] = {"id": aid, "role":"assistant", "text": err_txt}
            _errlog(f"LLM 예외: {e}", where="[qa_llm]", exc=e)

        # 최신 상태가 즉시 보이도록 한 프레임 갱신
        st.rerun()

    # ✅ 2) (입력 처리 후) 대화 로그 렌더 → 같은 런에서 최신 상태가 보임
    st.markdown('<div class="chat-box">', unsafe_allow_html=True)
    for m in ss["chat"]:
        klass = "user" if m["role"] == "user" else "ai"
        st.markdown(f'<div class="row {klass}"><div class="bubble {klass}">{m["text"]}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

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
