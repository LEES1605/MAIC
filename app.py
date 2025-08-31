# [01] future import ==========================================================
from __future__ import annotations

# [02] imports & bootstrap ====================================================
import os, io, json, time, traceback, importlib, importlib.util, sys
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

if st:
    st.set_page_config(page_title="LEES AI Teacher", layout="wide")


# [04] 경로/상태 & 에러로그 =====================================================
def _persist_dir() -> Path:
    # 1) 인덱서가 정의한 경로 우선
    try:
        from src.rag.index_build import PERSIST_DIR as IDX
        return Path(IDX).expanduser()
    except Exception:
        pass
    # 2) config 경로
    try:
        from src.config import PERSIST_DIR as CFG
        return Path(CFG).expanduser()
    except Exception:
        pass
    # 3) 최종 폴백
    return Path.home() / ".maic" / "persist"

PERSIST_DIR = _persist_dir()
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# Streamlit 세션에 공유(오케스트레이터와 SSOT 동기화)
def _share_persist_dir_into_session(p: Path) -> None:
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = p
    except Exception:
        pass
_share_persist_dir_into_session(PERSIST_DIR)

def _is_brain_ready() -> bool:
    p = PERSIST_DIR
    if not p.exists():
        return False
    # 존재/용량 신호 중 하나라도 있으면 준비로 간주(빠른 판정)
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


# [05] 모드/LLM/임포트 헬퍼 =====================================================
def _is_admin_view() -> bool:
    env = (os.getenv("APP_MODE") or _from_secrets("APP_MODE", "student") or "student").lower()
    return bool(env == "admin" or (st and (st.session_state.get("is_admin") or st.session_state.get("admin_mode"))))

def _llm_health_badge() -> tuple[str, str]:
    # 시작 속도를 위해 '키 존재'만으로 최소 상태 표시
    has_g  = bool(os.getenv("GEMINI_API_KEY") or _from_secrets("GEMINI_API_KEY"))
    has_o  = bool(os.getenv("OPENAI_API_KEY") or _from_secrets("OPENAI_API_KEY"))
    if not (has_g or has_o): return ("키없음", "⚠️")
    if has_g and has_o: return ("Gemini/OpenAI", "✅")
    return ("Gemini", "✅") if has_g else ("OpenAI", "✅")

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


# [06] 상태 SSOT + 지하철 노선 진행선 ==========================================
def _get_brain_status() -> dict[str, Any]:
    """
    헤더/UI가 공유하는 단일 진실 소스(SSOT) 상태 객체를 반환.
    Fields:
      - code: 'READY' | 'SCANNING' | 'RESTORING' | 'WARN' | 'ERROR' | 'MISSING'
      - attached: bool
      - msg: 사용자 메시지
      - source: 'local' | 'drive' | None
    """
    if st is None:
        return {
            "code": "READY" if _is_brain_ready() else "MISSING",
            "attached": bool(_is_brain_ready()),
            "msg": "테스트 모드: 로컬 인덱스 확인",
            "source": "local" if _is_brain_ready() else None,
        }

    ss = st.session_state
    phase = (ss.get("_boot_phase") or "").upper()
    phase_map = {
        "LOCAL_CHECK": "SCANNING",
        "RESTORE_FROM_RELEASE": "RESTORING",
        "DIFF_CHECK": "SCANNING",
        "REINDEXING": "SCANNING",
        "READY_MARK": "SCANNING",
        "READY": "READY",
        "ERROR": "ERROR",
    }
    phase_code = phase_map.get(phase, "")
    code = (ss.get("brain_status_code") or "").upper().strip()
    if not code:
        code = phase_code or ("READY" if _is_brain_ready() else "MISSING")

    msg  = ss.get("brain_status_msg")
    if not msg:
        default_msgs = {
            "READY": "두뇌 준비완료",
            "SCANNING": "자료 검사 중…",
            "RESTORING": "백업 복원 중…",
            "WARN": "주의: 부분 불일치/검토 필요",
            "ERROR": "오류: 복구/연결 실패",
            "MISSING": "두뇌 없음: 빌드/복원 필요",
        }
        msg = default_msgs.get(code, code)

    attached = code in ("READY", "WARN") and _is_brain_ready()
    return {"code": code, "attached": bool(attached), "msg": str(msg), "source": ss.get("brain_source")}

def _set_phase(code: str, msg: str = "") -> None:
    if st is None: 
        return
    ss = st.session_state
    ss["_boot_phase"] = code
    if msg:
        ss["_boot_msg"] = msg

def _render_boot_progress_line():
    """지하철 노선 스타일 진행 표시
       - READY면 모바일에서 공간 차지 방지를 위해 **완전히 숨김**
       - 모바일(≤640px)에서는 진행선 자체를 한 줄로 숨김(상태 배지로만 표현)
    """
    if st is None:
        return
    ss = st.session_state
    ready_now = _is_brain_ready() or (ss.get("_boot_phase") == "READY")
    if ready_now:
        return  # 준비완료면 진행선 자체를 숨김

    steps = [
        ("LOCAL_CHECK", "로컬검사"),
        ("RESTORE_FROM_RELEASE", "백업복원"),
        ("DIFF_CHECK", "변경감지"),
        ("REINDEXING", "재인덱싱"),
        ("READY_MARK", "마킹"),
        ("READY", "준비완료"),
    ]
    phase = (ss.get("_boot_phase") or "LOCAL_CHECK").upper()
    has_error = (phase == "ERROR")
    idx = next((i for i,(k,_) in enumerate(steps) if k == phase), 0)

    st.markdown("""
    <style>
      /* 모바일에서는 전체 진행선 블록 숨김(상태 배지로 대체) */
      @media (max-width: 640px){
        .metro-wrap{ display:none !important; }
      }
      .metro-wrap{ margin-top:.25rem; }
      .metro-step{flex:1}
      .metro-seg{height:2px;border-top:2px dashed #cdd6e1;margin:6px 0 2px 0}
      .metro-seg.done{border-top-style:solid;border-color:#10a37f}
      .metro-seg.doing{border-top-style:dashed;border-color:#f0ad00}
      .metro-seg.todo{border-top-style:dashed;border-color:#cdd6e1}
      .metro-seg.error{border-top-style:solid;border-color:#c5362c}
      .metro-lbl{font-size:.78rem;color:#536273;text-align:center;white-space:nowrap}
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(len(steps), gap="small")
    for i,(code,label) in enumerate(steps):
        if has_error:
            klass = "error" if i == idx else "todo"
        else:
            if i < idx:  klass = "done"
            elif i == idx: klass = "doing"
            else: klass = "todo"
        with cols[i]:
            st.markdown(
                f'<div class="metro-wrap"><div class="metro-step"><div class="metro-seg {klass}"></div>'
                f'<div class="metro-lbl">{label}</div></div></div>',
                unsafe_allow_html=True
            )

# [07] 헤더(오버레이 배지·3D 타이틀·부제목 앵커) ==============================
def _header():
    """
    - 제목/부제목 한 블록 렌더.
    - 오버레이(🟢/⚙)를 더 위로 띄워 부제목과 간격 확보.
    - 제목: 진한 남색 + 3D 섀도, 폰트 50% 확대.
    """
    if st is None:
        return

    ss = st.session_state
    ss.setdefault("_show_admin_login", False)

    # 쿼리파라미터로 설정패널 열기/닫기
    try:
        qp = st.query_params   # Streamlit ≥1.31
        qp_dict = dict(qp)
        has_new_qp = True
    except Exception:
        qp_dict = st.experimental_get_query_params()
        has_new_qp = False

    if "settings" in qp_dict:
        flag = str(qp_dict.get("settings", "1"))
        ss["_show_admin_login"] = flag in ("1", "true", "True")
        try:
            if has_new_qp:
                st.query_params.clear()
            else:
                st.experimental_set_query_params()
        except Exception:
            pass

    # 상태 배지 텍스트/색상
    status = _get_brain_status()
    code = status["code"]
    badge_txt, badge_class = {
        "READY":     ("🟢 준비완료", "green"),
        "SCANNING":  ("🟡 준비중",   "yellow"),
        "RESTORING": ("🟡 복원중",   "yellow"),
        "WARN":      ("🟡 주의",     "yellow"),
        "ERROR":     ("🔴 오류",     "red"),
        "MISSING":   ("🔴 미준비",   "red"),
    }.get(code, ("🔴 미준비", "red"))

    # CSS/HTML (오버레이 더 위로, 앵커 상단 패딩 추가)
    st.markdown(f"""
    <style>
      .lees-header {{ margin: 0 0 .35rem 0; }}

      .lees-header .title-3d {{
        font-size: clamp(36px, 5.4vw, 63px);
        font-weight: 800; letter-spacing: .3px; line-height: 1.04;
        color: #0B1B45;
        text-shadow:
          0 1px 0 #ffffff,
          0 2px 0 #e9eef9,
          0 3px 0 #d2dbf2,
          0 6px 12px rgba(0,0,0,.22);
        margin: 0;
      }}

      .lees-header .subhead-wrap {{
        position: relative;
        margin-top: .95rem; /* 제목과 부제목 사이 여유 */
      }}

      .lees-header .subhead {{
        position: relative;
        font-weight: 700;
        font-size: clamp(22px, 3.2vw, 36px);
        line-height: 1.25;
        color: #1f2937;
        word-break: keep-all;
      }}

      /* 앵커 위쪽 여백을 키워 오버레이와 본문 텍스트가 닿지 않게 함 */
      .lees-header .anchor {{
        position: relative; display: inline-block;
        padding-top: .45em;  /* ↑ 0.45em */
      }}

      /* 오버레이를 더 위로: translateY(-120%)로 상향 이동 */
      .lees-header .badge, .lees-header .gear {{
        position: absolute; left: 0; top: 0;
        transform: translateY(-120%);
        font-size: .7em; line-height: 1;
        padding: .18em .55em; border-radius: 999px;
        user-select: none; -webkit-tap-highlight-color: transparent;
        z-index: 2; white-space: nowrap;
      }}

      .lees-header .gear {{
        left: 100%;
        margin-left: -0.6em;
        padding: .18em .4em; border-radius: 10px;
        background: #f3f4f6; color: #111827; border: 1px solid #e5e7eb; text-decoration: none;
      }}
      .lees-header .gear:hover {{ filter: brightness(.96); }}

      /* 배지 색상 */
      .lees-header .badge.green  {{ background:#e7f7ef; color:#0a7f49; border:1px solid #bfead7; }}
      .lees-header .badge.yellow {{ background:#fff7e6; color:#9a6a00; border:1px solid #ffe2a8; }}
      .lees-header .badge.red    {{ background:#fde8e8; color:#a61b29; border:1px solid #f5b5bb; }}

      @media (max-width: 380px) {{
        .lees-header .badge, .lees-header .gear {{ transform: translateY(-130%); }}
      }}
    </style>

    <div class="lees-header" id="lees-header">
      <h1 class="title-3d">LEES AI Teacher</h1>
      <div class="subhead-wrap">
        <div class="subhead">
          <span class="anchor anchor-left">질문은
            <span class="badge {badge_class}">{badge_txt}</span>
          </span>
          천재들의 공부 방법
          <span class="anchor anchor-right">이다.
            <a class="gear" href="?settings=1" aria-label="관리자 설정">⚙</a>
          </span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # (선택) 설정 패널
    if ss.get("_show_admin_login") and not _is_admin_view():
        with st.expander("관리자 로그인", expanded=True):
            pwd_set = (_from_secrets("ADMIN_PASSWORD", "")
                       or _from_secrets("APP_ADMIN_PASSWORD", "")
                       or "")
            pw = st.text_input("관리자 비밀번호", type="password")
            if st.button("로그인", use_container_width=True):
                if pw and pwd_set and pw == str(pwd_set):
                    ss["admin_mode"] = True
                    st.success("로그인 성공"); st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
    elif _is_admin_view():
        with st.expander("관리자 메뉴", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                if st.button("로그아웃", use_container_width=True):
                    ss["admin_mode"] = False
                    st.success("로그아웃"); st.rerun()
            with c2:
                st.write(" ")

    _render_boot_progress_line()
    # st.divider()  # ← 유지 금지(제목-부제목 사이 라인 없음)

# [08] 배경(완전 비활성) =======================================================
def _inject_modern_bg_lib():
    """배경 라이브러리 주입을 완전 비활성화(No-Op)."""
    try:
        s = globals().get("st", None)
        if s is not None and hasattr(s, "session_state"):
            s.session_state["__bg_lib_injected__"] = False
    except Exception:
        pass

def _mount_background(
    *, theme: str = "light", accent: str = "#5B8CFF", density: int = 3,
    interactive: bool = True, animate: bool = True, gradient: str = "radial",
    grid: bool = True, grain: bool = False, blur: int = 0, seed: int = 1234,
    readability_veil: bool = True,
) -> None:
    """배경 렌더 OFF(호출 시 즉시 return)."""
    return


# [09] 부팅 훅(오케스트레이터 오토플로우 호출) ================================
def _boot_autoflow_hook():
    """앱 부팅 시 1회 오토 플로우 실행(관리자=대화형, 학생=자동)"""
    try:
        mod = None
        for name in ("src.ui_orchestrator", "ui_orchestrator"):
            try:
                mod = importlib.import_module(name); break
            except Exception:
                mod = None
        if mod and hasattr(mod, "autoflow_boot_check"):
            mod.autoflow_boot_check(interactive=_is_admin_view())
    except Exception as e:
        _errlog(f"boot_autoflow_hook: {e}", where="[boot_hook]", exc=e)


# ======================= [10] 부팅/인덱스 준비 — START ========================
def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False):
    """세션 상태를 일관된 방식으로 세팅한다."""
    if st is None:
        return
    ss = st.session_state
    ss["brain_status_code"] = code
    ss["brain_status_msg"]  = msg
    ss["brain_source"]      = source
    ss["brain_attached"]    = bool(attached)
    ss["restore_recommend"] = (code in ("MISSING","ERROR"))
    ss.setdefault("index_decision_needed", False)
    ss.setdefault("index_change_stats", {})

def _quick_local_attach_only():
    """빠른 부팅: 네트워크 호출 없이 로컬 신호만 확인."""
    if st is None: return False
    ss = st.session_state
    man    = (PERSIST_DIR / "manifest.json")
    chunks = (PERSIST_DIR / "chunks.jsonl")
    ready  = (PERSIST_DIR / ".ready")

    if (chunks.exists() and chunks.stat().st_size > 0) or (man.exists() and man.stat().st_size > 0) or ready.exists():
        _set_brain_status("READY", "로컬 인덱스 연결됨(빠른 부팅)", "local", attached=True)
        return True
    else:
        _set_brain_status("MISSING", "인덱스 없음(관리자에서 '업데이트 점검' 필요)", "", attached=False)
        return False

def _run_deep_check_and_attach():
    """관리자 버튼 클릭 시 실행되는 네트워크 검사+복구."""
    if st is None: return
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
        try:
            # restore_latest가 (dest_dir: Path|str) 모두 수용하도록 사용
            restored = bool(restore_latest(PERSIST_DIR))
        except Exception as e:
            _errlog(f"restore 실패: {e}", where="[deep_check]")

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
    _set_brain_status("MISSING", "업데이트 점검 실패(인덱스 없음). 관리자: 재빌드/복구 필요", "", attached=False)
    ss["index_decision_needed"] = False
    ss["index_change_stats"] = {}

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
                if hasattr(st, "toast"): st.toast("자동 복원 완료", icon="✅")
                else: st.success("자동 복원 완료")
                _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
                if not st.session_state.get("_auto_rerun_done"):
                    st.session_state["_auto_rerun_done"] = True
                    st.rerun()
        except Exception as e:
            _errlog(f"auto restore failed: {e}", where="[auto_start]", exc=e)
# ======================== [10] 부팅/인덱스 준비 — END =========================

# =========== [11] 관리자 패널(지연 임포트 + 파일경로 폴백) — START ===========
def _render_admin_panels() -> None:
    """
    관리자 패널(지연 임포트 버전)
    - 토글(또는 체크박스)을 켠 '이후'에만 모듈을 import 및 렌더합니다.
    - import 실패 시 파일 경로에서 직접 로드하는 폴백을 수행합니다.
    """
    if st is None: return
    import time
    import traceback

    st.subheader("관리자 패널")

    # --- (A) 토글 UI: st.toggle 미지원 환경 대비 체크박스 폴백 ---
    toggle_key = "admin_orchestrator_open"
    if toggle_key not in st.session_state:
        st.session_state[toggle_key] = False

    try:
        open_panel = st.toggle(
            "🛠 진단 도구",
            value=st.session_state[toggle_key],
            help="필요할 때만 로드합니다."
        )
    except Exception:
        open_panel = st.checkbox(
            "🛠 진단 도구",
            value=st.session_state[toggle_key],
            help="필요할 때만 로드합니다."
        )

    st.session_state[toggle_key] = bool(open_panel)

    if not open_panel:
        st.caption("▶ 위 토글을 켜면 진단 도구 모듈을 불러옵니다.")
        return

    # --- (B) 오케스트레이터 모듈 임포트(경로 폴백 포함) ---
    def _import_orchestrator_with_fallback():
        tried_msgs = []
        # 1) 일반 모듈 임포트 시도
        for module_name in ("src.ui_orchestrator", "ui_orchestrator"):
            try:
                return importlib.import_module(module_name), f"import {module_name}"
            except Exception as e:
                tried_msgs.append(f"import {module_name} → {e!r}")

        # 2) 파일 경로에서 직접 로드 폴백
        roots = [
            Path(__file__).resolve().parent,  # app.py 있는 디렉터리
            Path.cwd(),                        # 현재 작업 디렉터리
        ]
        rels = ("src/ui_orchestrator.py", "ui_orchestrator.py")
        for root in roots:
            for rel in rels:
                candidate = (root / rel)
                if candidate.exists():
                    try:
                        spec = importlib.util.spec_from_file_location("ui_orchestrator", candidate)
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules["ui_orchestrator"] = mod
                        assert spec and spec.loader
                        spec.loader.exec_module(mod)  # type: ignore[union-attr]
                        return mod, f"file:{candidate.as_posix()}"
                    except Exception as e:
                        tried_msgs.append(f"file:{candidate} → {e!r}")

        raise ImportError("ui_orchestrator not found", tried_msgs)

    load_start = time.perf_counter()
    with st.spinner("진단 도구 모듈을 불러오는 중…"):
        try:
            mod, how = _import_orchestrator_with_fallback()
        except Exception as e:
            st.error("진단 도구를 불러오지 못했습니다.")
            with st.expander("오류 자세히 보기"):
                if isinstance(e, ImportError) and len(e.args) > 1:
                    attempts = e.args[1]
                    st.write("시도 내역:")
                    for line in attempts:
                        st.write("• ", line)
                st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            return

    # --- (C) 렌더 함수 탐색 및 실행 ---
    candidate_names = ("render_index_orchestrator_panel", "render_orchestrator_panel", "render")
    render_fn = None
    for fn_name in candidate_names:
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            render_fn = fn
            break

    if render_fn is None:
        st.warning(f"렌더 함수를 찾을 수 없습니다: {', '.join(candidate_names)}")
        return

    try:
        render_fn()
    except Exception as e:
        st.error("진단 도구 렌더링 중 오류가 발생했습니다.")
        with st.expander("오류 자세히 보기"):
            st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        return
    finally:
        elapsed_ms = (time.perf_counter() - load_start) * 1000.0

    st.caption(f"✓ 로드/렌더 완료 — {elapsed_ms:.0f} ms")
# ============ [11] 관리자 패널(지연 임포트 + 파일경로 폴백) — END ============

# [12] 채팅 UI(스타일/모드/상단 상태 라벨=SSOT) ===============================
def _inject_chat_styles_once():
    """전역 CSS: 말풍선/라디오 pill + ChatPane(단일 틀) + '모드=카드 하단' 시각 접합."""
    if st is None: return
    if st.session_state.get("_chat_styles_injected"):
        return
    st.session_state["_chat_styles_injected"] = True

    st.markdown("""
    <style>
      /* ───────── ChatPane: 단일 틀(항상 표시) ───────── */
      .chatpane{ background:#f5f7fb;border:1px solid #e6ecf5;border-radius:18px;
                 padding:8px;margin-top:10px; }
      .chatpane .messages{ max-height:60vh;overflow-y:auto;padding:6px; }

      /* '질문모드'를 ChatPane 하단처럼 보이도록: marker 다음의 stRadio를 카드-풋터로 스타일 */
      .pane-foot-marker + div[data-testid="stRadio"]{
        border-left:1px solid #e6ecf5; border-right:1px solid #e6ecf5; border-bottom:1px solid #e6ecf5;
        border-bottom-left-radius:18px; border-bottom-right-radius:18px;
        background:#f5f7fb; padding:10px 12px; margin-top:0; margin-bottom:6px;
      }
      /* 라디오 pill 배치/스타일(유지) */
      div[data-testid="stRadio"] > div[role="radiogroup"]{display:flex;gap:10px;flex-wrap:wrap}
      div[data-testid="stRadio"] [role="radio"]{
        border:2px solid #bcdcff;border-radius:12px;padding:6px 12px;background:#fff;color:#0a2540;
        font-weight:700;font-size:14px;line-height:1;
      }
      div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{background:#eaf6ff;border-color:#9fd1ff;color:#0a2540;}
      div[data-testid="stRadio"] svg{display:none!important}

      /* 턴 구분선(유지) */
      .turn-sep{height:0;border-top:1px dashed #E5EAF2;margin:14px 2px;position:relative;}
      .turn-sep::after{content:'';position:absolute;top:-4px;left:50%;transform:translateX(-50%);
                       width:8px;height:8px;border-radius:50%;background:#E5EAF2;}

      /* 상태 라벨(유지) */
      .status-btn{display:inline-block;border-radius:10px;padding:4px 10px;font-weight:700;font-size:13px}
      .status-btn.green{background:#E4FFF3;color:#0f6d53;border:1px solid #bff0df}
      .status-btn.yellow{background:#FFF8E1;color:#8a6d00;border:1px solid #ffe099}
      .status-btn.red{background:#FFE8E6;color:#a1302a;border:1px solid #ffc7c2}
    </style>
    """, unsafe_allow_html=True)


# [13] 채팅 패널 ==============================================================
def _render_chat_panel():
    import time, base64, json, urllib.request
    try:
        import yaml
    except Exception:
        yaml = None

    ss = st.session_state
    if "chat" not in ss: ss["chat"] = []

    _inject_chat_styles_once()

    # ── 현재 모드(세션 값) 읽기: 모드-선택 UI는 아래 'pane-foot-marker' 바로 뒤에 인라인 렌더
    cur_label = ss.get("qa_mode_radio") or "문법"
    MODE_TOKEN = {"문법":"문법설명","문장":"문장구조분석","지문":"지문분석"}[cur_label]

    # ── 입력창(하단 고정)
    user_q = st.chat_input("예) 분사구문이 뭐예요?  예) 이 문장 구조 분석해줘")
    qtxt = user_q.strip() if user_q and user_q.strip() else None
    do_stream = qtxt is not None
    if do_stream:
        ss["chat"].append({"id": f"u{int(time.time()*1000)}", "role": "user", "text": qtxt})

    ev_notes  = ss.get("__evidence_class_notes", "")
    ev_books  = ss.get("__evidence_grammar_books", "")

    # ── GitHub / Drive / Fallback 프롬프트 로더 (생략 없이 포함)
    def _github_fetch_prompts_text():
        token  = _from_secrets("GH_TOKEN") or os.getenv("GH_TOKEN")
        repo   = _from_secrets("GH_REPO")  or os.getenv("GH_REPO")
        branch = _from_secrets("GH_BRANCH","main") or os.getenv("GH_BRANCH","main")
        path   = _from_secrets("GH_PROMPTS_PATH","prompts.yaml") or os.getenv("GH_PROMPTS_PATH","prompts.yaml")
        if not (token and repo and yaml): return None
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}","User-Agent":"maic-app"})
        try:
            with urllib.request.urlopen(req) as r:
                meta = json.loads(r.read().decode("utf-8"))
                text = base64.b64decode((meta.get("content") or "").encode()).decode("utf-8")
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
            usr_p = (usr_p.replace("{QUESTION}", q)
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
            sys_p = parts.get("system"); usr_p = parts.get("user")
            if usr_p:
                usr_p = (usr_p.replace("{QUESTION}", q)
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
                "1) 한 줄 핵심","2) 이미지/비유 (짧게)","3) 핵심 규칙 3–5개 (• bullet)",
                "4) 예문 1개(+한국어 해석)","5) 한 문장 리마인드",
                "6) 출처 1개: [출처: GPT지식/GEMINI지식/자료명]"
            ]
            usr_p = f"[질문]\n{q}\n\n[작성 지침]\n- 형식을 지켜라.\n" + "\n".join(f"- {x}" for x in lines)
        elif mode_token == "문장구조분석":
            sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
            usr_p = ("[출력 형식]\n0) 모호성 점검\n1) 괄호 규칙 요약\n2) S–V–O–C–M 한 줄 개요\n"
                     "3) 성분 식별: 표/리스트\n4) 구조·구문 단계적 설명\n5) 핵심 포인트 2–3개\n6) 출처 유형만 표기\n\n"
                     f"[문장]\n{q}")
        else:
            sys_p = BASE + " 불확실한 판단은 '약 ~% 불확실'로 명시한다."
            usr_p = ("[출력 형식]\n1) 한 줄 요지\n2) 구조 요약(단락별 핵심)\n3) 핵심어 3–6개+이유\n4) 풀이 힌트\n\n"
                     f"[지문/질문]\n{q}")
        st.session_state["__prompt_source"] = "Fallback"
        return sys_p, usr_p

    def _resolve_prompts(mode_token: str, q: str, ev1: str, ev2: str, cur_label: str):
        gh = _build_prompt_from_github(mode_token, q, ev1, ev2)
        if gh and (gh.get("system") or gh.get("user")):
            st.session_state["__prompt_source"] = "GitHub"
            sys_p = gh.get("system") or ""
            usr_p = gh.get("user") or f"[모드:{mode_token}]\n{q}"
            if mode_token == "문법설명" and not ev1 and not ev2:
                usr_p += "\n\n[지시]\n- 첫 줄: '안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요.'"
            return sys_p, usr_p
        dv = _build_prompt_from_drive(mode_token, q, ev1, ev2)
        if dv and (dv.get("system") or dv.get("user")):
            st.session_state["__prompt_source"] = "Drive"
            sys_p = dv.get("system") or ""
            usr_p = dv.get("user") or f"[모드:{mode_token}]\n{q}"
            if mode_token == "문법설명" and not ev1 and not ev2:
                usr_p += "\n\n[지시]\n- 첫 줄: '안내: 현재 자료 연결이 원활하지 않아 간단 모드로 답변합니다. 핵심만 짧게 안내할게요.'"
            return sys_p, usr_p
        return _fallback_prompts(mode_token, q, ev1, ev2, cur_label)

    # ── 항상 보이는 ChatPane(단일 틀) + 메시지 스크롤 영역
    st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)

    # 기록 렌더
    prev_role = None
    for m in ss["chat"]:
        role = m.get("role","assistant")
        if prev_role is not None and prev_role != role:
            st.markdown('<div class="turn-sep"></div>', unsafe_allow_html=True)
        _render_bubble(role, m.get("text",""))
        prev_role = role

    # ── 스트리밍 출력(메시지 영역 안에서 진행)
    text_final = ""
    if do_stream:
        if prev_role is not None and prev_role == "user":
            st.markdown('<div class="turn-sep"></div>', unsafe_allow_html=True)
        ph = st.empty()

        def _render_ai(text_html: str):
            ph.markdown(
                '<div style="display:flex;justify-content:flex-start;margin:8px 0;">'
                '  <div style="max-width:88%;padding:10px 12px;border-radius:16px;border-top-left-radius:8px;'
                '              line-height:1.6;font-size:15px;box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;'
                '              position:relative;border:1px solid #BEE3FF;background:#EAF6FF;color:#0a2540;">'
                '    <span style="display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;'
                '                 font-size:11px;font-weight:700;background:#DFF1FF;color:#0f5b86;'
                '                 border:1px solid #BEE3FF;">답변</span><br/>'
                f'    {text_html}'
                '  </div>'
                '</div>', unsafe_allow_html=True
            )

        _render_ai("답변 준비중…")
        system_prompt, user_prompt = _resolve_prompts(MODE_TOKEN, qtxt or "", ev_notes, ev_books, cur_label)

        prov = _try_import("src.llm.providers", ["call_with_fallback"])
        call = prov.get("call_with_fallback")
        if not callable(call):
            text_final = "(오류) LLM 어댑터를 사용할 수 없습니다."
            _render_ai(text_final)
        else:
            import html, re, inspect
            def esc(t: str) -> str:
                t = html.escape(t or "").replace("\n","<br/>")
                return re.sub(r"  ","&nbsp;&nbsp;", t)

            sig = inspect.signature(call); params = sig.parameters.keys(); kwargs = {}
            if "messages" in params:
                kwargs["messages"] = [{"role":"system","content":system_prompt or ""},
                                      {"role":"user","content":user_prompt}]
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
                _render_ai(esc(acc))

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
                    _render_ai(esc(text_final))
            except Exception as e:
                text_final = f"(오류) {type(e).__name__}: {e}"
                _render_ai(esc(text_final))

    # ── ChatPane 닫기
    st.markdown('</div></div>', unsafe_allow_html=True)

    # ── ChatPane 하단처럼 보이도록: 질문모드 UI를 'pane-foot-marker' 바로 뒤에 '인라인' 렌더 (함수 호출 제거)
    st.markdown('<div class="pane-foot-marker"></div>', unsafe_allow_html=True)
    mode = st.radio(
        "질문 모드", ["문법","문장","지문"],
        index=["문법","문장","지문"].index(ss.get("qa_mode_radio","문법")),
        horizontal=True, key="qa_mode_radio", label_visibility="collapsed"
    )

    # ── 스트림 완료 후 기록 저장/리렌더
    if do_stream:
        ss["chat"].append({"id": f"a{int(time.time()*1000)}", "role": "assistant", "text": text_final})
        st.rerun()

# ============================ [14] 본문 렌더 — START ============================
def _render_body() -> None:
    if st is None:
        return

    # 1) 부팅 오토플로우 1회 실행
    if not st.session_state.get("_boot_checked"):
        try:
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)

    # 2) 배경(비활성)
    _mount_background(theme="light", accent="#5B8CFF", density=3,
                      interactive=True, animate=True, gradient="radial",
                      grid=True, grain=False, blur=0, seed=1234, readability_veil=True)

    # 3) 헤더
    _header()

    # 4) 빠른 부팅(로컬만 확인)
    try:
        _quick_local_attach_only()
    except Exception as e:
        _errlog(f"quick attach failed: {e}", where="[render_body]", exc=e)

    # 5) 관리자 패널 + 업데이트 점검
    if _is_admin_view():
        _render_admin_panels()
        with st.container():
            if st.button("🧭 업데이트 점검", help="클라우드와 로컬을 비교해 변경 사항을 확인합니다. 필요 시 재인덱싱을 권장합니다.", use_container_width=True):
                with st.spinner("업데이트 점검 중…"):
                    _run_deep_check_and_attach()
                    st.success(st.session_state.get("brain_status_msg", "완료"))
                    st.rerun()

    # 6) (선택) 자동 시작
    _auto_start_once()

    # 7) 본문: 챗
    _render_chat_panel()
# ============================= [14] 본문 렌더 — END =============================




# [15] main ===================================================================
def main():
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()

if __name__ == "__main__":
    main()
# =============================== [END] =======================================
