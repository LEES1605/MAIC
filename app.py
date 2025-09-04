# [01] future import ==========================================================
from __future__ import annotations

# ============================ [02] imports & bootstrap — START ============================
import importlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
from typing import Any as _AnyForSt  # mypy: 전역 st를 Any로 고정

# streamlit: 정적 타입은 Any로(경고 회피), 런타임은 모듈 또는 None
st: _AnyForSt
try:
    import streamlit as _st_mod
    st = _st_mod
except Exception:
    st = None  # mypy에서 Any로 간주되므로 추가 ignore 불필요
# ============================= [02] imports & bootstrap — END =============================

# [03] secrets → env 승격 & 서버 안정 옵션 ====================================
def _from_secrets(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if st is None or not hasattr(st, "secrets"):
            return os.getenv(name, default)
        val = st.secrets.get(name, None)
        if val is None:
            return os.getenv(name, default)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return os.getenv(name, default)

def _bootstrap_env() -> None:
    keys = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GH_TOKEN",
        "GH_REPO",
        "GH_BRANCH",
        "GH_PROMPTS_PATH",
        "GDRIVE_PREPARED_FOLDER_ID",
        "GDRIVE_BACKUP_FOLDER_ID",
        "APP_MODE",
        "AUTO_START_MODE",
        "LOCK_MODE_FOR_STUDENTS",
        "APP_ADMIN_PASSWORD",
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

# ===== [PATCH / app.py / [04] 경로/상태 & 에러로그 / L0071–L0208] — START =====
# [04] 경로/상태 & 에러로그 =====================================================
def _persist_dir() -> Path:
    """인덱스 퍼시스트 경로를 결정한다.
    1) src.rag.index_build.PERSIST_DIR
    2) src.config.PERSIST_DIR
    3) ~/.maic/persist (폴백)
    """
    # 1) 인덱서가 노출하는 경로 우선
    try:
        from src.rag.index_build import PERSIST_DIR as IDX
        return Path(IDX).expanduser()
    except Exception:
        pass
    # 2) 전역 설정 경로
    try:
        from src.config import PERSIST_DIR as CFG
        return Path(CFG).expanduser()
    except Exception:
        pass
    # 3) 최종 폴백
    return Path.home() / ".maic" / "persist"


PERSIST_DIR = _persist_dir()
# 안전: 경로가 없다면 생성
try:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


def _share_persist_dir_into_session(p: Path) -> None:
    """세션 상태에 persist 경로를 공유한다(다른 모듈과 일관성 유지)."""
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = p
    except Exception:
        pass


_share_persist_dir_into_session(PERSIST_DIR)


def _mark_ready() -> None:
    """준비 신호 파일(.ready)을 만든다."""
    try:
        (PERSIST_DIR / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass


def _is_brain_ready() -> bool:
    """인덱스 준비 여부(로컬 신호 기반) — SSOT(단일 진실) 엄격 판정.
    규칙: .ready 파일과 chunks.jsonl(>0B)이 둘 다 있어야 True.
    이렇게 해야 헤더 배지/진행선/진단 패널이 같은 결론을 낸다.
    """
    # 세션에 공유된 경로가 있으면 우선 사용
    p = None
    try:
        p = st.session_state.get("_PERSIST_DIR") if st is not None else None
    except Exception:
        p = None
    if not isinstance(p, Path):
        p = _persist_dir()

    if not p.exists():
        return False

    try:
        ready_ok = (p / ".ready").exists()
        chunks_path = (p / "chunks.jsonl")
        chunks_ok = chunks_path.exists() and chunks_path.stat().st_size > 0
        return bool(ready_ok and chunks_ok)
    except Exception:
        # 어떤 예외든 안전하게 미준비로 처리
        return False


def _get_brain_status() -> dict:
    """앱 전역에서 참조하는 상위 상태(SSOT)를 반환한다.
    반환 예: {"code": "READY"|"MISSING"|..., "msg": "..."}
    - 세션에 명시 상태가 있으면 그것을 우선 사용
    - 없으면 로컬 인덱스 유무로 READY/MISSING 판정
    """
    try:
        if st is None:
            return {"code": "MISSING", "msg": "Streamlit unavailable"}

        ss = st.session_state
        code = ss.get("brain_status_code")
        msg = ss.get("brain_status_msg")
        if code and msg:
            return {"code": str(code), "msg": str(msg)}

        if _is_brain_ready():
            return {"code": "READY", "msg": "로컬 인덱스 연결됨(SSOT)"}
        return {"code": "MISSING", "msg": "인덱스 없음(관리자에서 '업데이트 점검' 필요)"}
    except Exception as e:
        _errlog("상태 계산 실패", where="[04]_get_brain_status", exc=e)
        return {"code": "MISSING", "msg": "상태 계산 실패"}


def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """표준 에러 로깅(콘솔 + Streamlit 노출). 보안/안정성 고려:
    - 메시지에 민감정보를 포함하지 않는다.
    - 실패해도 앱이 죽지 않도록 try/except로 감싼다.
    """
    try:
        prefix = f"{where} " if where else ""
        # 콘솔
        print(f"[ERR] {prefix}{msg}")
        if exc:
            traceback.print_exception(exc)
        # UI 노출(가능할 때만)
        if st is not None:
            try:
                with st.expander("자세한 오류 로그", expanded=False):
                    detail = ""
                    if exc:
                        try:
                            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                        except Exception:
                            detail = "traceback 사용 불가"
                    st.code(f"{prefix}{msg}\n{detail}")
            except Exception:
                # Streamlit 렌더 실패는 무시
                pass
    except Exception:
        # 로깅 자체 실패도 조용히 무시
        pass
# ===== [PATCH / app.py / [04] 경로/상태 & 에러로그 / L0071–L0208] — END =====

# [05] 모드/LLM/임포트 헬퍼 =====================================================
def _is_admin_view() -> bool:
    env = (os.getenv("APP_MODE") or _from_secrets("APP_MODE", "student") or "student").lower()
    return bool(env == "admin" or (st and (st.session_state.get("is_admin") or st.session_state.get("admin_mode"))))


def _llm_health_badge() -> tuple[str, str]:
    """시작 속도를 위해 '키 존재'만으로 최소 상태 표시."""
    has_g = bool(os.getenv("GEMINI_API_KEY") or _from_secrets("GEMINI_API_KEY"))
    has_o = bool(os.getenv("OPENAI_API_KEY") or _from_secrets("OPENAI_API_KEY"))

    if not (has_g or has_o):
        return ("키없음", "⚠️")

    if has_g and has_o:
        return ("Gemini/OpenAI", "✅")

    if has_g:
        return ("Gemini", "✅")

    return ("OpenAI", "✅")


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


def _render_boot_progress_line():
    """지하철 노선 스타일 진행 표시 — 완료여도 항상 보임, 가로 래핑."""
    if st is None:
        return
    ss = st.session_state
    steps = [
        ("LOCAL_CHECK", "로컬검사"),
        ("RESTORE_FROM_RELEASE", "백업복원"),
        ("DIFF_CHECK", "변경감지"),
        ("DOWNLOAD", "다운로드"),
        ("UNZIP", "복구/해제"),
        ("BUILD_INDEX", "인덱싱"),
        ("READY", "완료"),
    ]
    phase = ss.get("_boot_phase") or ("READY" if _is_brain_ready() else "LOCAL_CHECK")
    has_error = phase == "ERROR"
    idx = next((i for i, (k, _) in enumerate(steps) if k == phase), len(steps) - 1)

    st.markdown(
        """
    <style>
      .metro-flex{ display:flex; flex-wrap:wrap; align-items:center; gap:12px 22px; margin:10px 0 6px 0; }
      .metro-node{ display:flex; flex-direction:column; align-items:center; min-width:80px; }
      .metro-seg{ width:84px; height:10px; border-top:4px solid #9dc4ff; border-radius:8px; position:relative; }
      .metro-seg.done{ border-color:#5aa1ff; }
      .metro-seg.doing{ border-color:#ffd168; }
      .metro-seg.todo{ border-top-style:dashed; border-color:#cdd6e1; }
      .metro-seg.error{ border-color:#ef4444; }
      .metro-dot{ position:absolute; top:-5px; right:-6px; width:14px; height:14px; border-radius:50%; background:#ffd168; }
      .metro-lbl{ margin-top:4px; font-size:12px; color:#334155; font-weight:700; white-space:nowrap; }
      @media (max-width:480px){ .metro-seg{ width:72px; } }
    </style>
    """,
        unsafe_allow_html=True,
    )

    html = ['<div class="metro-flex">']
    for i, (_, label) in enumerate(steps):
        if has_error:
            klass = "error" if i == idx else "todo"
        else:
            klass = "done" if i < idx else ("doing" if i == idx else "todo")
        dot = '<div class="metro-dot"></div>' if klass == "doing" else ""
        html.append(
            f'<div class="metro-node"><div class="metro-seg {klass}">{dot}</div><div class="metro-lbl">{label}</div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)

# ============================ [06] RERUN GUARD UTILS — START ============================
def _safe_rerun(tag: str, ttl: int = 1) -> None:
    """
    Streamlit rerun을 '태그별 최대 ttl회'로 제한합니다.
    - tag: 'admin:login', 'admin:logout', 'auto_start' 등 식별자
    - ttl: 허용 rerun 횟수(기본 1회)
    """
    # 전역에서 안전하게 st를 조회 (mypy/런타임 모두 안전)
    st_mod = globals().get("st", None)
    if st_mod is None:
        return

    try:
        ss = getattr(st_mod, "session_state", None)
        if not isinstance(ss, dict):
            return

        key = "__rerun_counts__"
        counts = ss.get(key)
        if not isinstance(counts, dict):
            counts = {}

        cnt = int(counts.get(tag, 0))
        if cnt >= int(ttl):
            return

        counts[tag] = cnt + 1
        ss[key] = counts
        st_mod.rerun()
    except Exception:
        # 가드 자체 실패 시 조용히 무시 (UX를 깨지 않음)
        pass
# ============================= [06] RERUN GUARD UTILS — END =============================

# ============================ [07] 헤더(배지·타이틀·⚙️) — START ============================
def _header():
    """
    - 상단 상태 배지 + 브랜드 타이틀 + 관리자 영역(⚙️/로그아웃)을 한 줄 구성.
    - 관리자 로그인은 st.form으로 처리하여 불필요한 재실행(리렌더)을 최소화.
    - 로그인/로그아웃/닫기 시에는 _safe_rerun(tag, ttl=1)으로 '최대 1회'만 새로고침.
    """
    st_mod = globals().get("st", None)
    if st_mod is None:
        return

    st = st_mod  # 지역 별칭(가독성)
    ss = st.session_state

    # 초기 세션 키
    ss.setdefault("admin_mode", False)
    ss.setdefault("_show_admin_login", False)

    # 현재 브레인 상태
    try:
        status = _get_brain_status()
        code = status.get("code", "MISSING")
    except Exception:
        code = "MISSING"

    badge_txt, badge_class = {
        "READY": ("🟢 준비완료", "green"),
        "SCANNING": ("🟡 준비중", "yellow"),
        "RESTORING": ("🟡 복원중", "yellow"),
        "WARN": ("🟡 주의", "yellow"),
        "ERROR": ("🔴 오류", "red"),
        "MISSING": ("🔴 미준비", "red"),
    }.get(code, ("🔴 미준비", "red"))

    # 간단 스타일(기존 스타일 구획이 있다면 그대로 유지 가능)
    st.markdown(
        """
        <style>
          .status-btn { padding: 4px 8px; border-radius: 8px; font-weight: 600; }
          .status-btn.green { background:#e7f7ee; color:#117a38; }
          .status-btn.yellow{ background:#fff6e5; color:#8a5b00; }
          .status-btn.red   { background:#ffeaea; color:#a40000; }
          .brand-title { font-weight:800; letter-spacing:.2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 1) 상단 바: 배지 | 타이틀 | 관리자 버튼
    c1, c2, c3 = st.columns([1, 3, 1], gap="small")
    with c1:
        st.markdown(
            f'<span class="status-btn {badge_class}">{badge_txt}</span>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown('<span class="brand-title">LEES AI Teacher</span>', unsafe_allow_html=True)
    with c3:
        if ss.get("admin_mode"):
            if st.button("🚪 로그아웃", key="logout_now", help="관리자 로그아웃"):
                ss["admin_mode"] = False
                ss["_show_admin_login"] = False
                if hasattr(st, "toast"):
                    st.toast("로그아웃 완료", icon="👋")
                else:
                    st.success("로그아웃 완료")
                _safe_rerun("admin:logout", ttl=1)
        else:
            if st.button("⚙️", key="open_admin_login", help="관리자 로그인"):
                ss["_show_admin_login"] = not ss.get("_show_admin_login", False)

    # 2) 관리자 로그인 폼(폼 전송 시에만 재실행 발생 → 불필요 리렌더 감소)
    if not ss.get("admin_mode") and ss.get("_show_admin_login"):
        with st.container(border=True):
            st.write("🔐 관리자 로그인")

            # 비밀번호 원천: secrets 우선 → 환경변수 대체
            try:
                pwd_set = (
                    _from_secrets("ADMIN_PASSWORD", None)
                    or _from_secrets("APP_ADMIN_PASSWORD", None)
                    or os.getenv("ADMIN_PASSWORD")
                    or os.getenv("APP_ADMIN_PASSWORD")
                    or None
                )
            except Exception:
                pwd_set = None

            with st.form("admin_login_form", clear_on_submit=False):
                pw = st.text_input("비밀번호", type="password")
                col_a, col_b = st.columns([1, 1])
                submit = col_a.form_submit_button("로그인")
                cancel = col_b.form_submit_button("닫기")

            if cancel:
                ss["_show_admin_login"] = False
                _safe_rerun("admin:close", ttl=1)

            if submit:
                if not pwd_set:
                    st.error("서버에 관리자 비밀번호가 설정되어 있지 않습니다.")
                elif pw and str(pw) == str(pwd_set):
                    ss["admin_mode"] = True
                    ss["_show_admin_login"] = False
                    if hasattr(st, "toast"):
                        st.toast("로그인 성공", icon="✅")
                    else:
                        st.success("로그인 성공")
                    _safe_rerun("admin:login", ttl=1)
                else:
                    st.error("비밀번호가 올바르지 않습니다.")

    # 3) 진행선(부팅/복원 상태 시각화)
    try:
        _render_boot_progress_line()
    except Exception:
        # 진행선 렌더 실패는 UX만 영향 → 조용히 무시
        pass
# ============================= [07] 헤더(배지·타이틀·⚙️) — END =============================



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
    *,
    theme: str = "light",
    accent: str = "#5B8CFF",
    density: int = 3,
    interactive: bool = True,
    animate: bool = True,
    gradient: str = "radial",
    grid: bool = True,
    grain: bool = False,
    blur: int = 0,
    seed: int = 1234,
    readability_veil: bool = True,
) -> None:
    """배경 렌더 OFF(호출 시 즉시 return)."""
    return

# ===== [PATCH / app.py / [09] 부팅 훅(오케스트레이터 오토플로우 호출) / L0397–L0643] — START =====
# [09] 부팅 훅(오케스트레이터 오토플로우 호출) ================================
def _boot_autoflow_hook():
    """앱 부팅 시 1회 오토 플로우 실행(관리자=대화형, 학생=자동)"""
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


# ======================= [10] 부팅/인덱스 준비 — START ========================
def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False):
    # (기존 그대로)
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

# ... (중간 보조 함수들은 기존 그대로 유지) ...

def _auto_start_once():
    """AUTO_START_MODE에 따른 1회성 자동 복원."""
    # 안전 가드: 중복 실행 방지
    try:
        if st is None or not hasattr(st, "session_state"):
            return
        if st.session_state.get("_auto_start_done"):
            return
        st.session_state["_auto_start_done"] = True
    except Exception:
        return

    mode = (os.getenv("AUTO_START_MODE") or _from_secrets("AUTO_START_MODE", "off") or "off").lower()
    if mode not in ("restore", "on"):
        return

    # 전역 헬퍼(_try_import) 없이 표준 importlib로 안전하게 시도
    try:
        import importlib
        rel = importlib.import_module("src.backup.github_release")
        fn = getattr(rel, "restore_latest", None)
    except Exception:
        fn = None

    if not callable(fn):
        return

    try:
        if fn(dest_dir=PERSIST_DIR):
            _mark_ready()
            if hasattr(st, "toast"):
                st.toast("자동 복원 완료", icon="✅")
            else:
                st.success("자동 복원 완료")
            _set_brain_status("READY", "자동 복원 완료", "release", attached=True)
            # 자동복원은 최대 1회만 새로고침
            _safe_rerun("auto_start", ttl=1)
    except Exception as e:
        _errlog(f"auto restore failed: {e}", where="[auto_start]", exc=e)
# ======================== [10] 부팅/인덱스 준비 — END =========================



# ===== [PATCH / app.py / [11] 관리자 패널(지연 임포트 + 파일경로 폴백) / L0643–L0738] — START =====
# =========== [11] 관리자 패널(지연 임포트 + 파일경로 폴백) — START ===========
def _render_admin_panels() -> None:
    """
    관리자 패널(지연 임포트 버전)
    - 토글(또는 체크박스)을 켠 '이후'에만 모듈을 import 및 렌더합니다.
    - import 실패 시 파일 경로에서 직접 로드하는 폴백을 수행합니다.
    """
    if st is None:
        return

    # --- (A) 토글 상태 보존/표시 ---
    toggle_key = "_admin_diag_open"
    st.session_state.setdefault(toggle_key, False)

    # 모바일에선 토글, 데스크톱에선 토글/체크박스 중 사용
    try:
        open_panel = st.toggle("🛠 진단 도구", value=st.session_state[toggle_key], help="필요할 때만 로드합니다.")
    except Exception:
        open_panel = st.checkbox("🛠 진단 도구", value=st.session_state[toggle_key], help="필요할 때만 로드합니다.")

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
                return importlib.import_module(module_name)
            except Exception as e:
                tried_msgs.append(f"{module_name} 실패: {e}")
        # 2) 파일 경로에서 직접 로드(폴백)
        for candidate in ("src/ui_orchestrator.py", "ui_orchestrator.py"):
            try:
                spec = importlib.util.spec_from_file_location("ui_orchestrator", candidate)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    # (mypy: unused-ignore 방지) 직접 실행
                    spec.loader.exec_module(mod)
                    return mod
            except Exception as e:
                tried_msgs.append(f"{candidate} 로드 실패: {e}")
        raise ImportError(" or ".join(tried_msgs))

    # --- (C) 렌더 호출 & 예외 처리 ---
    import time as _time
    import traceback as _tb
    load_start = _time.perf_counter()
    try:
        mod = _import_orchestrator_with_fallback()
        # ✅ 신·구 함수명 호환: 새 이름 → 없으면 구 이름
        render_fn = getattr(mod, "render_index_orchestrator_panel", None)
        if not callable(render_fn):
            render_fn = getattr(mod, "render_diagnostics_panel", None)

        if not callable(render_fn):
            st.warning("진단 도구 렌더러를 찾지 못했습니다. (render_index_orchestrator_panel / render_diagnostics_panel)")
            return

        render_fn()
    except Exception as e:
        st.error("진단 도구 렌더링 중 오류가 발생했습니다.")
        with st.expander("오류 자세히 보기"):
            st.code("".join(_tb.format_exception(type(e), e, e.__traceback__)))
        return
    finally:
        elapsed_ms = (_time.perf_counter() - load_start) * 1000.0

    st.caption(f"✓ 로드/렌더 완료 — {elapsed_ms:.0f} ms")


# ============ [11] 관리자 패널(지연 임포트 + 파일경로 폴백) — END ============
# ===== [PATCH / app.py / [11] 관리자 패널(지연 임포트 + 파일경로 폴백) / L0643–L0738] — END =====



# [12] 채팅 UI(스타일/모드/상단 상태 라벨=SSOT) ===============================
def _inject_chat_styles_once():
    """전역 CSS: ChatPane(대화틀) + 라디오 pill + 노란 입력창 + 인풋 내부 화살표 버튼 + 배지."""
    if st is None:
        return
    if st.session_state.get("_chat_styles_injected"):
        return
    st.session_state["_chat_styles_injected"] = True

    st.markdown(
        """
    <style>
      /* ChatPane */
      .chatpane{
        background:#EDF4FF; border:1px solid #D5E6FF; border-radius:18px;
        padding:10px; margin-top:12px;
      }
      .chatpane .messages{ max-height:60vh; overflow-y:auto; padding:8px; }

      /* 라디오 pill */
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

      /* 인-카드 입력폼: 인풋 내부에 화살표 버튼(절대배치, 순수 CSS) */
      .chatpane form[data-testid="stForm"]{ position:relative; background:#EDF4FF; padding:8px 10px 10px 10px; margin:0; }
      .chatpane form[data-testid="stForm"] input[type="text"]{
        background:#FFF8CC !important; border:1px solid #F2E4A2 !important; border-radius:999px !important;
        color:#333 !important; height:46px; padding-right:56px;
      }
      .chatpane form[data-testid="stForm"] ::placeholder{ color:#8A7F4A !important; }
      .chatpane form[data-testid="stForm"] button[type="submit"]{
        position:absolute; right:18px; top:50%; transform:translateY(-50%);
        width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
        font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
      }

      /* 턴 구분선 */
      .turn-sep{height:0; border-top:1px dashed #E5EAF2; margin:14px 2px; position:relative;}
      .turn-sep::after{content:''; position:absolute; top:-4px; left:50%; transform:translateX(-50%);
                       width:8px; height:8px; border-radius:50%; background:#E5EAF2;}
    </style>
    """,
        unsafe_allow_html=True,
    )


def _render_bubble(role: str, text: str):
    """질문=파스텔 노랑, 답변=파스텔 하늘. 칩은 인라인."""
    import html
    import re

    is_user = role == "user"
    wrap = (
        "display:flex;justify-content:flex-end;margin:8px 0;"
        if is_user
        else "display:flex;justify-content:flex-start;margin:8px 0;"
    )
    base = (
        "max-width:88%;padding:10px 12px;border-radius:16px;line-height:1.6;font-size:15px;"
        "box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;position:relative;"
    )
    bubble = (
        base + "border-top-right-radius:8px;border:1px solid #F2E4A2;background:#FFF8CC;color:#333;"
        if is_user
        else base + "border-top-left-radius:8px;border:1px solid #BEE3FF;background:#EAF6FF;color:#0a2540;"
    )
    label_chip = (
        "display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;"
        "background:#FFF2B8;color:#6b5200;border:1px solid #F2E4A2;"
        if is_user
        else "display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;"
        "background:#DFF1FF;color:#0f5b86;border:1px solid #BEE3FF;"
    )
    t = html.escape(text or "").replace("\n", "<br/>")
    t = re.sub(r"  ", "&nbsp;&nbsp;", t)
    st.markdown(
        f'<div style="{wrap}"><div style="{bubble}"><span style="{label_chip}">'
        f'{"질문" if is_user else "답변"}</span><br/>{t}</div></div>',
        unsafe_allow_html=True,
    )


def _render_mode_controls_pills() -> str:
    """질문 모드 pill (ChatPane 상단에 배치). 반환: '문법'|'문장'|'지문'"""
    _inject_chat_styles_once()
    ss = st.session_state
    cur = ss.get("qa_mode_radio") or "문법"
    labels = ["문법", "문장", "지문"]
    idx = labels.index(cur) if cur in labels else 0
    sel = st.radio("질문 모드", options=labels, index=idx, horizontal=True, label_visibility="collapsed")
    if sel != cur:
        ss["qa_mode_radio"] = sel
        st.rerun()
    return ss.get("qa_mode_radio", sel)

# ============================ [13] 채팅 패널 — START ============================
# [13] 채팅 패널 ==============================================================
def _render_chat_panel():
    ss = st.session_state
    if "chat" not in ss:
        ss["chat"] = []

    _inject_chat_styles_once()

    # 상단: 질문 모드 pill (카톡형에서 입력창 바로 위)
    cur_label = _render_mode_controls_pills()
    MODE_TOKEN = {"문법": "문법설명", "문장": "문장구조분석", "지문": "지문분석"}[cur_label]

    # ChatPane — 메시지 영역 OPEN
    st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)

    # 말풍선 렌더러 -------------------------------------------------------------
    def _render_bubble(role: str, text: str):
        import html as _html, re as _re
        is_user = (role == "user")

        # 정렬/버블 스타일
        wrap = (
            "display:flex;justify-content:flex-end;margin:8px 0;"
            if is_user
            else "display:flex;justify-content:flex-start;margin:8px 0;"
        )
        base = (
            "max-width:88%;padding:10px 12px;border-radius:16px;line-height:1.6;"
            "font-size:15px;box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;"
            "position:relative;"
        )
        bubble = (
            base
            + "border-top-right-radius:8px;border:1px solid #F2E4A2;"
            + "background:#FFF8CC;color:#333;"
            if is_user
            else base
            + "border-top-left-radius:8px;border:1px solid #BEE3FF;"
            + "background:#EAF6FF;color:#0a2540;"
        )

        # 칩 스타일
        chip_role = (
            "display:inline-block;margin:-2px 6px 6px 0;padding:1px 8px;border-radius:999px;"
            "font-size:11px;font-weight:700;background:#FFF2B8;color:#6b5200;"
            "border:1px solid #F2E4A2;"
        )
        chip_src = (
            "display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;"
            "font-size:11px;font-weight:700;background:#eef2f6;color:#334155;"
            "border:1px solid #cbd5e1;"
        )
        chip_pers = (
            "display:inline-block;margin:-2px 6px 6px 0;padding:1px 8px;border-radius:999px;"
            "font-size:11px;font-weight:700;background:#f1f5f9;color:#334155;"
            "border:1px solid #cbd5e1;"
        )

        # 페르소나 이름 매핑
        if role == "assistant":
            persona = "피티쌤"
        elif role == "evaluator":
            persona = "미나쌤"
        else:
            persona = None

        # 히스토리 텍스트에서 '출처:' 꼬리표 분리 → 칩으로 표시
        t = str(text or "")
        m = _re.search(r"^(.*?)(?:\n+|\s+)출처:\s*(.+)$", t, flags=_re.S)
        src = None
        if m:
            body = m.group(1)
            src = m.group(2).strip()
        else:
            body = t

        body = _html.escape(body).replace("\n", "<br/>")
        body = _re.sub(r"  ", "&nbsp;&nbsp;", body)

        if is_user:
            header = f'<span style="{chip_role}">질문</span>'
        else:
            pers_html = (
                f'<span style="{chip_pers}">{_html.escape(persona)}</span>'
                if persona
                else ""
            )
            src_html = (
                f'<span style="{chip_src}">{_html.escape(src)}</span>'
                if src
                else ""
            )
            header = pers_html + src_html

        st.markdown(
            f'<div style="{wrap}"><div style="{bubble}">{header}<br/>' + body + "</div></div>",
            unsafe_allow_html=True,
        )

    # 과거 메시지 렌더
    prev_role = None
    for m in ss["chat"]:
        role = m.get("role", "assistant")
        if prev_role is not None and prev_role != role:
            st.markdown('<div class="turn-sep"></div>', unsafe_allow_html=True)
        _render_bubble(role, m.get("text", ""))
        prev_role = role

    # 스트리밍/유저-즉시 자리(메시지 영역 내부에서 placeholder 확보)
    ph_user = st.empty()   # 전송 직후 "내 말풍선" 즉시 표출용
    ph_ans = st.empty()    # 주답변 스트리밍(피티쌤)
    ph_eval = st.empty()   # 보완 스트리밍(미나쌤)

    # 메시지 영역 CLOSE(폼/업로더는 같은 ChatPane 내부)
    st.markdown("</div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # ＋ 입력 도우미: 카메라/앨범 → OCR → 입력칸 자동 주입
    # ─────────────────────────────────────────────────────────────────────────
    def _close_plus() -> None:
        ss["__plus_open"] = False

    cols = st.columns([1, 12])
    with cols[0]:
        if st.button("＋", key="plus_btn", help="카메라/앨범에서 이미지로 질문하기"):
            ss["__plus_open"] = not ss.get("__plus_open", False)
    with cols[1]:
        st.caption(
            "이미지로 질문하고 싶다면 ＋ 버튼을 눌러 촬영하거나 앨범에서 선택하세요."
        )

    if ss.get("__plus_open"):
        with st.container():
            st.markdown(
                "**입력 도우미** · 이미지를 가져와 텍스트로 변환해 드려요."
            )
            tabs = st.tabs(["📷 카메라", "🖼️ 앨범(사진)"])

            # 공통 OCR 함수
            def _ocr_and_fill(bin_file, filename_hint: str) -> None:
                try:
                    tmp_dir = (PERSIST_DIR / "tmp_uploads")
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    ext = Path(filename_hint).suffix or ".png"
                    fpath = tmp_dir / f"upl_{int(time.time() * 1000)}{ext}"
                    with open(fpath, "wb") as fw:
                        fw.write(bin_file.getbuffer())
                    import importlib
                    ocr_txt = ""
                    try:
                        _m = importlib.import_module("src.vision.ocr")
                        _fn = getattr(_m, "extract_text", None)
                        if callable(_fn):
                            ocr_txt = str(_fn(str(fpath)) or "")
                    except Exception:
                        ocr_txt = ""
                    if ocr_txt:
                        ss["inpane_q"] = ocr_txt.strip()
                        st.success(
                            "✓ OCR 결과를 입력칸에 넣었어요. 필요하면 수정 후 전송하세요."
                        )
                        preview = (
                            ocr_txt[:180] + "…" if len(ocr_txt) > 180 else ocr_txt
                        )
                        st.code(preview or "(빈 텍스트)")
                        return
                    st.warning(
                        "텍스트를 찾지 못했어요. 명암·해상도를 확인하거나 "
                        "다른 이미지를 시도해 주세요."
                    )
                except Exception as e:
                    _errlog("OCR 처리 실패", where="[13]_ocr_plus", exc=e)
                    st.error(
                        "OCR 처리 중 오류가 발생했어요. 텍스트로 직접 입력해 주세요."
                    )

            with tabs[0]:
                cam = st.camera_input("카메라로 촬영", key="camera_input")
                if cam is not None:
                    _ocr_and_fill(cam, "camera.png")

            with tabs[1]:
                up = st.file_uploader(
                    "앨범에서 선택",
                    type=["png", "jpg", "jpeg", "webp", "bmp"],
                    accept_multiple_files=False,
                    key="album_uploader",
                )
                if up is not None:
                    _ocr_and_fill(up, up.name)

            st.button("닫기", on_click=_close_plus)

    # ─────────────────────────────────────────────────────────────────────────
    # 입력 폼 (전송 화살표를 입력칸 '안'에 배치)
    # ─────────────────────────────────────────────────────────────────────────
    with st.form("inpane_chat_form", clear_on_submit=True):
        st.markdown('<div id="inpane_wrap">', unsafe_allow_html=True)
        st.markdown(
            """
            <style>
            #inpane_wrap { position: relative; }
            #inpane_wrap [data-testid="stTextInput"] input {
                padding-right: 48px;
            }
            #inpane_wrap .stButton > button {
                position: absolute;
                right: 8px;
                top: 50%;
                transform: translateY(-50%);
                height: 36px;
                min-height: 36px;
                width: 36px;
                padding: 0;
                border-radius: 999px;
                line-height: 36px;
            }
            @media (max-width: 480px) {
                #inpane_wrap [data-testid="stTextInput"] input {
                    padding-right: 56px;
                }
                #inpane_wrap .stButton > button { right: 6px; }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        qtxt = st.text_input(
            "질문 입력",
            value=ss.get("inpane_q", ""),
            placeholder="예) 분사구문이 뭐예요?  예) 이 문장 구조 분석해줘",
            label_visibility="collapsed",
            key="inpane_q",
        )
        submitted = st.form_submit_button("➤", type="secondary")
        st.markdown("</div>", unsafe_allow_html=True)

    # (A) 제출 처리 — 내 말풍선 즉시 표시 → 답변 스트리밍
    if submitted and not ss.get("_sending", False):
        question = (qtxt or "").strip()
        if not question:
            st.warning("질문을 입력해 주세요.")
            return

        ss["_sending"] = True
        # 1) 히스토리 기록
        ss["chat"].append(
            {"id": f"u{int(time.time()*1000)}", "role": "user", "text": question}
        )
        # 2) 내 말풍선 즉시 표시
        import html as _html, re as _re
        _wrap = "display:flex;justify-content:flex-end;margin:8px 0;"
        _bubble = (
            "max-width:88%;padding:10px 12px;border-radius:16px;line-height:1.6;"
            "font-size:15px;box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;"
            "position:relative;border-top-right-radius:8px;border:1px solid #F2E4A2;"
            "background:#FFF8CC;color:#333;"
        )
        _chip_user = (
            "display:inline-block;margin:-2px 6px 6px 0;padding:1px 8px;border-radius:999px;"
            "font-size:11px;font-weight:700;background:#FFF2B8;color:#6b5200;"
            "border:1px solid #F2E4A2;"
        )
        _body = _html.escape(question).replace("\n", "<br/>")
        _body = _re.sub(r"  ", "&nbsp;&nbsp;", _body)
        ph_user.markdown(
            f'<div style="{_wrap}"><div style="{_bubble}"><span style="{_chip_user}">'
            "질문</span><br/>" + _body + "</div></div>",
            unsafe_allow_html=True,
        )

        # 증거/모드
        ev_notes = ss.get("__evidence_class_notes", "")
        ev_books = ss.get("__evidence_grammar_books", "")

        # 프롬프트 해석
        try:
            from src.prompting.resolve import resolve_prompts
            system_prompt, _resolved_user_prompt, source = resolve_prompts(
                MODE_TOKEN, question, ev_notes, ev_books, cur_label, ss,
            )
            ss["__prompt_source"] = source
        except Exception:
            system_prompt = ""
            ss["__prompt_source"] = "fallback"

        # RAG 라벨(출처 칩)
        try:
            import importlib as _imp
            _label_mod = _imp.import_module("src.rag.label")
            _decide_label = getattr(_label_mod, "decide_label", None)
            _search_hits = getattr(_label_mod, "search_hits", None)
        except Exception:
            _decide_label = None
            _search_hits = None

        try:
            hits = _search_hits(question) if callable(_search_hits) else None
        except Exception:
            hits = None
        try:
            source_label = (
                _decide_label(hits, default_if_none="[AI지식]")
                if callable(_decide_label)
                else "[AI지식]"
            )
        except Exception:
            source_label = "[AI지식]"
        ss["__last_source_label"] = source_label

        # (A-1) 주 답변 에이전트 스트리밍 (피티쌤)
        from typing import Any as _AnyT, Dict as _DictT
        acc_ans = ""

        def _emit_ans(piece: str) -> None:
            nonlocal acc_ans
            import html, re
            acc_ans += str(piece or "")

            def esc(t: str) -> str:
                t = html.escape(t or "").replace("\n", "<br/>")
                return re.sub(r"  ", "&nbsp;&nbsp;", t)

            ph_ans.markdown(
                '<div style="display:flex;justify-content:flex-start;margin:8px 0;">'
                '  <div style="max-width:88%;padding:10px 12px;border-radius:16px;'
                '              border-top-left-radius:8px; line-height:1.6;font-size:15px;'
                '              box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap; position:relative;'
                '              border:1px solid #BEE3FF;background:#EAF6FF;color:#0a2540;">'
                '    <span style="display:inline-block;margin:-2px 6px 6px 0;padding:1px 8px;border-radius:999px;'
                '                 font-size:11px;font-weight:700;background:#f1f5f9;color:#334155;'
                '                 border:1px solid #cbd5e1;">피티쌤</span>'
                '    <span style="display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;'
                '                 font-size:11px;font-weight:700;background:#eef2f6;color:#334155;'
                '                 border:1px solid #cbd5e1;">'
                + esc(str(ss.get("__last_source_label", "")))
                + "</span><br/>"
                + esc(acc_ans)
                + "  </div></div>",
                unsafe_allow_html=True,
            )

        full_answer = ""
        try:
            import importlib as _imp2
            _resp = _imp2.import_module("src.agents.responder")
            _answer_stream = getattr(_resp, "answer_stream", None)
        except Exception:
            _answer_stream = None

        if callable(_answer_stream):
            try:
                for ch in _answer_stream(
                    question=question,
                    mode=MODE_TOKEN,
                    ctx={"hits": hits, "source_label": source_label},
                ):
                    _emit_ans(ch)
                full_answer = acc_ans or "(응답이 비어있어요)"
            except Exception as e:
                full_answer = f"(오류) {type(e).__name__}: {e}"
                _emit_ans(full_answer)
        else:
            try:
                from src.llm import providers as _prov
                call = getattr(_prov, "call_with_fallback", None)
            except Exception:
                call = None
            if callable(call):
                import inspect as _inspect
                params = _inspect.signature(call).parameters.keys()
                kwargs: _DictT[str, _AnyT] = {}
                if "messages" in params:
                    kwargs["messages"] = [
                        {"role": "system", "content": system_prompt or ""},
                        {"role": "user", "content": question},
                    ]
                else:
                    if "prompt" in params:
                        kwargs["prompt"] = question
                    elif "user_prompt" in params:
                        kwargs["user_prompt"] = question
                    if "system_prompt" in params:
                        kwargs["system_prompt"] = system_prompt or ""
                    elif "system" in params:
                        kwargs["system"] = system_prompt or ""
                res = call(**kwargs)
                full_answer = res.get("text") if isinstance(res, dict) else str(res)
                if not full_answer:
                    full_answer = "(응답이 비어있어요)"
                _emit_ans(full_answer)
            else:
                full_answer = "(오류) LLM 어댑터를 사용할 수 없습니다."
                _emit_ans(full_answer)

        # 기록(본문+출처 꼬리표 → 히스토리 렌더 시 칩으로 분리)
        ss["chat"].append(
            {
                "id": f"a{int(time.time()*1000)}",
                "role": "assistant",
                "text": f"{full_answer}\n\n출처: {source_label}",
            }
        )

        # (B) 보완(Co-teacher) 스트리밍 (미나쌤)
        acc_eval = ""

        def _emit_eval(piece: str) -> None:
            nonlocal acc_eval
            import html, re
            acc_eval += str(piece or "")

            def esc2(t: str) -> str:
                t = html.escape(t or "").replace("\n", "<br/>")
                return re.sub(r"  ", "&nbsp;&nbsp;", t)

            ph_eval.markdown(
                '<div style="display:flex;justify-content:flex-start;margin:8px 0;">'
                '  <div style="max-width:88%;padding:10px 12px;border-radius:16px;'
                '              border-top-left-radius:8px; line-height:1.6;font-size:13px;'
                '              box-shadow:0 1px 1px rgba(0,0,0,.04);white-space:pre-wrap; position:relative;'
                '              border:1px dashed #C7D2FE;background:#EEF2FF;color:#1e293b;">'
                '    <span style="display:inline-block;margin:-2px 6px 6px 0;padding:1px 8px;border-radius:999px;'
                '                 font-size:11px;font-weight:700;background:#f1f5f9;color:#334155;'
                '                 border:1px solid #cbd5e1;">미나쌤</span>'
                '    <span style="display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;'
                '                 font-size:11px;font-weight:700;background:#eef2f6;color:#334155;'
                '                 border:1px solid #cbd5e1;">'
                + esc2(str(ss.get("__last_source_label", "")))
                + "</span><br/>"
                + esc2(acc_eval)
                + "  </div></div>",
                unsafe_allow_html=True,
            )

        try:
            import importlib as _imp3
            _eval = _imp3.import_module("src.agents.evaluator")
            _eval_stream = getattr(_eval, "evaluate_stream", None)
        except Exception:
            _eval_stream = None

        if callable(_eval_stream):
            try:
                import inspect as _inspect2
                params = _inspect2.signature(_eval_stream).parameters
                _kwargs: dict = {"question": question, "mode": MODE_TOKEN}
                if "answer" in params:
                    _kwargs["answer"] = full_answer
                if "ctx" in params:
                    _kwargs["ctx"] = {"answer": full_answer}
                for ch in _eval_stream(**_kwargs):
                    _emit_eval(ch)
                full_eval = acc_eval or " "
                _emit_eval(full_eval)
            except TypeError:
                try:
                    for ch in _eval_stream(
                        question=question, mode=MODE_TOKEN, answer=full_answer
                    ):
                        _emit_eval(ch)
                    full_eval = acc_eval or " "
                    _emit_eval(full_eval)
                except Exception as e2:
                    full_eval = f"(오류) {type(e2).__name__}: {e2}"
                    _emit_eval(full_eval)
            except Exception as e:
                full_eval = f"(오류) {type(e).__name__}: {e}"
                _emit_eval(full_eval)
        else:
            full_eval = "보완 에이전트를 사용할 수 없어서, 주 답변만 제공했어요."
            _emit_eval(full_eval)

        # 기록 — evaluator에도 출처 꼬리표 부여
        ss["chat"].append(
            {
                "id": f"e{int(time.time()*1000)}",
                "role": "evaluator",
                "text": f"{full_eval}\n\n출처: {source_label}",
            }
        )

        ss["_sending"] = False
        st.rerun()
# ============================= [13] 채팅 패널 — END =============================



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
        finally:
            st.session_state["_boot_checked"] = True

    # 2) 배경(비활성)
    _mount_background(
        theme="light",
        accent="#5B8CFF",
        density=3,
        interactive=True,
        animate=True,
        gradient="radial",
        grid=True,
        grain=False,
        blur=0,
        seed=1234,
        readability_veil=True,
    )

    # 3) 헤더
    _header()

    # 4) 빠른 부팅(로컬만 확인)
    try:
        _qlao = globals().get("_quick_local_attach_only")
        if callable(_qlao):
            _qlao()
    except Exception as e:
        _errlog(f"quick attach failed: {e}", where="[render_body]", exc=e)

    # 5) 관리자 패널
    if _is_admin_view():
        _render_admin_panels()
        # ❌ 레거시 중복 버튼 삭제:
        #    여기서 추가로 '업데이트 점검' 버튼을 렌더하지 않는다.
        #    모든 복구/점검/재인덱싱은 상단 '🛠 진단 도구' 패널에서만 수행.
        st.caption("ⓘ 복구/재인덱싱은 상단 ‘🛠 진단 도구’ 패널에서만 수행됩니다.")

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
