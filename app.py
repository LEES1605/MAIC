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
    """전역 CSS: ChatPane + 라디오 pill + 노란 입력창 + 인풋 내부 화살표 버튼 + 말풍선/칩."""
    if st is None:
        return
    if st.session_state.get("_chat_styles_injected"):
        return
    st.session_state["_chat_styles_injected"] = True

    st.markdown(
        """
    <style>
      /* ChatPane 컨테이너 */
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

      /* 인-카드 입력폼: 인풋 내부 화살표 버튼(절대배치) */
      .chatpane form[data-testid="stForm"]{ position:relative; background:#EDF4FF; padding:8px 10px 10px 10px; margin:0; }
      .chatpane form[data-testid="stForm"] input[type="text"]{
        background:#FFF8CC !important; border:1px solid #F2E4A2 !important; border-radius:999px !important;
        color:#333 !important; height:46px; padding-right:56px;
      }
      .chatpane form[data-testid="stForm"] ::placeholder{ color:#8A7F4A !important; }
      /* Streamlit이 type="button"일 수 있으므로 type 지정 없이 버튼 전체를 타깃 */
      .chatpane form[data-testid="stForm"] button{
        position:absolute; right:18px; top:50%; transform:translateY(-50%);
        width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
        font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
      }

      /* 말풍선 기본 */
      .msg-row{ display:flex; margin:8px 0; }
      .msg-row.left{ justify-content:flex-start; }
      .msg-row.right{ justify-content:flex-end; }
      .bubble{
        max-width:88%; padding:10px 12px; border-radius:16px; line-height:1.6; font-size:15px;
        box-shadow:0 1px 1px rgba(0,0,0,.05); white-space:pre-wrap; position:relative;
      }
      .bubble.user{ border-top-right-radius:8px; border:1px solid #F2E4A2; background:#FFF8CC; color:#333; }
      .bubble.ai  { border-top-left-radius:8px;  border:1px solid #BEE3FF; background:#EAF6FF; color:#0a2540; }

      /* 칩(이름) & 출처 */
      .chip{
        display:inline-block; margin:-2px 0 6px 0; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:700;
        color:#fff; line-height:1;
      }
      .chip.me{ background:#059669; }     /* 나 */
      .chip.pt{ background:#2563eb; }     /* 피티쌤 */
      .chip.mn{ background:#7c3aed; }     /* 미나쌤 */
      .chip-src{
        display:inline-block; margin-left:6px; padding:2px 8px; border-radius:10px;
        background:#eef2ff; color:#3730a3; font-size:12px; font-weight:600; line-height:1;
        border:1px solid #c7d2fe; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        vertical-align:middle;
      }

      /* 턴 구분선(옵션) */
      .turn-sep{height:0; border-top:1px dashed #E5EAF2; margin:14px 2px; position:relative;}
      .turn-sep::after{content:''; position:absolute; top:-4px; left:50%; transform:translateX(-50%);
                       width:8px; height:8px; border-radius:50%; background:#E5EAF2;}
      @media (max-width:480px){
        .bubble{ max-width:96%; }
        .chip-src{ max-width:160px; }
      }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _render_bubble(role: str, text: str):
    """(참고용) 기본 말풍선 렌더러."""
    import html, re
    is_user = role == "user"
    side = "right" if is_user else "left"
    klass = "user" if is_user else "ai"
    t = html.escape(text or "").replace("\n", "<br/>")
    t = re.sub(r"  ", "&nbsp;&nbsp;", t)
    st.markdown(
        f'<div class="msg-row {side}"><div class="bubble {klass}">{t}</div></div>',
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
# 질문(나=오른쪽) → 피티쌤(왼쪽, 스트리밍) → 미나쌤(왼쪽, 스트리밍)
def _render_chat_panel() -> None:
    import importlib as _imp
    import html, re
    from typing import Optional
    import streamlit as st

    # 라벨러(출처 칩)
    try:
        try:
            _label_mod = _imp.import_module("src.rag.label")
        except Exception:
            _label_mod = _imp.import_module("label")
        _decide_label = getattr(_label_mod, "decide_label", None)
        _search_hits = getattr(_label_mod, "search_hits", None)
    except Exception:
        _decide_label = None
        _search_hits = None

    # 제너레이터 & 버퍼
    from src.agents.responder import answer_stream
    from src.agents.evaluator import evaluate_stream
    from src.llm.streaming import BufferOptions, make_stream_handler

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

    def _emit_bubble(placeholder, who: str, acc_text: str, *, source: Optional[str], align_right: bool) -> None:
        side_cls = "right" if align_right else "left"
        klass = "user" if align_right else "ai"
        chips = _chip_html(who) + (_src_html(source) if not align_right else "")
        html_block = (
            f'<div class="msg-row {side_cls}">'
            f'  <div class="bubble {klass}">{chips}<br/>{_esc(acc_text)}</div>'
            f'</div>'
        )
        placeholder.markdown(html_block, unsafe_allow_html=True)

    # 상태
    ss = st.session_state
    question = str(ss.get("inpane_q", "") or "").strip()
    if not question:
        return

    # 출처 라벨
    src_label = "[AI지식]"
    if callable(_search_hits) and callable(_decide_label):
        try:
            hits = _search_hits(question, top_k=5)
            src_label = _decide_label(hits, default_if_none="[AI지식]")
        except Exception:
            src_label = "[AI지식]"

    # 1) 사용자 말풍선(오른쪽)
    ph_user = st.empty()
    _emit_bubble(ph_user, "나", question, source=None, align_right=True)

    # 2) 피티쌤(왼쪽, 스트리밍)
    ph_ans = st.empty()
    acc_ans = ""

    def _on_emit_ans(chunk: str) -> None:
        nonlocal acc_ans
        acc_ans += str(chunk or "")
        _emit_bubble(ph_ans, "피티쌤", acc_ans, source=src_label, align_right=False)

    emit_chunk_ans, close_stream_ans = make_stream_handler(
        on_emit=_on_emit_ans,
        opts=BufferOptions(
            min_emit_chars=8,
            soft_emit_chars=24,
            max_latency_ms=150,
            flush_on_strong_punct=True,
            flush_on_newline=True,
        ),
    )
    for piece in answer_stream(question=question, mode=ss.get("__mode", "")):
        emit_chunk_ans(str(piece or ""))
    close_stream_ans()
    full_answer = acc_ans.strip() or "(응답이 비어있어요)"

    # 3) 미나쌤(왼쪽, 스트리밍)
    ph_eval = st.empty()
    acc_eval = ""

    def _on_emit_eval(chunk: str) -> None:
        nonlocal acc_eval
        acc_eval += str(chunk or "")
        _emit_bubble(ph_eval, "미나쌤", acc_eval, source=src_label, align_right=False)

    emit_chunk_eval, close_stream_eval = make_stream_handler(
        on_emit=_on_emit_eval,
        opts=BufferOptions(
            min_emit_chars=8,
            soft_emit_chars=24,
            max_latency_ms=150,
            flush_on_strong_punct=True,
            flush_on_newline=True,
        ),
    )
    for piece in evaluate_stream(
        question=question,
        mode=ss.get("__mode", ""),
        answer=full_answer,
        ctx={"answer": full_answer},
    ):
        emit_chunk_eval(str(piece or ""))
    close_stream_eval()
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
        try:
            _render_admin_index_panel()
        except Exception as e:
            _errlog(f"admin index panel failed: {e}", where="[admin-index]", exc=e)
        st.caption("ⓘ 복구/재인덱싱은 상단 ‘🛠 진단 도구’ 또는 아래 인덱싱 패널에서 수행할 수 있어요.")

    # 6) 자동 시작
    _auto_start_once()

    # 7) 채팅 메시지(상단)
    _inject_chat_styles_once()
    _render_chat_panel()

    # 8) 입력 폼(항상 맨 아래에 위치)
    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        # 모드 pill → 세션 반영
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        # 입력폼(화살표는 CSS로 인풋 내부 우측에 고정)
        with st.form("chat_form", clear_on_submit=False):
            q = st.text_input("질문", placeholder="질문을 입력하세요…", key="q_text")
            submitted = st.form_submit_button("➤")
        st.markdown('</div>', unsafe_allow_html=True)

    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        # 입력 직후 한 번 더 렌더하여 곧바로 대화 표시(허용 rerun 1회)
        _safe_rerun("chat:submit", ttl=1)
    else:
        st.session_state.setdefault("inpane_q", "")
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
# ======================== [16] ADMIN: Index Panel — START ========================
def _render_admin_index_panel() -> None:
    """관리자용 인덱싱 패널: 강제 재인덱싱(HQ) + 인덱싱 전/후 파일 목록 확인."""
    import importlib
    from pathlib import Path

    if st is None or not _is_admin_view():
        return

    with st.container(border=True):
        st.subheader("📚 인덱싱(관리자)")

        # dataset_dir 해석: label._resolve_dataset_dir(None) 우선
        def _resolve_dataset_dir_for_ui() -> Path:
            try:
                mod = importlib.import_module("src.rag.label")
                fn = getattr(mod, "_resolve_dataset_dir", None)
                if callable(fn):
                    return fn(None)
            except Exception:
                pass
            env = os.getenv("MAIC_DATASET_DIR") or os.getenv("RAG_DATASET_DIR")
            if env:
                return Path(env).expanduser()
            repo_root = Path(__file__).resolve().parent
            prepared = (repo_root / "prepared").resolve()
            if prepared.exists():
                return prepared
            return (repo_root / "knowledge").resolve()

        ds = _resolve_dataset_dir_for_ui()
        st.write(f"**Dataset Dir:** `{str(ds)}`")

        # 사전 스캔: 이번에 인덱싱 대상 파일 예비목록
        files: list[Path] = []
        try:
            rag = importlib.import_module("src.rag.search")
            SUP = getattr(rag, "SUPPORTED_EXTS", {".md", ".txt", ".pdf"})
            for p in sorted(ds.rglob("*")):
                if p.is_file() and p.suffix.lower() in SUP:
                    files.append(p)
        except Exception:
            pass

        with st.expander("이번에 인덱싱할 파일(예상)", expanded=bool(files)):
            if files:
                data = [{"title": p.stem, "path": str(p)} for p in files[:200]]
                st.dataframe(data, hide_index=True, use_container_width=True)
                if len(files) > 200:
                    st.caption(f"… 외 {len(files) - 200}개")
            else:
                st.info("대상 파일이 없거나 스캔에 실패했습니다.")

        col1, col2 = st.columns([1, 3])
        do_rebuild = col1.button("🔁 강제 재인덱싱(HQ)", help="캐시를 무시하고 인덱스를 새로 만듭니다.")
        show_after = col2.toggle("인덱싱 결과 표시", value=True)

        idx = None
        if do_rebuild:
            # 진행률 바(사전 스캔 개수 기준 가시화)
            total = max(1, len(files))
            prog = st.progress(0.0, text="인덱싱 중…")
            try:
                # 실제 재인덱싱(HQ)
                rebuild = getattr(rag, "rebuild_and_cache", None)
                if callable(rebuild):
                    idx = rebuild(str(ds))
                else:
                    build = getattr(rag, "build_index", None)
                    if callable(build):
                        idx = build(str(ds))
                # 진행률 완료 표시
                prog.progress(1.0, text="인덱싱 완료")
                st.success("강제 재인덱싱 완료 (HQ)")
            except Exception as e:
                prog.progress(0.0)
                _errlog(f"reindex failed: {e}", where="[admin-index.rebuild]", exc=e)
                st.error("강제 재인덱싱 중 오류가 발생했어요.")

        if show_after:
            try:
                if idx is None:
                    get_or = getattr(rag, "get_or_build_index", None)
                    if callable(get_or):
                        idx = get_or(str(ds), use_cache=True)
                docs = (idx or {}).get("docs", [])
                st.caption(f"인덱싱 문서 수: **{len(docs)}**")
                if docs:
                    data = [{"title": d.get("title"), "path": d.get("path")} for d in docs[:200]]
                    st.dataframe(data, hide_index=True, use_container_width=True)
                    if len(docs) > 200:
                        st.caption(f"… 외 {len(docs) - 200}개")
                else:
                    st.info("표시할 문서가 없어요.")
            except Exception as e:
                _errlog(f"list docs failed: {e}", where="[admin-index.list]", exc=e)
                st.error("문서 목록 표시 중 오류가 발생했어요.")
# ========================= [16] ADMIN: Index Panel — END =========================
