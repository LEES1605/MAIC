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

# [07] 헤더(배지·타이틀·⚙️ 같은 줄, 진행선은 READY시 숨김) =========================
def _header():
    """
    - [좌] 상태 배지, [가운데] 타이틀, [우] ⚙️(아이콘만) — 한 줄에 고정
    - 모바일에서도 줄바꿈 방지(flex-nowrap)
    - 진행선은 READY일 때 숨김
    """
    if st is None:
        return

    ss = st.session_state
    ss.setdefault("_show_admin_login", False)

    # 상태 배지 텍스트/색상
    s = _get_brain_status()
    code = s["code"]
    badge_txt, badge_class = {
        "READY": ("준비완료", "green"),
        "SCANNING": ("준비중", "yellow"),
        "RESTORING": ("복원중", "yellow"),
        "WARN": ("주의", "yellow"),
        "ERROR": ("오류", "red"),
        "MISSING": ("미준비", "red"),
    }.get(code, ("미준비", "red"))

    def _safe_popover(label: str, **kw):
        if hasattr(st, "popover"):
            try:
                return st.popover(label, **kw)
            except Exception:
                pass
        return st.expander(label, expanded=True)

    # ── 스타일
    st.markdown("""
    <style>
      /* 상태 배지 */
      .status-btn{display:inline-block;border-radius:10px;padding:4px 10px;
                  font-weight:700;font-size:13px;margin-right:.5rem}
      .status-btn.green{background:#E4FFF3;color:#0f6d53;border:1px solid #bff0df}
      .status-btn.yellow{background:#FFF8E1;color:#8a6d00;border:1px solid #ffe099}
      .status-btn.red{background:#FFE8E6;color:#a1302a;border:1px solid #ffc7c2}

      /* 3-열을 한 줄(flex-nowrap)로 강제: 배지 · 타이틀 · ⚙️ */
      #brand-flex + div{ display:flex !important; align-items:flex-end !important; gap:.5rem;
                         flex-wrap:nowrap !important; }
      #brand-flex + div [data-testid="column"]{ flex:0 0 auto !important; }
      /* 가운데 열(타이틀)은 유연하게 늘어나고 줄어듦 */
      #brand-flex + div [data-testid="column"]:nth-child(2){ flex:1 1 auto !important; min-width:0; }

      /* 타이틀: 60% 확대 */
      .brand-title{ font-size:2.4em; font-weight:800; letter-spacing:.2px; line-height:1; }

      /* ⚙️ 팝오버 버튼 — 아이콘만(좁은 폭에서도 한 줄 유지) */
      #brand-flex + div [data-testid="stPopover"] > button{
        width:28px; height:28px; min-width:28px; padding:0; border-radius:14px;
      }
      #brand-flex + div [data-testid="stPopover"] > button p{ margin:0; font-size:18px; line-height:1; }

      /* 아주 좁은 폭 대응: 타이틀만 살짝 축소 */
      @media (max-width:420px){
        .brand-title{ font-size:2.1em; }
      }

      /* 본문 타이틀(요청대로 30% 축소) */
      .hero-ask{ font-size:1.54rem; font-weight:800; letter-spacing:.2px; margin: 4px 0 8px; }
    </style>
    """, unsafe_allow_html=True)

    # ── 앵커 → 바로 다음 columns 묶음을 flex-nowrap로 제어
    st.markdown('<div id="brand-flex"></div>', unsafe_allow_html=True)

    # [좌] 배지 · [가운데] 타이틀 · [우] ⚙️(아이콘만)
    c_badge, c_title, c_gear = st.columns([0.0001, 1, 0.0001], gap="small")
    with c_badge:
        st.markdown(f'<span class="status-btn {badge_class}">{badge_txt}</span>', unsafe_allow_html=True)
    with c_title:
        st.markdown('<span class="brand-title">LEES AI Teacher</span>', unsafe_allow_html=True)
    with c_gear:
        if not _is_admin_view():
            with _safe_popover("⚙️"):
                with st.form(key="admin_login"):
                    pwd_set = (_from_secrets("ADMIN_PASSWORD", "")
                               or _from_secrets("APP_ADMIN_PASSWORD", "")
                               or "")
                    pw = st.text_input("관리자 비밀번호", type="password")
                    submit = st.form_submit_button("로그인", use_container_width=True)
                    if submit:
                        if pw and pwd_set and pw == str(pwd_set):
                            ss["admin_mode"] = True
                            st.success("로그인 성공"); st.rerun()
                        else:
                            st.error("비밀번호가 올바르지 않습니다.")
        else:
            with _safe_popover("⚙️"):
                with st.form(key="admin_logout"):
                    col1, col2 = st.columns(2)
                    with col1:
                        submit = st.form_submit_button("로그아웃", use_container_width=True)
                    with col2:
                        close  = st.form_submit_button("닫기",   use_container_width=True)
                if submit:
                    ss["admin_mode"] = False
                    st.success("로그아웃"); st.rerun()
                elif close:
                    st.rerun()

    # 진행선(READY면 자동 숨김)
    _render_boot_progress_line()
    st.divider()



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
    """전역 CSS: 턴 구분선/라디오 pill/상태 배지만. 말풍선 색은 인라인 스타일."""
    if st is None: return
    if st.session_state.get("_chat_styles_injected"):
        return
    st.session_state["_chat_styles_injected"] = True

    st.markdown("""
    <style>
      /* 턴(질문↔답변) 사이 구분선 */
      .turn-sep{height:0; border-top:1px dashed #E5EAF2; margin:14px 2px; position:relative;}
      .turn-sep::after{content:''; position:absolute; top:-4px; left:50%; transform:translateX(-50%);
                       width:8px; height:8px; border-radius:50%; background:#E5EAF2;}
      /* 라디오 pill 보정 */
      div[data-testid="stRadio"] > div[role="radiogroup"]{display:flex;gap:10px;flex-wrap:wrap}
      div[data-testid="stRadio"] [role="radio"]{border:2px solid #bcdcff;border-radius:12px;padding:6px 12px;background:#fff;color:#0a2540;
        font-weight:700;font-size:14px;line-height:1;}
      div[data-testid="stRadio"] [role="radio"][aria-checked="true"]{background:#eaf6ff;border-color:#9fd1ff;color:#0a2540;}
      div[data-testid="stRadio"] svg{display:none!important}
      /* 상태 라벨 */
      .status-btn{display:inline-block;border-radius:10px;padding:4px 10px;font-weight:700; font-size:13px}
      .status-btn.green{background:#E4FFF3;color:#0f6d53;border:1px solid #bff0df}
      .status-btn.yellow{background:#FFF8E1;color:#8a6d00;border:1px solid #ffe099}
      .status-btn.red{background:#FFE8E6;color:#a1302a;border:1px solid #ffc7c2}
    </style>
    """, unsafe_allow_html=True)

def _render_bubble(role:str, text:str):
    """라벨을 칩 형태로 인라인 배치(absolute 제거) → 들여쓰기/겹침 문제 해결."""
    import html, re
    is_user = (role == "user")
    wrap = "display:flex;justify-content:flex-end;margin:8px 0;" if is_user else "display:flex;justify-content:flex-start;margin:8px 0;"
    # 말풍선(질문=파스텔 노랑, 답변=파스텔 하늘)
    base = "max-width:88%;padding:10px 12px;border-radius:16px;line-height:1.6;font-size:15px;box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;position:relative;"
    bubble = (
        base + "border-top-right-radius:8px;border:1px solid #FFE18A;background:#FFF7C2;color:#3d3a00;"
        if is_user else
        base + "border-top-left-radius:8px;border:1px solid #BEE3FF;background:#EAF6FF;color:#0a2540;"
    )
    # 라벨 칩(인라인)
    label_chip = (
        "display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;"
        "background:#FFECAA;color:#6b5200;border:1px solid #FFE18A;"
        if is_user else
        "display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;"
        "background:#DFF1FF;color:#0f5b86;border:1px solid #BEE3FF;"
    )

    t = html.escape(text or "").replace("\n","<br/>")
    t = re.sub(r"  ","&nbsp;&nbsp;", t)
    html_str = (
        f'<div style="{wrap}">'
        f'  <div style="{bubble}">'
        f'    <span style="{label_chip}">{("질문" if is_user else "답변")}</span><br/>'
        f'    {t}'
        f'  </div>'
        f'</div>'
    )
    st.markdown(html_str, unsafe_allow_html=True)

def _render_mode_controls_pills() -> str:
    _inject_chat_styles_once()
    ss = st.session_state
    cur = ss.get("qa_mode_radio") or "문법"
    labels = ["어법", "문장", "지문"]
    map_to = {"어법": "문법", "문장": "문장", "지문": "지문"}
    idx = labels.index({"문법": "어법", "문장": "문장", "지문": "지문"}[cur])
    sel = st.radio("질문 모드 선택", options=labels, index=idx, horizontal=True, label_visibility="collapsed")
    new_key = map_to[sel]
    if new_key != cur:
        ss["qa_mode_radio"] = new_key
        st.rerun()
    return ss.get("qa_mode_radio", new_key)

def _render_llm_status_minimal():
    s = _get_brain_status()
    code = s["code"]
    if code == "READY":
        st.markdown('<span class="status-btn green">🟢 준비완료</span>', unsafe_allow_html=True)
    elif code in ("SCANNING", "RESTORING"):
        st.markdown('<span class="status-btn yellow">🟡 준비중</span>', unsafe_allow_html=True)
    elif code == "WARN":
        st.markdown('<span class="status-btn yellow">🟡 주의</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-btn red">🔴 준비안됨</span>', unsafe_allow_html=True)


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
    # ⬇️ 중복 배지 제거: _render_llm_status_minimal() 호출 삭제
    cur_label = _render_mode_controls_pills()     # "문법" / "문장" / "지문"
    MODE_TOKEN = {"문법":"문법설명","문장":"문장구조분석","지문":"지문분석"}[cur_label]

    ev_notes  = ss.get("__evidence_class_notes", "")
    ev_books  = ss.get("__evidence_grammar_books", "")

    # (이하 기존 로직 동일: 프롬프트 해석, 메시지 렌더, 스트리밍 등)
    # ...


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
    st.markdown('<h2 class="hero-ask">질문은 천재들의 공부 방법이다.</h2>', unsafe_allow_html=True)
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
