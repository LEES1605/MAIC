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
        # LLM
        "OPENAI_API_KEY","OPENAI_MODEL","GEMINI_API_KEY","GEMINI_MODEL",
        # GitHub
        "GITHUB_TOKEN","GITHUB_REPO",
        # Drive
        "GDRIVE_PREPARED_FOLDER_ID","GDRIVE_BACKUP_FOLDER_ID",
        # App
        "APP_MODE",          # admin|student
        "AUTO_START_MODE",   # detect|restore|full
    ]
    for k in keys:
        v = _from_secrets(k)
        if v and not os.getenv(k):
            os.environ[k] = str(v)

    # 서버 안정 설정
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_RUN_ON_SAVE", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION", "false")

_bootstrap_env()

# ==== [04] 경로/상태 & 에러로그 ==============================================
def _persist_dir() -> Path:
    try:
        from src.config import PERSIST_DIR as CFG  # 프로젝트 표준 경로
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

# ==== [05] 동적 임포트 바인딩(있는 것만 사용) ===============================
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

# 관리자/오케스트레이터/백업/RAG/LLM
_ui_admin = _try_import("src.ui_admin", [
    "ensure_admin_session_keys", "render_admin_controls", "render_role_caption", "render_mode_radio_admin"
])
_ui_orch  = _try_import("src.ui_orchestrator", ["render_index_orchestrator_panel"])
_gh       = _try_import("src.backup.github_release", ["restore_latest"])
_rag      = _try_import("src.rag.index_build", ["build_index_with_checkpoint"])
_llm      = _try_import("src.llm.providers", ["call_with_fallback","call_openai","call_gemini"])

# ==== [06] 페이지 설정 & 헤더 =================================================
if st:
    st.set_page_config(page_title="AI Teacher", layout="wide")

def _is_admin_view() -> bool:
    env = (os.getenv("APP_MODE") or _from_secrets("APP_MODE","student") or "student").lower()
    return bool(env == "admin" or (st and (st.session_state.get("is_admin") or st.session_state.get("admin_mode"))))

def _header():
    if st is None: return
    left, right = st.columns([0.7, 0.3])
    with left:
        st.markdown("### AI Teacher")
        st.caption("MAIC · Streamlit 기반 24/7 Q&A")
    with right:
        st.markdown(f"**{'🟢 두뇌 준비됨' if _is_brain_ready() else '🟡 두뇌 연결 대기'}**")
        if _import_warns:
            with st.expander("임포트 경고", expanded=False):
                for w in _import_warns: st.code(w, language="text")
    st.divider()

# ==== [07] 시작 오케스트레이션 ==============================================
def _auto_start_once() -> None:
    if st is None: return
    if st.session_state.get("_auto_started"): return
    st.session_state["_auto_started"] = True

    if _is_brain_ready():  # 이미 준비됨
        return

    mode = (os.getenv("AUTO_START_MODE") or _from_secrets("AUTO_START_MODE","detect") or "detect").lower()
    try:
        if mode == "restore" and _gh.get("restore_latest"):
            ok = bool(_gh["restore_latest"](dest_dir=PERSIST_DIR))
            if ok: _mark_ready()
        elif mode == "full" and _rag.get("build_index_with_checkpoint"):
            _rag["build_index_with_checkpoint"](
                update_pct=lambda *_: None, update_msg=lambda *_: None,
                gdrive_folder_id=os.getenv("GDRIVE_PREPARED_FOLDER_ID","prepared"),
                gcp_creds={}, persist_dir=str(PERSIST_DIR), remote_manifest={}
            )
            _mark_ready()
        # detect 모드: 화면 오케스트레이터에서 질문 진행
    except Exception as e:
        _errlog(f"AUTO_START_MODE 실행 오류: {e}", where="[auto_start]", exc=e)

# ==== [08] 관리자 패널(오케스트레이터/모드/로그) ============================
def _render_admin_panels() -> None:
    if st is None or not _is_admin_view(): return

    # 상단 공통 컨트롤
    if _ui_admin.get("ensure_admin_session_keys"): _ui_admin["ensure_admin_session_keys"]()
    if _ui_admin.get("render_admin_controls"):     _ui_admin["render_admin_controls"]()
    if _ui_admin.get("render_role_caption"):       _ui_admin["render_role_caption"]()
    st.divider()

    # 자료/인덱스 오케스트레이터
    st.markdown("## 관리자: 자료/인덱스 관리")
    if _ui_orch.get("render_index_orchestrator_panel"):
        _ui_orch["render_index_orchestrator_panel"]()
    else:
        st.info("오케스트레이터 모듈이 없습니다: src.ui_orchestrator")

    # 설명 모드 라디오(관리자 전용)
    st.markdown("### 설명 모드 설정")
    if _ui_admin.get("render_mode_radio_admin"):
        _ui_admin["render_mode_radio_admin"]()
    else:
        default = st.session_state.get("qa_mode_radio","문법설명")
        st.session_state["qa_mode_radio"] = st.radio("설명 모드", ["문법설명","문장구조분석","지문분석"],
                                                     index=["문법설명","문장구조분석","지문분석"].index(default))

    # 오류 로그
    with st.expander("오류 로그", expanded=False):
        txt = _errlog_text()
        st.text_area("최근 오류", value=txt, height=180)
        st.download_button("로그 다운로드", data=txt.encode("utf-8"), file_name="app_error_log.txt")

# ==== [09] 채팅 패널(학생/관리자 공통) ======================================
def _llm_call(prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """
    통일 LLM 호출: Gemini → 실패 시 OpenAI 폴백.
    providers 모듈이 없으면 간단 에러 반환.
    """
    if _llm.get("call_with_fallback"):
        return _llm["call_with_fallback"](prompt=prompt, system=system,
                                          primary="gemini", secondary="openai",
                                          temperature=0.3, max_tokens=800)
    return {"ok": False, "error": "LLM providers 모듈 미탑재"}

def _render_chat_panel() -> None:
    if st is None: return
    ss = st.session_state
    ss.setdefault("chat", [])
    ss.setdefault("_chat_next_id", 1)
    ready = _is_brain_ready()

    # 상단 배지
    with st.container(border=True):
        left, right = st.columns([0.7, 0.3])
        with left:
            st.markdown(f"**{'🟢 두뇌 준비됨' if ready else '🟡 두뇌 연결 대기'}**")
        with right:
            mode = ss.get("qa_mode_radio","문법설명")
            st.markdown(f"모드: **{mode}**")

    # 대화 이력
    with st.container(border=True):
        for m in ss["chat"]:
            if m["role"] == "user":
                with st.chat_message("user", avatar="🧑"): st.markdown(m["text"])
            else:
                with st.chat_message("assistant", avatar="🤖"): st.markdown(m["text"])

    # 입력
    user_q = st.chat_input("질문을 입력하세요")
    if not user_q: return

    msg_id = ss["_chat_next_id"]; ss["_chat_next_id"] += 1
    ss["chat"].append({"id": msg_id, "role":"user", "text": user_q})

    system_prompt = "너는 한국의 영어학원 원장처럼, 따뜻하고 명확하게 설명한다."
    mode = ss.get("qa_mode_radio","문법설명")
    prompt = f"[모드:{mode}]\n{user_q}"

    with st.chat_message("assistant", avatar="🤖"):
        slot = st.empty()
        try:
            res = _llm_call(prompt, system_prompt)
            if res.get("ok"):
                text = (res.get("text") or "").strip()
                ss["chat"].append({"id": msg_id+1, "role":"assistant", "text": text, "provider": res.get("provider")})
                slot.markdown(text)
            else:
                slot.error(f"생성 실패: {res.get('error')}")
                _errlog(f"LLM 실패: {res.get('error')}", where="[qa_llm]")
        except Exception as e:
            slot.error(f"예외: {type(e).__name__}: {e}")
            _errlog(f"LLM 예외: {e}", where="[qa_llm]", exc=e)

# ==== [10] 학생/관리자 뷰 게이팅 ============================================
def _render_body() -> None:
    if st is None: return
    # 헤더 + 자동 시작 훅
    _header()
    _auto_start_once()

    # 관리자에게만 관리자 패널 노출
    if _is_admin_view():
        _render_admin_panels()

    # Q&A는 공통
    st.markdown("## Q&A")
    _render_chat_panel()

# ==== [11] main ==============================================================
def main():
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()

if __name__ == "__main__":
    main()
