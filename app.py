# ==== [01] future import =====================================================
from __future__ import annotations

# ==== [02] bootstrap & imports ==============================================
import os, io, json, time, traceback, importlib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except Exception:
    st = None  # 로컬/테스트 환경 방어

# ==== [03] secrets → env 승격 & 서버 안정 옵션 ===============================
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
        "APP_MODE", "AUTO_START_MODE", "LOCK_MODE_FOR_STUDENTS", "APP_ADMIN_PASSWORD",
    ]
    for k in keys:
        v = _from_secrets(k)
        if v and not os.getenv(k):
            os.environ[k] = str(v)
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")

_bootstrap_env()

# ==== [04] 경로/상태 & 에러로그 ==============================================
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
    if not p.exists(): return False
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
    try: (PERSIST_DIR / ".ready").write_text("ok", encoding="utf-8")
    except Exception: pass

def _errlog(msg: str, *, where: str = "", exc: BaseException | None = None) -> None:
    if st is None: return
    ss = st.session_state
    ss.setdefault("_error_log", [])
    ss["_error_log"].append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "where": where, "msg": str(msg),
        "trace": traceback.format_exc() if exc else "",
    })

def _errlog_text() -> str:
    if st is None: return ""
    out = io.StringIO()
    for i, r in enumerate(st.session_state.get("_error_log", []), 1):
        out.write(f"[{i}] {r['ts']} {r.get('where','')}\n{r['msg']}\n")
        if r.get("trace"): out.write(r["trace"] + "\n")
        out.write("-"*60 + "\n")
    return out.getvalue()

# ==== [05] 동적 임포트 바인딩 ===============================================
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
_ui_orch  = _try_import("src.ui_orchestrator", ["render_index_orchestrator_panel"])
_gh       = _try_import("src.backup.github_release", ["restore_latest"])
_rag      = _try_import("src.rag.index_build", ["build_index_with_checkpoint"])
_llm      = _try_import("src.llm.providers", ["call_with_fallback"])

# ==== [06] 페이지 설정 & 헤더 + 로그인 토글 =================================
if st:
    st.set_page_config(page_title="LEES AI Teacher", layout="wide")  # (5)

def _is_admin_view() -> bool:
    env = (os.getenv("APP_MODE") or _from_secrets("APP_MODE","student") or "student").lower()
    return bool(env == "admin" or (st and (st.session_state.get("is_admin") or st.session_state.get("admin_mode"))))

def _toggle_login_flag():
    st.session_state["_show_admin_login"] = not st.session_state.get("_show_admin_login", False)

def _header():
    if st is None: return
    left, right = st.columns([0.8, 0.2])
    with left:
        st.markdown("### LEES AI Teacher")     # (5)
        # caption 제거 (6)
    with right:
        if _is_admin_view():
            status = "🟢 준비완료" if _is_brain_ready() else "🟡 준비중"   # (3)
            st.markdown(f"**{status}**")
            st.button("관리자", on_click=_toggle_login_flag, use_container_width=True)  # 관리자일 때만 노출
        else:
            # (2) 학생 화면: 상태 텍스트 + '관리자' 버튼 모두 숨김
            st.empty()
    if _import_warns:
        with st.expander("임포트 경고", expanded=False):
            for w in _import_warns: st.code(w, language="text")
    st.divider()



def _login_panel_if_needed():
    """학생 화면에서도 열 수 있는 고정형 로그인 패널(헤더 아래)."""
    if st is None or _is_admin_view() is True:
        return
    if not st.session_state.get("_show_admin_login", False):
        return
    pwd_set = os.getenv("APP_ADMIN_PASSWORD") or _from_secrets("APP_ADMIN_PASSWORD","0000") or "0000"
    with st.container(border=True):
     요. 최신 GitHub Releases에서 복원할 수 있어요.")
        with c2:
            if st.button("최신 릴리스에서 복원", type="primary", use_container_width=True):
                try:
                    ok = bool(_gh["restore_latest"](dest_dir=PERSIST_DIR))
                    if ok:
                        _mark_ready()
                        st.success("복원 완료! 잠시 후 새로고침됩니다.")
                        st.rerun()
                    else:
                        st.error("복원 실패: Releases의 manifest/chunks를 확인하세요.")
                except Exception as e:
                    _errlog(f"manual restore failed: {e}", where="[manual_restore]", exc=e)
                    st.error(f"예외: {type(e).__name__}: {e}")

# ==== [08] 설명 모드 허용/기본값: 영속 설정 ==================================
def _modes_cfg_path() -> Path:
    return PERSIST_DIR / "explain_modes.json"

def _load_modes_cfg() -> Dict[str, Any]:
    try:
        p = _modes_cfg_path()
        if not p.exists():
            return {"allowed": ["문법","문장","지문"], "default": "문법"}
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {"allowed": ["문법","문장","지문"], "default": "문법"}

def _save_modes_cfg(cfg: Dict[str, Any]) -> None:
    try:
        p = _modes_cfg_path()
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _errlog(f"save modes cfg failed: {e}", where="[modes_save]", exc=e)

def _sanitize_modes_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    modes = ["문법","문장","지문"]
    allowed = [m for m in (cfg.get("allowed") or []) if m in modes]
    if not allowed:
        allowed = []  # 전부 끌 수도 있게 허용
    default = cfg.get("default") or "문법"
    if default not in modes:
        default = "문법"
    # default가 허용되지 않았어도 유지(학생은 선택 불가 → 버튼 회색)
    return {"allowed": allowed, "default": default}

# ==== [09] 관리자 패널 =======================================================
def _render_admin_panels() -> None:
    if st is None or not _is_admin_view(): return
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
    c1,c2,c3 = st.columns(3)
    with c1:  g = st.checkbox("문법",      value=("문법" in a))
    with c2:  s = st.checkbox("문장",  value=("문장" in a))
    with c3:  p = st.checkbox("지문",      value=("지문" in a))

    # 기본 모드 선택(관리자용) — 전체 모드 중 선택
    base_modes = ["문법","문장","지문"]
    default_sel = st.selectbox("기본 모드(학생 초기값)", base_modes, index=base_modes.index(cfg["default"]))

    if st.button("허용 설정 저장", type="primary"):
        new_cfg = _sanitize_modes_cfg({"allowed": [m for m, v in [
            ("문법", g), ("문장", s), ("지문", p)
        ] if v], "default": default_sel})
        _save_modes_cfg(new_cfg)
        st.success("저장 완료")
        st.rerun()

    if _ui_admin.get("render_mode_radio_admin"):
        st.markdown("#### (관리자 전용) 미리보기용 모드 선택")
        _ui_admin["render_mode_radio_admin"]()

    with st.expander("오류 로그", expanded=False):
        txt = _errlog_text()
        st.text_area("최근 오류", value=txt, height=180)
        st.download_button("로그 다운로드", data=txt.encode("utf-8"), file_name="app_error_log.txt")

# ==== [10] 설명 모드: 미니멀 세그먼트 버튼(파스텔) + 커스텀 채팅 UI ==========
def _inject_minimal_styles_once():
    if st.session_state.get("_minimal_styles_injected"):
        return
    st.session_state["_minimal_styles_injected"] = True
    st.markdown("""
    <style>
      /* --- 세그먼트 버튼 --- */
      .seg-wrap { display:flex; gap:8px; justify-content:space-between; }
      .seg-btn {
        flex:1; text-align:center; padding:10px 12px;
        border:2px solid #bcdcff; border-radius:16px;
        background:#ffffff; color:#111; font-weight:600;
        text-decoration:none; user-select:none; display:block;
      }
      .seg-btn:hover { background:#f5fbff; }
      .seg-btn.selected {
        background:#a7d8ff;              /* 선택: 파스텔 하늘색 */
        border-color:#89c8ff;
      }
      .seg-btn.disabled {
        background:#eeeeee; color:#888; border-color:#dddddd; pointer-events:none;
      }

      /* --- 채팅 박스 --- */
      .chat-box { border:2px solid #bcdcff; background:#e6f7ff; padding:12px; border-radius:16px; }
      .bubble { max-width:92%; padding:10px 12px; border-radius:14px; margin:6px 0; line-height:1.5; font-size:1rem; }
      .user  { background:#fff7cc; margin-left:auto; }  /* 학생: 연노랑 */
      .ai    { background:#d9f7d9;  margin-right:auto; } /* AI: 연초록 */
      .row   { display:flex; }
      .row.user { justify-content:flex-end; }
      .row.ai   { justify-content:flex-start; }
    </style>
    """, unsafe_allow_html=True)

# 내부 키 ↔ 표시 라벨(단순화) 매핑
_MODE_KEYS   = ["문법","문장","지문"]   # 내부 로직용
_MODE_LABELS = {"문법":"어법", "문장":"문장", "지문":"지문"}  # ← (1) 단순화 라벨

def _load_modes_cfg_safe() -> Dict[str, Any]:
    defaults = {"allowed": _MODE_KEYS[:], "default": "문법설명"}
    try:
        if '_load_modes_cfg' in globals() and callable(globals()['_load_modes_cfg']):
            if '_sanitize_modes_cfg' in globals() and callable(globals()['_sanitize_modes_cfg']):
                return globals()['_sanitize_modes_cfg'](globals()['_load_modes_cfg']())
            return globals()['_load_modes_cfg']()
        p = PERSIST_DIR / "explain_modes.json"
        if not p.exists(): return defaults
        obj = json.loads(p.read_text(encoding="utf-8") or "{}")
        allowed = [m for m in (obj.get("allowed") or []) if m in _MODE_KEYS]
        default = obj.get("default") or "문법"
        if default not in _MODE_KEYS: default = "문법"
        return {"allowed": allowed, "default": default}
    except Exception:
        return defaults

def _render_mode_controls_minimal(*, admin: bool) -> str:
    _inject_minimal_styles_once()
    ss = st.session_state
    cfg = _load_modes_cfg_safe()
    allowed: set[str] = set(cfg.get("allowed", []))
    default_mode = cfg.get("default", "문법설명")
    cur = ss.get("qa_mode_radio") or default_mode

    # 학생이 비허용 모드에 있으면 폴백
    if (not admin) and (cur not in allowed) and allowed:
        cur = default_mode
        ss["qa_mode_radio"] = cur

    # 3분할 세그먼트 버튼 (a 태그: 밑줄 제거는 CSS text-decoration:none 으로 처리)  ← (2)
    cols = st.columns(3)
    for col, key in zip(cols, _MODE_KEYS):
        label = _MODE_LABELS[key]
        selected   = (cur == key)
        is_disabled = False if admin else (key not in allowed)
        cls = "seg-btn" + (" selected" if selected else "") + (" disabled" if is_disabled else "")
        # 클릭 시 쿼리파라미터 없이 세션으로만 반영(동적 모듈 fetch 오류 예방)
        with col:
            # 링크 대신 버튼형 HTML을 클릭 → 폼 submit 없이 JS로는 못 바꾸므로 Streamlit 버튼 함께 사용
            # 시각은 HTML, 동작은 Streamlit 버튼으로 처리
            st.markdown(f'<div class="seg-wrap"><span class="{cls}">{label}</span></div>', unsafe_allow_html=True)
            if st.button(label, key=f"mode_btn_{key}", disabled=is_disabled):
                ss["qa_mode_radio"] = key
                cur = key
                st.rerun()
    return cur

def _llm_call(prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    if _llm.get("call_with_fallback"):
        return _llm["call_with_fallback"](prompt=prompt, system=system,
                                          primary="gemini", secondary="openai",
                                          temperature=0.3, max_tokens=800)
    return {"ok": False, "error": "LLM providers 모듈 미탑재"}

def _render_chat_panel() -> None:
    if st is None:
        return
    ss = st.session_state
    ss.setdefault("chat", [])
    ss.setdefault("_chat_next_id", 1)

    ready = _is_brain_ready()
    admin = _is_admin_view()

    # 상단 상태 + (미니멀 세그먼트 버튼)
    with st.container(border=True):
        c1, c2 = st.columns([0.65, 0.35])
        with c1:
            st.markdown(f"**{'🟢 준비완료' if ready else '🟡 준비중'}**")  # (3)와 일치
        with c2:
            _ = _render_mode_controls_minimal(admin=admin)

    if not ready:
        _manual_restore_cta()

    # 커스텀 채팅 상자
    st.markdown('<div class="chat-box">', unsafe_allow_html=True)
    for m in ss["chat"]:
        if m["role"] == "user":
            st.markdown(f'<div class="row user"><div class="bubble user">{m["text"]}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="row ai"><div class="bubble ai">{m["text"]}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 입력 + 호출
    user_q = st.chat_input("질문을 입력하세요")
    if not user_q:
        return

    msg_id = ss["_chat_next_id"]; ss["_chat_next_id"] += 1
    ss["chat"].append({"id": msg_id, "role": "user", "text": user_q})

    cfg = _load_modes_cfg_safe()
    mode = ss.get("qa_mode_radio") or cfg.get("default", "문법설명")
    system_prompt = "너는 한국의 영어학원 원장처럼, 따뜻하고 명확하게 설명한다."
    prompt = f"[모드:{mode}]\n{user_q}"

    with st.spinner("생성 중..."):
        try:
            res = _llm_call(prompt, system_prompt)
            text = (res.get("text") or f"생성 실패: {res.get('error')}").strip() if res.get("ok") else (res.get("error") or "생성 실패")
            ss["chat"].append({"id": msg_id+1, "role":"assistant", "text": text, "provider": res.get("provider")})
        except Exception as e:
            ss["chat"].append({"id": msg_id+1, "role":"assistant", "text": f"예외: {type(e).__name__}: {e}"})
            _errlog(f"LLM 예외: {e}", where="[qa_llm]", exc=e)
    st.rerun()
# =========================== [10] END =======================================


# ==== [11] 본문 렌더 =========================================================
def _header_and_login():
    _header()
    _login_panel_if_needed()     # ← 학생 화면에서도 로그인 가능

def _render_body() -> None:
    if st is None: return
    _header_and_login()
    _auto_start_once()
    if _is_admin_view():
        _render_admin_panels()
    st.markdown("## Q&A")
    _render_chat_panel()

# ==== [12] main ==============================================================
def main():
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()

if __name__ == "__main__":
    main()
# =============================== [END] =======================================
