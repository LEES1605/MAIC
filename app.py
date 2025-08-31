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
        "GH_TOKEN","GH_REPO","GH_BRANCH","GH_PROMPTS_PATH",
        "GDRIVE_PREPARED_FOLDER_ID","GDRIVE_BACKUP_FOLDER_ID",
        "APP_MODE","AUTO_START_MODE","LOCK_MODE_FOR_STUDENTS","APP_ADMIN_PASSWORD",
        "DISABLE_BG",
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
    for s in ["chunks.jsonl","manifest.json",".ready","faiss.index","index.faiss","chroma.sqlite","docstore.json"]:
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

# [05] 지연 임포트 헬퍼 =========================================================
def _try_import(mod: str, attrs: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        m = importlib.import_module(mod)
    except Exception:
        return out
    for a in attrs:
        try:
            out[a] = getattr(m, a)
        except Exception:
            pass
    return out

# [06] 페이지 설정 & 헤더(아이콘 로그인, Enter 제출 지원) =======================
if st:
    st.set_page_config(page_title="LEES AI Teacher", layout="wide")

def _is_admin_view() -> bool:
    env = (os.getenv("APP_MODE") or _from_secrets("APP_MODE", "student") or "student").lower()
    return bool(env == "admin" or (st and (st.session_state.get("is_admin") or st.session_state.get("admin_mode"))))

def _toggle_login_flag():
    st.session_state["_show_admin_login"] = not st.session_state.get("_show_admin_login", False)

def _llm_health_badge() -> tuple[str, str]:
    # 시작 속도를 위해 '키 존재'만으로 최소 상태 표시
    has_g  = bool(os.getenv("GEMINI_API_KEY") or _from_secrets("GEMINI_API_KEY"))
    has_o  = bool(os.getenv("OPENAI_API_KEY") or _from_secrets("OPENAI_API_KEY"))
    if not (has_g or has_o): return ("키없음", "⚠️")
    if has_g and has_o: return ("Gemini/OpenAI", "✅")
    return ("Gemini", "✅") if has_g else ("OpenAI", "✅")
# START [06A] 상태 SSOT 헬퍼 =========================================
def _get_brain_status() -> dict[str, Any]:
    """헤더/관리자 패널이 공유하는 단일 진실 소스(SSOT) 상태 객체를 반환합니다.

    Fields:
      - code: 'READY' | 'SCANNING' | 'RESTORING' | 'WARN' | 'ERROR' | 'MISSING'
      - attached: bool  (Q&A 가능한 상태인지)
      - msg: 사용자용 짧은 메시지
      - source: 'local' | 'drive' | None
    """
    if st is None:
        # headless/test 모드: 파일시스템만으로 판단
        return {
            "code": "READY" if _is_brain_ready() else "MISSING",
            "attached": bool(_is_brain_ready()),
            "msg": "테스트 모드: 로컬 인덱스 확인",
            "source": "local" if _is_brain_ready() else None,
        }

    ss = st.session_state

    # attach/restore 흐름에서 미리 기록해 둔 상태가 있으면 우선 사용
    code = (ss.get("brain_status_code") or "").upper().strip()
    msg  = ss.get("brain_status_msg")
    src  = ss.get("brain_source")  # 'local' | 'drive' | None

    # 하위호환: 세부 코드가 없다면 기존 세션키들로 유추
    if not code:
        if ss.get("restore_in_progress"):
            code = "RESTORING"
        elif ss.get("scan_in_progress"):
            code = "SCANNING"
        elif ss.get("brain_warning"):
            code = "WARN"
        elif ss.get("brain_error"):
            code = "ERROR"
        else:
            code = "READY" if _is_brain_ready() else "MISSING"

    if not msg:
        default_msgs = {
            "READY": "두뇌 준비완료",
            "SCANNING": "자료 스캔 중…",
            "RESTORING": "백업 복원 중…",
            "WARN": "주의: 부분 불일치/검토 필요",
            "ERROR": "오류: 복구/연결 실패",
            "MISSING": "두뇌 없음: 빌드/복원 필요",
        }
        msg = default_msgs.get(code, code)

    attached = code in ("READY", "WARN") and _is_brain_ready()

    return {
        "code": code,
        "attached": bool(attached),
        "msg": str(msg),
        "source": src,
    }
# END [06A] 상태 SSOT 헬퍼 =========================================

# START [06] _header 교체 (L135–L184) =================================
def _header():
    """
    헤더 미니멀:
    - 상태 텍스트(예: '준비완료') 제거, 아이콘만 사용
    - 아이콘을 제목 앞에 배치, 제목 크기 1.5배
    - 로그인 팝오버는 안전 폴백(지원 안 되면 expander)
    """
    import streamlit as st
    if st is None:
        return
    ss = st.session_state
    ss.setdefault("_show_admin_login", False)

    status = _get_brain_status()
    code = status["code"]

    # 상태 → 아이콘만 사용 (텍스트 제거)
    badge_icon = {
        "READY": "🟢", "SCANNING": "🟡", "RESTORING": "🟡",
        "WARN": "🟠", "ERROR": "🔴", "MISSING": "🔴",
    }.get(code, "⚪")

    # 가벼운 안전 팝오버(미지원/실패 시 expander 폴백)
    def _safe_popover(label: str, **kw):
        if hasattr(st, "popover"):
            try:
                return st.popover(label, **kw)
            except Exception:
                pass
        return st.expander(label, expanded=True)

    # 제목/뱃지 스타일(최소 CSS)
    st.markdown("""
    <style>
      .brand-row { display:flex; align-items:center; gap:.5rem; }
      .brand-badge { font-size:1.25em; }
      .brand-title { font-size:1.5em; font-weight:800; letter-spacing:.2px; }
    </style>
    """, unsafe_allow_html=True)

    left, right = st.columns([0.78, 0.22])
    with left:
        st.markdown(
            f'<div class="brand-row"><span class="brand-badge">{badge_icon}</span>'
            f'<span class="brand-title">LEES AI Teacher</span></div>',
            unsafe_allow_html=True
        )
    with right:
        # LLM 상태(간단 캡션만 유지)
        label, icon = _llm_health_badge()
        st.caption(f"LLM: {icon} {label}")

        # 로그인/로그아웃 팝오버(안전 버전)
        if not _is_admin_view():
            with _safe_popover("👤", use_container_width=True):
                with st.form(key="admin_login"):
                    # 비밀번호 키 폴백: ADMIN_PASSWORD → APP_ADMIN_PASSWORD
                    pwd_set = (_from_secrets("ADMIN_PASSWORD", "")
                               or _from_secrets("APP_ADMIN_PASSWORD", "")
                               or "")
                    pw = st.text_input("관리자 비밀번호", type="password")
                    submit = st.form_submit_button("로그인", use_container_width=True)
                    if submit:
                        if pw and pwd_set and pw == str(pwd_set):
                            ss["admin_mode"] = True
                            st.success("로그인 성공")
                            st.rerun()
                        else:
                            st.error("비밀번호가 올바르지 않습니다.")
        else:
            with _safe_popover("👤", use_container_width=True):
                with st.form(key="admin_logout"):
                    col1, col2 = st.columns(2)
                    with col1:
                        submit = st.form_submit_button("로그아웃", use_container_width=True)
                    with col2:
                        close  = st.form_submit_button("닫기",   use_container_width=True)
                if submit:
                    ss["admin_mode"] = False
                    st.success("로그아웃")
                    st.rerun()
                elif close:
                    st.rerun()

    st.divider()
def _login_panel_if_needed():
    return  # 더 이상 사용 안 함

# [06B] 배경 라이브러리(필요 시) ==============================================
# START [06B] 배경 완전 비활성 교체 (L262–L345)
def _inject_modern_bg_lib():
    """
    배경 라이브러리 주입을 완전 비활성화합니다.
    - 과거: 대량 CSS/JS를 st.markdown(unsafe_allow_html=True)로 삽입
    - 현재: No-Op 처리(아무 것도 하지 않음)
    """
    try:
        # 혹시 이전 세션키를 사용하던 코드가 있어도 부작용이 없도록 False로 통일
        st = globals().get("st", None)
        if st is not None and hasattr(st, "session_state"):
            st.session_state["__bg_lib_injected__"] = False
    except Exception:
        pass

def _mount_background(
    *, theme: str = "light", accent: str = "#5B8CFF", density: int = 3,
    interactive: bool = True, animate: bool = True, gradient: str = "radial",
    grid: bool = True, grain: bool = False, blur: int = 0, seed: int = 1234,
    readability_veil: bool = True,
) -> None:
    """
    배경을 렌더하지 않습니다(하드 OFF).
    - 호출부(_render_body) 구조를 유지하기 위해 동일 시그니처로 즉시 return.
    """
    return
# END [06B] 배경 완전 비활성 교체 (L262–L345)


# [07] 부팅/인덱스 준비(빠른 경로) =============================================
def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False):
    """세션 상태를 일관된 방식으로 세팅한다."""
    ss = st.session_state
    ss["index_status_code"] = code
    ss["brain_status_msg"]  = msg
    ss["index_source"]      = source
    ss["brain_attached"]    = bool(attached)
    ss["restore_recommend"] = (code in ("MISSING","ERROR"))
    ss.setdefault("index_decision_needed", False)
    ss.setdefault("index_change_stats", {})

def _quick_local_attach_only():
    """빠른 부팅: 네트워크 호출 없이 로컬 시그널만 확인."""
    ss = st.session_state
    man    = (PERSIST_DIR / "manifest.json")
    chunks = (PERSIST_DIR / "chunks.jsonl")
    ready  = (PERSIST_DIR / ".ready")

    if (chunks.exists() and chunks.stat().st_size > 0) or (man.exists() and man.stat().st_size > 0) or ready.exists():
        _set_brain_status("READY", "로컬 인덱스 연결됨(빠른 부팅)", "local", attached=True)
        return True
    else:
        _set_brain_status("MISSING", "인덱스 없음(관리자에서 '깊은 점검' 필요)", "", attached=False)
        return False

def _run_deep_check_and_attach():
    """관리자 버튼 클릭 시 실행되는 네트워크 검사+복구."""
    ss = st.session_state
    idx = _try_import("src.rag.index_build", ["quick_precheck", "diff_with_manifest"])
    rel = _try_import("src.backup.github_release", ["restore_latest"])
    quick  = idx.get("quick_precheck")
    diff   = idx.get("diff_with_manifest")
    restore_latest = rel.get("restore_latest")

    # 0) 로컬 먼저
    if _is_brain_ready():
        stats = {}
        changed = False
        if callable(diff):
            try:
                d = diff() or {}
                stats = d.get("stats") or {}
                total = int(stats.get("added",0))+int(stats.get("changed",0))+int(stats.get("removed",0))
                changed = total > 0
            except Exception as e:
                _errlog(f"diff 실패: {e}", where="[deep_check]")
        msg = "로컬 인덱스 연결됨" + ("(신규/변경 감지)" if changed else "(변경 없음/판단 불가)")
        _set_brain_status("READY", msg, "local", attached=True)
        ss["index_decision_needed"] = changed
        ss["index_change_stats"] = stats
        return

    # 1) Drive precheck (선택적)
    if callable(quick):
        try: _ = quick() or {}
        except Exception as e: _errlog(f"precheck 예외: {e}", where="[deep_check]")

    # 2) GitHub Releases 복구
    restored = False
    if callable(restore_latest):
        try: restored = bool(restore_latest(PERSIST_DIR))
        except Exception as e: _errlog(f"restore 실패: {e}", where="[deep_check]")

    if restored and _is_brain_ready():
        stats = {}
        changed = False
        if callable(diff):
            try:
                d = diff() or {}
                stats = d.get("stats") or {}
                total = int(stats.get("added",0))+int(stats.get("changed",0))+int(stats.get("removed",0))
                changed = total > 0
            except Exception as e:
                _errlog(f"diff 실패(복구후): {e}", where="[deep_check]")
        msg = "Releases에서 복구·연결" + ("(신규/변경 감지)" if changed else "(변경 없음/판단 불가)")
        _set_brain_status("READY", msg, "release", attached=True)
        ss["index_decision_needed"] = changed
        ss["index_change_stats"] = stats
        return

    # 3) 실패
    _set_brain_status("MISSING", "깊은 점검 실패(인덱스 없음). 관리자: 재빌드/복구 필요", "", attached=False)
    ss["index_decision_needed"] = False
    ss["index_change_stats"] = {}

# [08] 자동 시작(선택) — 기본 비활성 ==========================================
def _auto_start_once():
    """AUTO_START_MODE에 따른 1회성 자동 복원."""
    if st is None or st.session_state.get("_auto_started"):
        return
    st.session_state["_auto_started"] = True

    if _is_brain_ready():
        return

    mode = (os.getenv("AUTO_START_MODE") or _from_secrets("AUTO_START_MODE", "off") or "off").lower()
    if mode in ("restore","on"):
        rel = _try_import("src.backup.github_release", ["restore_latest"])
        fn = rel.get("restore_latest")
        if not callable(fn): return
        try:
            if fn(dest_dir=PERSIST_DIR):
                _mark_ready()
                st.toast("자동 복원 완료", icon="✅")
                _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
                # rerun은 단 1회만 허용
                if not st.session_state.get("_auto_rerun_done"):
                    st.session_state["_auto_rerun_done"] = True
                    st.rerun()
        except Exception as e:
            _errlog(f"auto restore failed: {e}", where="[auto_start]", exc=e)
# [08] END

# ============================== [09] 관리자 패널 — START ==============================
def _render_admin_panels() -> None:
    """
    관리자 패널(지연 임포트 버전)
    - 토글(또는 체크박스)을 켠 '이후'에만 오케스트레이터 모듈을 import 및 렌더합니다.
    - 토글이 꺼져 있으면 어떤 무거운 의존성도 로드하지 않습니다.
    - 실패 시 사용자 메시지(간단) + 상세 스택(Expander)로 안내합니다.
    """
    # 표준 라이브러리(가벼움)
    import time
    import importlib
    import traceback

    # 스트림릿
    import streamlit as st

    st.subheader("관리자 패널")

    # --- (A) 토글 UI: st.toggle 미지원 환경 대비 체크박스 폴백 ---
    #   - 세션 상태 키를 고정해 재실행(rerun) 시에도 상태 유지
    toggle_key = "admin_orchestrator_open"
    if toggle_key not in st.session_state:
        st.session_state[toggle_key] = False

    try:
        open_panel = st.toggle(
            "🔧 오케스트레이터 도구 열기 (지연 로드)",
            value=st.session_state[toggle_key],
            help="클릭 시 필요한 모듈을 즉시 로드합니다."
        )
    except Exception:
        open_panel = st.checkbox(
            "🔧 오케스트레이터 도구 열기 (지연 로드)",
            value=st.session_state[toggle_key],
            help="클릭 시 필요한 모듈을 즉시 로드합니다."
        )

    # 세션 상태 동기화
    st.session_state[toggle_key] = bool(open_panel)

    # 토글이 꺼져 있으면, 어떤 무거운 것도 실행하지 않고 종료
    if not open_panel:
        st.caption("▶ 필요할 때만 로드되도록 최적화되었습니다. 위 토글을 켜면 모듈을 불러옵니다.")
        return

    load_start = time.perf_counter()
    with st.spinner("오케스트레이터 모듈을 불러오는 중…"):
        mod = None
        last_err = None

        # --- (B) 지연 임포트 ---
        # 프로젝트 구조 변화에 대비해 두 가지 경로를 시도합니다.
        for module_name in ("src.ui_orchestrator", "ui_orchestrator"):
            try:
                mod = importlib.import_module(module_name)
                break  # 성공 시 루프 탈출
            except Exception as e:
                last_err = e
                mod = None

    # 임포트 실패 처리
    if mod is None:
        import textwrap
        st.error("오케스트레이터 모듈을 불러오지 못했습니다.")
        if last_err is not None:
            with st.expander("오류 자세히 보기"):
                st.code("".join(traceback.format_exception(type(last_err), last_err, last_err.__traceback__)))
        st.info(textwrap.dedent("""
            점검 팁:
            1) 모듈 경로가 맞는지 확인: src/ui_orchestrator.py 또는 ui_orchestrator.py
            2) 모듈 내 의존 패키지가 누락되지 않았는지 확인
            3) 모듈 import 시 네트워크 초기화가 과도하지 않은지 확인
        """).strip())
        return

    # --- (C) 렌더 함수 탐색 ---
    candidate_names = (
        "render_index_orchestrator_panel",
        "render_orchestrator_panel",
        "render",
    )
    render_fn = None
    for fn_name in candidate_names:
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            render_fn = fn
            break

    if render_fn is None:
        st.warning(f"오케스트레이터 렌더 함수를 찾을 수 없습니다: {', '.join(candidate_names)}")
        return

    # --- (D) 렌더 실행(안전 호출) ---
    try:
        render_fn()  # 모듈 측에서 Streamlit 컴포넌트를 그립니다.
    except Exception as e:
        st.error("오케스트레이터 렌더링 중 오류가 발생했습니다.")
        with st.expander("오류 자세히 보기"):
            st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        return
    finally:
        elapsed_ms = (time.perf_counter() - load_start) * 1000.0

    st.caption(f"✓ 오케스트레이터 로드/렌더 완료 — {elapsed_ms:.0f} ms")

# =============================== [09] 관리자 패널 — END ===============================


# [10] 학생 UI (Stable Chatbot): 파스텔 배경 + 말풍선 + 스트리밍 =================
def _inject_chat_styles_once():
    """
    채팅용 전역 CSS 1회 주입:
    - 커스텀 레이아웃(.row/.bubble)과 Streamlit chat 모두를 타겟팅
    - 사용자: 보라 톤 / AI: 화이트, 확실한 대비
    """
    import streamlit as st  # 안전상 재임포트 허용
    if st.session_state.get("_chat_styles_injected"):
        return
    st.session_state["_chat_styles_injected"] = True

    st.markdown("""
    <style>
      /* ===== 공통 컨테이너(있으면 적용, 없으면 무해) ===== */
      .chat-wrap{
        background:#f5f7fb !important;border:1px solid #e6ecf5 !important;border-radius:18px;
        padding:10px 10px 8px;margin-top:10px
      }
      .chat-box{min-height:240px;max-height:54vh;overflow-y:auto;padding:6px 6px 2px}

      /* ===== 커스텀 말풍선(앱 내 .row/.bubble 구조용) ===== */
      .row{display:flex;margin:8px 0}
      .row.user{justify-content:flex-end}
      .row.ai{justify-content:flex-start}
      .bubble{
        max-width:88%;padding:12px 14px;border-radius:16px;line-height:1.6;font-size:15px;
        box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;position:relative;border:1px solid #e0e4ea;
      }
      /* 사용자(보라 톤) */
      .bubble.user{
        background:#EFE6FF !important;
        color:#201547;
        border-color:#D6CCFF !important;
        border-top-right-radius:8px;
      }
      /* AI(화이트) */
      .bubble.ai{
        background:#FFFFFF;
        color:#14121f;
        border-top-left-radius:8px;
      }

      /* ===== Streamlit chat 기본 위젯에 대한 보정(있을 때만 적용) ===== */
      /* 사용자 메시지(오른쪽) */
      [data-testid="stChatMessageUser"] > div{
        display:flex; justify-content:flex-end;
      }
      [data-testid="stChatMessageUser"] [data-testid="stMarkdownContainer"]{
        max-width:88%; background:#EFE6FF; color:#201547;
        border:1px solid #D6CCFF; border-radius:16px; border-top-right-radius:8px;
        padding:12px 14px; box-shadow:0 1px 1px rgba(0,0,0,.05);
      }
      /* 어시스턴트 메시지(왼쪽) */
      [data-testid="stChatMessage"] > div{
        display:flex; justify-content:flex-start;
      }
      [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"]{
        max-width:88%; background:#FFFFFF; color:#14121f;
        border:1px solid #e0e4ea; border-radius:16px; border-top-left-radius:8px;
        padding:12px 14px; box-shadow:0 1px 1px rgba(0,0,0,.05);
      }

      /* ===== 라디오(모드 선택) pill 형태 보정 ===== */
      div[data-testid="stRadio"] > div[role="radiogroup"]{display:flex;gap:10px;flex-wrap:wrap}
      div[data-testid="stRadio"] [role="radio"]{
        border:2px solid #bcdcff;border-radius:12px;padding:6px 12px;background:#fff;color:#0a2540;
        font-weight:700;font-size:14px;line-height:1;
      }
      div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{
        background:#eaf6ff;border-color:#9fd1ff;color:#0a2540;
      }
      div[data-testid="stRadio"] svg{display:none!important}
    </style>
    """, unsafe_allow_html=True)
def _render_bubble(role:str, text:str):
    import html, re
    klass = "user" if role=="user" else "ai"
    t = html.escape(text or "").replace("\n","<br/>")
    t = re.sub(r"  ","&nbsp;&nbsp;", t)
    st.markdown(f'<div class="row {klass}"><div class="bubble {klass}">{t}</div></div>', unsafe_allow_html=True)

def _render_mode_controls_pills():
    """
    질문 모드 라디오: 라벨 문구를 미니멀하게 숨김(label_visibility='collapsed')
    기존 상태 키(ss['qa_mode_radio'])와 '어법/문장/지문' 맵핑 유지
    """
    import streamlit as st
    _inject_chat_styles_once()
    ss = st.session_state

    cur = ss.get("qa_mode_radio") or "문법"
    labels = ["어법", "문장", "지문"]
    map_to = {"어법": "문법", "문장": "문장", "지문": "지문"}
    idx = labels.index({"문법": "어법", "문장": "문장", "지문": "지문"}[cur])

    # ⚠️ 라벨 숨김(미니멀): label_visibility="collapsed"
    sel = st.radio(
        "질문 모드 선택",
        options=labels,
        index=idx,
        horizontal=True,
        label_visibility="collapsed",
    )
    new_key = map_to[sel]
    if new_key != cur:
        ss["qa_mode_radio"] = new_key
        st.rerun()
    return ss.get("qa_mode_radio", new_key)
def _render_llm_status_minimal():
    has_g  = bool(os.getenv("GEMINI_API_KEY") or _from_secrets("GEMINI_API_KEY"))
    has_o  = bool(os.getenv("OPENAI_API_KEY") or _from_secrets("OPENAI_API_KEY"))
    ok = bool(has_g or has_o)
    st.markdown(
        f'<span class="status-btn {"green" if ok else "yellow"}">'
        f'{"🟢 준비완료" if ok else "🟡 키없음"}</span>', unsafe_allow_html=True)

def _render_chat_panel():
    import time, base64, json, urllib.request
    try:
        import yaml
    except Exception:
        yaml = None

    ss = st.session_state
    if "chat" not in ss: ss["chat"] = []

    _inject_chat_styles_once()
    _render_llm_status_minimal()
    cur_label = _render_mode_controls_pills()     # "문법" / "문장" / "지문"
    MODE_TOKEN = {"문법":"문법설명","문장":"문장구조분석","지문":"지문분석"}[cur_label]

    ev_notes  = ss.get("__evidence_class_notes", "")
    ev_books  = ss.get("__evidence_grammar_books", "")

    # GitHub prompts 로더(질문이 있을 때만 네트워크)
    def _github_fetch_prompts_text():
        token  = st.secrets.get("GH_TOKEN") or os.getenv("GH_TOKEN")
        repo   = st.secrets.get("GH_REPO")  or os.getenv("GH_REPO")
        branch = st.secrets.get("GH_BRANCH", "main") or os.getenv("GH_BRANCH","main")
        path   = st.secrets.get("GH_PROMPTS_PATH", "prompts.yaml") or os.getenv("GH_PROMPTS_PATH","prompts.yaml")
        if not (token and repo and yaml):
            return None
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}","User-Agent": "maic-app"})
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
            usr_p = (usr_p
                     .replace("{QUESTION}", q)
                     .replace("{EVIDENCE_CLASS_NOTES}", ev1 or "")
                     .replace("{EVIDENCE_GRAMMAR_BOOKS}", ev2 or ""))
            return {"system": sys_p, "user": usr_p}
        except Exception:
            return None

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

    def _fallback_prompts(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str):
        NOTICE = "안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요."
        BASE = "너는 한국의 영어학원 원장처럼 따뜻하고 명확하게 설명한다. 모든 출력은 한국어로 간결하게."
        if mode_token == "문법설명":
            sys_p = BASE + " 주제에서 벗어난 장황한 배경설명은 금지한다."
            lines = []
            if not ev1 and not ev2: lines.append(NOTICE)
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
        else:
            sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
            usr_p = (
                "[출력 형식]\n"
                "1) 한 줄 요지(명사구)\n"
                "2) 구조 요약: (서론–본론–결론) 또는 단락별 핵심 문장\n"
                "3) 핵심어/표현 3–6개 + 이유\n"
                "4) 문제풀이 힌트(있다면)\n\n"
                f"[지문/질문]\n{q}"
            )
        st.session_state["__prompt_source"] = "Fallback"
        return sys_p, usr_p

    def _resolve_prompts(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str):
        gh = _build_prompt_from_github(mode_token, q, ev1, ev2)
        if gh and (gh.get("system") or gh.get("user")):
            st.session_state["__prompt_source"] = "GitHub"
            sys_p = gh.get("system") or ""
            usr_p = gh.get("user") or f"[모드:{mode_token}]\n{q}"
            if mode_token == "문법설명" and not ev1 and not ev2:
                usr_p += "\n\n[지시]\n- 답변 첫 줄을 다음 문장으로 시작: '안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요.'"
            return sys_p, usr_p

        dv = _build_prompt_from_drive(mode_token, q, ev1, ev2)
        if dv and (dv.get("system") or dv.get("user")):
            st.session_state["__prompt_source"] = "Drive"
            sys_p = dv.get("system") or ""
            usr_p = dv.get("user") or f"[모드:{mode_token}]\n{q}"
            if mode_token == "문법설명" and not ev1 and not ev2:
                usr_p += "\n\n[지시]\n- 답변 첫 줄을 다음 문장으로 시작: '안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요.'"
            return sys_p, usr_p

        return _fallback_prompts(mode_token, q, ev1, ev2, cur_label)

    # 입력 & 렌더
    user_q = st.chat_input("예) 분사구문이 뭐예요?  예) 이 문장 구조 분석해줘")
    qtxt = user_q.strip() if user_q and user_q.strip() else None
    do_stream = qtxt is not None
    if do_stream:
        ts = int(time.time()*1000); uid = f"u{ts}"
        ss["chat"].append({"id": uid, "role": "user", "text": qtxt})

    with st.container():
        st.markdown('<div class="chat-wrap"><div class="chat-box">', unsafe_allow_html=True)
        for m in ss["chat"]:
            _render_bubble(m.get("role","assistant"), m.get("text",""))

        text_final = ""
        if do_stream:
            ph = st.empty()
            ph.markdown(f'<div class="row ai"><div class="bubble ai">{"답변 준비중…"}</div></div>', unsafe_allow_html=True)
            system_prompt, user_prompt = _resolve_prompts(MODE_TOKEN, qtxt, ev_notes, ev_books, cur_label)

            # LLM 어댑터는 필요할 때만 지연 임포트
            prov = _try_import("src.llm.providers", ["call_with_fallback"])
            call = prov.get("call_with_fallback")

            if not callable(call):
                text_final = "(오류) LLM 어댑터를 사용할 수 없습니다."
                ph.markdown(f'<div class="row ai"><div class="bubble ai">{text_final}</div></div>', unsafe_allow_html=True)
            else:
                import inspect
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
                    elif "system" in params:      kwargs["system"] = (system_prompt or "")

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
                    ph.markdown(f'<div class="row ai"><div class="bubble ai">{acc}</div></div>', unsafe_allow_html=True)

                supports_stream = ("stream" in params) or ("on_token" in params) or ("on_delta" in params) or ("yield_text" in params)
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
                        ph.markdown(f'<div class="row ai"><div class="bubble ai">{text_final}</div></div>', unsafe_allow_html=True)
                except Exception as e:
                    text_final = f"(오류) {type(e).__name__}: {e}"
                    ph.markdown(f'<div class="row ai"><div class="bubble ai">{text_final}</div></div>', unsafe_allow_html=True)
                    _errlog(f"LLM 예외: {e}", where="[qa_llm]", exc=e)

        st.markdown('</div></div>', unsafe_allow_html=True)

    if do_stream:
        ss["chat"].append({"id": f"a{int(time.time()*1000)}", "role": "assistant", "text": text_final})
        st.rerun()

# [11] 본문 렌더 ===============================================================
def _render_body() -> None:
    if st is None:
        return

    # 배경(필요 시)
    _mount_background(theme="light", accent="#5B8CFF", density=3,
                      interactive=True, animate=True, gradient="radial",
                      grid=True, grain=False, blur=0, seed=1234, readability_veil=True)

    _header()

    # 빠른 부팅: 네트워크 없이 로컬만 확인
    try:
        _quick_local_attach_only()
    except Exception as e:
        _errlog(f"quick attach failed: {e}", where="[render_body]", exc=e)

    # 관리자 패널 + 깊은 점검 버튼(네트워크 호출)
    if _is_admin_view():
        _render_admin_panels()
        with st.container():
            if st.button(
                "🔎 자료 자동 점검(깊은 검사)",
                help="Drive/Release 점검 및 복구, 변경 감지 수행",
                use_container_width=True
            ):
                with st.spinner("깊은 점검 중…"):
                    _run_deep_check_and_attach()
                    st.success(st.session_state.get("brain_status_msg", "완료"))
                    st.rerun()

    _auto_start_once()

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
