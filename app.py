# ========================= [00] HOOK: Admin Panel Launcher — START =========================
_render_admin_index_launcher()
# ========================= [00] HOOK: Admin Panel Launcher — END =========================

# [01] future import ==========================================================
from __future__ import annotations

# ========================= [02] ACCESS: Admin Gate — START =========================
def _is_admin_view() -> bool:
    """관리자 패널 표시 여부를 결정한다.
    - st.session_state['_diag'] 토글이 켜져 있으면 True
    - st.secrets.ADMIN_MODE == "1" 또는 ENV ADMIN_MODE == "1"이면 True
    - 그 외 False
    """
    import os

    try:
        # 세션 토글 우선
        if "st" in globals() and st is not None:
            try:
                if bool(st.session_state.get("_diag", False)):
                    return True
            except Exception:
                pass

            # 시크릿(배포 환경)
            try:
                val = str(st.secrets.get("ADMIN_MODE", "")).strip()
                if val == "1":
                    return True
            except Exception:
                pass

        # 환경변수(로컬/Actions)
        if os.getenv("ADMIN_MODE", "") == "1":
            return True
    except Exception:
        pass

    return False
# ========================= [02] ACCESS: Admin Gate — END =========================


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

# ==================== [05] UI: Index Panel Launcher — START =====================
def _render_admin_index_launcher() -> None:
    """상단 '진단 도구' 토글과 '인덱싱 패널([15]) 열기' 버튼.
    - 토글 켜짐 + 버튼 누름 → [15] 패널 렌더
    - 중복 렌더를 피하기 위해 session_state 키를 사용
    """
    if "st" not in globals() or st is None:
        return

    # 진단 도구 토글 (켜면 관리자 뷰 허용)
    st.toggle("🔧 진단 도구", value=st.session_state.get("_diag", False), key="_diag")

    c1, _c2 = st.columns([1, 6])
    if c1.button("🧰 인덱싱 패널([15]) 열기"):
        st.session_state["_open_admin_15"] = True

    # 조건 만족 시 [15] 렌더
    try:
        do_open = bool(st.session_state.get("_open_admin_15", False))
    except Exception:
        do_open = False

    if do_open and _is_admin_view():
        try:
            _render_admin_index_panel()
        except NameError:
            st.error("관리자 패널([15]) 함수를 찾을 수 없습니다.")
# ===================== [05] UI: Index Panel Launcher — END ======================


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
    - 관리자 로그인은 st.form으로 처리(Enter 제출 지원).
    - 로그인/로그아웃/닫기 시 즉시 rerun으로 모달을 닫는다.
    """
    st_mod = globals().get("st", None)
    if st_mod is None:
        return

    st = st_mod
    ss = st.session_state
    ss.setdefault("admin_mode", False)
    ss.setdefault("_show_admin_login", False)

    # 상태 배지
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

    st.markdown(
        """
        <style>
          .status-btn { padding: 4px 8px; border-radius: 8px; font-weight: 600; }
          .status-btn.green { background:#e7f7ee; color:#117a38; }
          .status-btn.yellow{ background:#fff6e5; color:#8a5b00; }
          .status-btn.red   { background:#ffeaea; color:#a40000; }
          .brand-title { font-weight:800; letter-spacing:.2px; }
          .admin-login-narrow [data-testid="stTextInput"] input{ height:42px; border-radius:10px; }
          .admin-login-narrow .stButton>button{ width:100%; height:42px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 3, 1], gap="small")
    with c1:
        st.markdown(f'<span class="status-btn {badge_class}">{badge_txt}</span>', unsafe_allow_html=True)
    with c2:
        st.markdown('<span class="brand-title">LEES AI Teacher</span>', unsafe_allow_html=True)
    with c3:
        if ss.get("admin_mode"):
            if st.button("🚪 로그아웃", key="logout_now", help="관리자 로그아웃"):
                ss["admin_mode"] = False
                ss["_show_admin_login"] = False
                st.toast("로그아웃 완료", icon="👋") if hasattr(st, "toast") else st.success("로그아웃 완료")
                st.rerun()
        else:
            if st.button("⚙️", key="open_admin_login", help="관리자 로그인"):
                ss["_show_admin_login"] = not ss.get("_show_admin_login", False)

    # 로그인 폼(Enter 제출 시 자동 닫힘)
    if not ss.get("admin_mode") and ss.get("_show_admin_login"):
        with st.container(border=True):
            st.write("🔐 관리자 로그인")
            # 🔑 비번 소스(순서): secrets → env
            try:
                pwd_set = (
                    _from_secrets("ADMIN_PASSWORD", None)
                    or _from_secrets("APP_ADMIN_PASSWORD", None)
                    or _from_secrets("MAIC_ADMIN_PASSWORD", None)
                    or os.getenv("ADMIN_PASSWORD")
                    or os.getenv("APP_ADMIN_PASSWORD")
                    or os.getenv("MAIC_ADMIN_PASSWORD")
                    or None
                )
            except Exception:
                pwd_set = None

            left, mid, right = st.columns([2, 1, 2])
            with mid:
                with st.form("admin_login_form", clear_on_submit=False):
                    st.markdown('<div class="admin-login-narrow">', unsafe_allow_html=True)
                    pw = st.text_input("비밀번호", type="password", key="admin_pw_input", help="Enter로 로그인")
                    col_a, col_b = st.columns([1, 1])
                    submit = col_a.form_submit_button("로그인")
                    cancel = col_b.form_submit_button("닫기")
                    st.markdown('</div>', unsafe_allow_html=True)

                if cancel:
                    ss["_show_admin_login"] = False
                    st.rerun()

                if submit:
                    if not pwd_set:
                        st.error("서버에 관리자 비밀번호가 설정되어 있지 않습니다.")
                    elif pw and str(pw) == str(pwd_set):
                        ss["admin_mode"] = True
                        ss["_show_admin_login"] = False
                        st.toast("로그인 성공", icon="✅") if hasattr(st, "toast") else st.success("로그인 성공")
                        st.rerun()  # ← Enter 제출 포함 즉시 닫힘
                    else:
                        st.error("비밀번호가 올바르지 않습니다.")
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


# ========================== [12] 채팅 UI(스타일/모드/상단) — START ==========================
def _inject_chat_styles_once() -> None:
    """전역 CSS: 카톡형 입력(인풋 내부 우측 ➤), 말풍선/칩, 모드 pill."""
    if st is None:
        return
    # v2 키로 강제 재주입 (이전 키가 True여서 스킵되던 문제 방지)
    if st.session_state.get("_chat_styles_injected_v2"):
        return
    st.session_state["_chat_styles_injected_v2"] = True

    st.markdown(
        """
    <style>
      /* ChatPane(메시지 영역) */
      .chatpane{
        position:relative;
        background:#EDF4FF; border:1px solid #D5E6FF; border-radius:18px;
        padding:10px; margin-top:12px;
      }
      .chatpane .messages{ max-height:60vh; overflow-y:auto; padding:8px; }

      /* 모드 pill */
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

      /* ─────────────────────────────────────────────────────────────────────
         카톡형 입력(핵심):
         - Streamlit의 마크다운 래퍼(<div class="chatpane">)는 실제로 폼의 부모가 아닙니다.
         - 따라서 .chatpane form[...] 선택자는 먹지 않았습니다.
         - 실 DOM 기준으로 '질문 인풋을 가진 폼'만 정확히 타깃팅합니다.
         - 최신 크롬에서 지원하는 :has() 사용. (관리자 로그인 폼 등에는 영향 없음)
         ───────────────────────────────────────────────────────────────────── */
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) {
        position:relative; background:#EDF4FF; padding:8px 10px 10px 10px; margin:0;
      }
      /* 인풋에 버튼 자리 확보 */
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) [data-testid="stTextInput"] input{
        background:#FFF8CC !important; border:1px solid #F2E4A2 !important; border-radius:999px !important;
        color:#333 !important; height:46px; padding-right:56px;
      }
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) ::placeholder{ color:#8A7F4A !important; }

      /* 제출 버튼 컨테이너(stButton)를 폼 기준으로 절대배치(다양한 DOM 변형 대응) */
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .stButton,
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .row-widget.stButton{
        position:absolute; right:14px; top:50%; transform:translateY(-50%);
        z-index:2; margin:0!important; padding:0!important;
      }
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .stButton > button,
      form[data-testid="stForm"]:has(input[placeholder='질문을 입력하세요…']) .row-widget.stButton > button{
        width:38px; height:38px; border-radius:50%; border:0; background:#0a2540; color:#fff;
        font-size:18px; line-height:1; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.15);
        padding:0; min-height:0;
      }

      /* 말풍선 */
      .msg-row{ display:flex; margin:8px 0; }
      .msg-row.left{ justify-content:flex-start; }
      .msg-row.right{ justify-content:flex-end; }
      .bubble{
        max-width:88%; padding:10px 12px; border-radius:16px; line-height:1.6; font-size:15px;
        box-shadow:0 1px 1px rgba(0,0,0,.05); white-space:pre-wrap; position:relative;
      }
      .bubble.user{ border-top-right-radius:8px; border:1px solid #F2E4A2; background:#FFF8CC; color:#333; }
      .bubble.ai  { border-top-left-radius:8px;  border:1px solid #BEE3FF; background:#EAF6FF; color:#0a2540; }

      /* 칩(이름) + 출처 */
      .chip{
        display:inline-block; margin:-2px 0 6px 0; padding:2px 10px; border-radius:999px;
        font-size:12px; font-weight:700; color:#fff; line-height:1;
      }
      .chip.me{ background:#059669; }   /* 나 */
      .chip.pt{ background:#2563eb; }   /* 피티쌤 */
      .chip.mn{ background:#7c3aed; }   /* 미나쌤 */
      .chip-src{
        display:inline-block; margin-left:6px; padding:2px 8px; border-radius:10px;
        background:#eef2ff; color:#3730a3; font-size:12px; font-weight:600; line-height:1;
        border:1px solid #c7d2fe; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        vertical-align:middle;
      }

      @media (max-width:480px){
        .bubble{ max-width:96%; }
        .chip-src{ max-width:160px; }
      }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _render_mode_controls_pills() -> str:
    """질문 모드 pill (ChatPane 상단). 반환: '문법'|'문장'|'지문'"""
    _inject_chat_styles_once()
    ss = st.session_state
    labels = ["문법", "문장", "지문"]
    cur = ss.get("qa_mode_radio") or "문법"
    idx = labels.index(cur) if cur in labels else 0
    sel = st.radio("질문 모드", options=labels, index=idx, horizontal=True, label_visibility="collapsed")
    ss["qa_mode_radio"] = sel
    return sel
# =========================== [12] 채팅 UI(스타일/모드/상단) — END ===========================


# ============================ [13] 채팅 패널 — START ============================
# 질문(오른쪽, 연노랑) → 피티쌤(왼쪽, 연하늘, 스트리밍) → 미나쌤(왼쪽, 연하늘, 스트리밍)
def _render_chat_panel() -> None:
    import importlib as _imp
    import html, re
    from typing import Optional
    import streamlit as st

    # 출처 라벨러
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

    def _emit_bubble(placeholder, who: str, acc_text: str,
                     *, source: Optional[str], align_right: bool) -> None:
        side_cls = "right" if align_right else "left"
        klass = "user" if align_right else "ai"
        chips = _chip_html(who) + (_src_html(source) if not align_right else "")
        html_block = (
            f'<div class="msg-row {side_cls}">'
            f'  <div class="bubble {klass}">{chips}<br/>{_esc(acc_text)}</div>'
            f'</div>'
        )
        placeholder.markdown(html_block, unsafe_allow_html=True)

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

    # 1) 사용자 말풍선(오른쪽, 연노랑)
    ph_user = st.empty()
    _emit_bubble(ph_user, "나", question, source=None, align_right=True)

    # 2) 피티쌤(왼쪽, 연하늘, 스트리밍)
    ph_ans = st.empty()
    acc_ans = ""

    def _on_emit_ans(chunk: str) -> None:
        nonlocal acc_ans
        acc_ans += str(chunk or "")
        _emit_bubble(ph_ans, "피티쌤", acc_ans, source=src_label, align_right=False)

    emit_chunk_ans, close_stream_ans = make_stream_handler(
        on_emit=_on_emit_ans,
        opts=BufferOptions(
            min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
            flush_on_strong_punct=True, flush_on_newline=True,
        ),
    )
    for piece in answer_stream(question=question, mode=ss.get("__mode", "")):
        emit_chunk_ans(str(piece or ""))
    close_stream_ans()
    full_answer = acc_ans.strip() or "(응답이 비어있어요)"

    # 3) 미나쌤(왼쪽, 연하늘, 스트리밍)
    ph_eval = st.empty()
    acc_eval = ""

    def _on_emit_eval(chunk: str) -> None:
        nonlocal acc_eval
        acc_eval += str(chunk or "")
        _emit_bubble(ph_eval, "미나쌤", acc_eval, source=src_label, align_right=False)

    emit_chunk_eval, close_stream_eval = make_stream_handler(
        on_emit=_on_emit_eval,
        opts=BufferOptions(
            min_emit_chars=8, soft_emit_chars=24, max_latency_ms=150,
            flush_on_strong_punct=True, flush_on_newline=True,
        ),
    )
    for piece in evaluate_stream(
        question=question, mode=ss.get("__mode", ""),
        answer=full_answer, ctx={"answer": full_answer},
    ):
        emit_chunk_eval(str(piece or ""))
    close_stream_eval()

    # 중복 방지
    ss["last_q"] = question
    ss["inpane_q"] = ""
# ============================= [13] 채팅 패널 — END =============================

# ============================ [14] 본문 렌더 — START ============================
def _render_body() -> None:
    if st is None:
        return

    # 1) 부팅 오토플로우 1회
    if not st.session_state.get("_boot_checked"):
        try:
            _boot_autoflow_hook()
        except Exception as e:
            _errlog(f"boot check failed: {e}", where="[render_body.boot]", exc=e)
        finally:
            st.session_state["_boot_checked"] = True

    # 2) 배경
    _mount_background(
        theme="light", accent="#5B8CFF", density=3, interactive=True, animate=True,
        gradient="radial", grid=True, grain=False, blur=0, seed=1234, readability_veil=True,
    )

    # 3) 헤더
    _header()

    # 4) 빠른 부팅 훅
    try:
        _qlao = globals().get("_quick_local_attach_only")
        if callable(_qlao):
            _qlao()
    except Exception as e:
        _errlog(f"quick attach failed: {e}", where="[render_body]", exc=e)

    # 5) 관리자 패널(존재할 때만 호출; 경고 오탐 방지)
    if _is_admin_view():
        _render_admin_panels()

        idx_panel = globals().get("_render_admin_index_panel")
        if callable(idx_panel):
            idx_panel()
        else:
            # 섹션 번호 확정: [15]
            st.info("관리자 인덱싱 패널이 비활성화되어 있습니다. [15] 구획이 없거나 주입되지 않았습니다.")

        idx_sources = globals().get("_render_admin_indexed_sources_panel")
        if callable(idx_sources):
            idx_sources()

        st.caption("ⓘ 복구/재인덱싱은 ‘🛠 진단 도구’ 또는 인덱싱 패널에서 수행할 수 있어요.")

    # 6) 자동 시작
    _auto_start_once()

    # 7) 채팅(위): 말풍선 영역
    _inject_chat_styles_once()
    with st.container():
        st.markdown('<div class="chatpane"><div class="messages">', unsafe_allow_html=True)
        try:
            _render_chat_panel()
        except Exception as e:
            _errlog(f"chat panel failed: {e}", where="[render_body.chat]", exc=e)
        st.markdown('</div></div>', unsafe_allow_html=True)

    # 8) 입력 폼
    with st.container(border=True, key="chatpane_container"):
        st.markdown('<div class="chatpane">', unsafe_allow_html=True)
        st.session_state["__mode"] = _render_mode_controls_pills() or st.session_state.get("__mode", "")
        with st.form("chat_form", clear_on_submit=False):
            q: str = st.text_input("질문", placeholder="질문을 입력하세요…", key="q_text")
            submitted: bool = st.form_submit_button("➤")
        st.markdown('</div>', unsafe_allow_html=True)

    # 9) 제출 처리
    if submitted and isinstance(q, str) and q.strip():
        st.session_state["inpane_q"] = q.strip()
        st.rerun()
    else:
        st.session_state.setdefault("inpane_q", "")
# ============================= [14] 본문 렌더 — END =============================
# ========================= [15] ADMIN: Index Panel — START =========================
def _render_admin_index_panel() -> None:
    """관리자 인덱싱 패널 (prepared 전용 + 스텝/진행바/로그/스톨표시)
    - prepared(Drive) 목록 미리보기
    - 🔁 강제 재인덱싱(HQ, prepared only)
    - prepared 신규파일 소비(seen)
    - 인덱스 요약 및 경로 불일치 진단
    - 로컬 ZIP 백업 / GitHub Releases 업로드 (자동/수동)
    - 스텝 라이트 + 단계형 진행바 + 라이브 로그 + STALLED 표시
    """
    import importlib
    import importlib.util
    import json
    import os
    import time
    import zipfile
    from pathlib import Path
    from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
    from urllib import request, error, parse

    if TYPE_CHECKING:
        from src.rag.index_status import IndexSummary as _IndexSummary

    if "st" not in globals() or st is None or not _is_admin_view():
        return

    st.markdown(
        "<div style='margin-top:0.5rem'></div>"
        "<h3>🧭 인덱싱(관리자: prepared 전용)</h3>",
        unsafe_allow_html=True,
    )

    # ── 안전 래퍼(앱 외부 훅이 없을 때 NameError 방지) ───────────────────────
    def _errlog_safe(msg: str, where: str = "") -> None:
        try:
            _errlog(msg, where=where)  # type: ignore[name-defined]
        except Exception:
            pass

    def _persist_dir_safe() -> Path:
        try:
            p = _persist_dir()  # type: ignore[name-defined]
            return Path(str(p)).expanduser()
        except Exception:
            return Path.home() / ".maic" / "persist"

    def _mark_ready_safe() -> None:
        try:
            _mark_ready()  # type: ignore[name-defined]
        except Exception:
            pass

    # ── UI 플레이스홀더(항상 같은 자리 덮어쓰기 → 중복 렌더 제거) ─────────────
    if "_IDX_PH_STEPS" not in st.session_state:
        st.session_state["_IDX_PH_STEPS"] = st.empty()
    if "_IDX_PH_STATUS" not in st.session_state:
        st.session_state["_IDX_PH_STATUS"] = st.empty()
    if "_IDX_PH_BAR" not in st.session_state:
        st.session_state["_IDX_PH_BAR"] = st.empty()
    if "_IDX_PH_LOG" not in st.session_state:
        st.session_state["_IDX_PH_LOG"] = st.empty()

    # ── 스텝/로그 헬퍼 ─────────────────────────────────────────────────────
    step_names: List[str] = [
        "스캔", "Persist확정", "인덱싱", "prepared소비", "요약/배지", "ZIP/Release"
    ]
    stall_threshold_sec = 60  # 마지막 업데이트 이후 60초 이상이면 STALLED

    def _step_reset(names: List[str]) -> None:
        st.session_state["_IDX_STEPS"] = [
            {"name": n, "state": "idle", "note": ""} for n in names
        ]
        st.session_state["_IDX_LOG"] = []
        st.session_state["_IDX_PROG"] = 0.0
        st.session_state["_IDX_START_TS"] = time.time()
        st.session_state["_IDX_LAST_TS"] = time.time()

    def _steps() -> List[Dict[str, str]]:
        if "_IDX_STEPS" not in st.session_state:
            _step_reset(step_names)
        return list(st.session_state["_IDX_STEPS"])

    def _touch() -> None:
        st.session_state["_IDX_LAST_TS"] = time.time()
        _render_status()

    def _step_set(idx: int, state: str, note: str = "") -> None:
        steps = _steps()
        if 0 <= idx < len(steps):
            steps[idx]["state"] = state
            if note:
                steps[idx]["note"] = note
            st.session_state["_IDX_STEPS"] = steps
            _touch()
            _render_stepper()
            _update_progress()

    def _icon(state: str) -> str:
        return {"idle": "⚪", "run": "🔵", "ok": "🟢", "fail": "🔴", "skip": "⚪"}.get(
            state, "⚪"
        )

    def _render_stepper() -> None:
        steps = _steps()
        lines = []
        for i, s in enumerate(steps, start=1):
            note = f" — {s.get('note','')}" if s.get("note") else ""
            lines.append(f"{_icon(s['state'])} {i}. {s['name']}{note}")
        st.session_state["_IDX_PH_STEPS"].markdown(
            "\n".join([f"- {ln}" for ln in lines])
        )

    def _is_running() -> bool:
        return any(s["state"] == "run" for s in _steps())

    def _render_status() -> None:
        now = time.time()
        last = float(st.session_state.get("_IDX_LAST_TS", now))
        start = float(st.session_state.get("_IDX_START_TS", now))
        since_last = int(now - last)
        since_start = int(now - start)
        running = _is_running()
        stalled = running and since_last >= stall_threshold_sec
        if stalled:
            text = (
                f"🟥 **STALLED** · 마지막 업데이트 {since_last}s 전 · 총 경과 {since_start}s"
            )
        elif running:
            text = f"🟦 RUNNING · 마지막 업데이트 {since_last}s 전 · 총 경과 {since_start}s"
        else:
            text = f"🟩 IDLE/COMPLETE · 총 경과 {since_start}s"
        st.session_state["_IDX_PH_STATUS"].markdown(text)

    def _update_progress() -> None:
        steps = _steps()
        done = sum(1 for s in steps if s["state"] in ("ok", "skip"))
        prog = done / len(steps)
        st.session_state["_IDX_PROG"] = prog
        bar = st.session_state.get("_IDX_BAR")
        if bar is None:
            st.session_state["_IDX_BAR"] = st.session_state["_IDX_PH_BAR"].progress(
                prog, text="진행률"
            )
        else:
            try:
                bar.progress(prog)
            except Exception:
                st.session_state["_IDX_BAR"] = (
                    st.session_state["_IDX_PH_BAR"].progress(prog, text="진행률")
                )

    def _log(msg: str, level: str = "info") -> None:
        buf: List[str] = st.session_state.get("_IDX_LOG", [])
        prefix = {"info": "•", "warn": "⚠", "err": "✖"}.get(level, "•")
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {prefix} {msg}"
        buf.append(line)
        if len(buf) > 200:
            buf = buf[-200:]
        st.session_state["_IDX_LOG"] = buf
        st.session_state["_IDX_PH_LOG"].text("\n".join(buf))
        _touch()

    # 초기 렌더(중복 출력 방지: 플레이스홀더만 사용)
    _render_stepper()
    _render_status()
    _update_progress()

    # ── GH 업로드/백업 헬퍼 ────────────────────────────────────────────────
    def _secret(name: str, default: str = "") -> str:
        try:
            v = st.secrets.get(name)
            if isinstance(v, str) and v:
                return v
        except Exception:
            pass
        return os.getenv(name, default)

    def _resolve_owner_repo() -> Tuple[str, str]:
        owner = _secret("GH_OWNER")
        repo = _secret("GH_REPO")
        if owner and repo:
            return owner, repo
        combo = _secret("GITHUB_REPO")
        if combo and "/" in combo:
            o, r = combo.split("/", 1)
            return o.strip(), r.strip()
        owner = owner or _secret("GITHUB_OWNER")
        repo = repo or _secret("GITHUB_REPO_NAME")
        return owner or "", repo or ""

    def _all_gh_secrets() -> bool:
        tok = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
        ow, rp = _resolve_owner_repo()
        return bool(tok and ow and rp)

    def _zip_index_dir(idx_dir: Path, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        zname = f"index_{ts}.zip"
        zpath = out_dir / zname
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _d, _f in os.walk(str(idx_dir)):
                for fn in _f:
                    p = Path(root) / fn
                    arc = str(p.relative_to(idx_dir))
                    try:
                        zf.write(str(p), arcname=arc)
                    except Exception:
                        pass
        return zpath

    def _gh_api(url: str, token: str, data: Optional[bytes], method: str,
                ctype: str) -> Dict[str, Any]:
        """GitHub REST API 호출 헬퍼."""
        req = request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github+json")
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with request.urlopen(req, timeout=30) as resp:
                txt = resp.read().decode("utf-8", "ignore")
                try:
                    return json.loads(txt)
                except Exception:
                    return {"_raw": txt}
        except error.HTTPError as e:
            # ✅ 여분의 ')' 제거된 문법 버그 픽스
            return {"_error": f"HTTP {e.code}", "detail": e.read().decode()}
        except Exception:
            return {"_error": "network_error"}

    def _upload_release_zip(
        owner: str, repo: str, token: str, tag: str, zip_path: Path,
        name: Optional[str] = None, body: str = ""
    ) -> Dict[str, Any]:
        api = "https://api.github.com"
        get_url = f"{api}/repos/{owner}/{repo}/releases/tags/{parse.quote(tag)}"
        rel = _gh_api(get_url, token, None, "GET", "")
        if "_error" in rel:
            payload = json.dumps(
                {"tag_name": tag, "name": name or tag, "body": body}
            ).encode("utf-8")
            rel = _gh_api(
                f"{api}/repos/{owner}/{repo}/releases",
                token,
                payload,
                "POST",
                "application/json",
            )
            if "_error" in rel:
                return rel

        rid = rel.get("id")
        if not rid:
            return {"_error": "no_release_id"}

        up_url = (
            f"https://uploads.github.com/repos/{owner}/{repo}/releases/{rid}/assets"
            f"?name={parse.quote(zip_path.name)}"
        )
        try:
            data = zip_path.read_bytes()
        except Exception:
            return {"_error": "zip_read_failed"}

        req = request.Request(up_url, data=data, method="POST")
        req.add_header("Authorization", f"token {token}")
        req.add_header("Content-Type", "application/zip")
        req.add_header("Accept", "application/vnd.github+json")
        try:
            with request.urlopen(req, timeout=60) as resp:
                txt = resp.read().decode("utf-8", "ignore")
                try:
                    return json.loads(txt)
                except Exception:
                    return {"_raw": txt}
        except error.HTTPError as e:
            return {"_error": f"HTTP {e.code}", "detail": e.read().decode()}
        except Exception:
            return {"_error": "network_error"}

    # ── prepared API / 목록 로더 ────────────────────────────────────────────
    def _load_prepared_api() -> Tuple[
        Optional[Callable[..., Dict[str, Any]]],
        Optional[Callable[..., None]],
        List[str],
    ]:
        tried: List[str] = []

        def _try(modname: str) -> Tuple[
            Optional[Callable[..., Dict[str, Any]]], Optional[Callable[..., None]]
        ]:
            try:
                m = importlib.import_module(modname)
                chk_fn = getattr(m, "check_prepared_updates", None)
                mark_fn = getattr(m, "mark_prepared_consumed", None)
                if callable(chk_fn) and callable(mark_fn):
                    tried.append(f"ok: {modname}")
                    return chk_fn, mark_fn
                tried.append(f"miss attrs: {modname}")
                return None, None
            except Exception as e:
                tried.append(f"fail: {modname} ({e})")
                return None, None

        for name in ("prepared", "gdrive"):
            chk, mark = _try(name)
            if chk and mark:
                return chk, mark, tried

        for name in ("src.prepared", "src.drive.prepared", "src.integrations.gdrive"):
            chk, mark = _try(name)
            if chk and mark:
                return chk, mark, tried

        repo = Path(__file__).resolve().parent
        for fname in ("prepared.py", "gdrive.py"):
            path = (repo / fname)
            if path.exists():
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"_dyn_{fname[:-3]}", str(path)
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        chk = getattr(mod, "check_prepared_updates", None)
                        mark = getattr(mod, "mark_prepared_consumed", None)
                        if callable(chk) and callable(mark):
                            tried.append(f"ok: {path}")
                            return chk, mark, tried
                        tried.append(f"miss attrs: {path}")
                except Exception as e:
                    tried.append(f"fail: {path} ({e})")
        return None, None, tried

    def _load_prepared_lister() -> Tuple[
        Optional[Callable[[], List[Dict[str, Any]]]], List[str]
    ]:
        tried: List[str] = []

        def _try(modname: str) -> Optional[Callable[[], List[Dict[str, Any]]]]:
            try:
                m = importlib.import_module(modname)
                fn = getattr(m, "list_prepared_files", None)
                if callable(fn):
                    tried.append(f"ok: {modname}")
                    return fn
                tried.append(f"miss func: {modname}")
                return None
            except Exception as e:
                tried.append(f"fail: {modname} ({e})")
                return None

        for name in ("src.integrations.gdrive", "gdrive"):
            fn = _try(name)
            if fn:
                return fn, tried
        return None, tried

    # ── prepared 목록 미리보기 (스캔 스텝) ──────────────────────────────────
    st.caption("※ 이 패널은 Drive의 prepared만을 입력원으로 사용합니다.")
    files_list: List[Dict[str, Any]] = []
    lister, dbg1 = _load_prepared_lister()
    if lister:
        try:
            _step_set(0, "run", "prepared 목록 수집 중")
            files_list = lister() or []
            _step_set(0, "ok", f"{len(files_list)}건")
            _log(f"prepared 목록 {len(files_list)}건")
        except Exception as e:
            _step_set(0, "fail", "목록 수집 실패")
            _log(f"prepared list failed: {e}", "err")
    else:
        st.warning("prepared 목록 함수를 찾지 못했습니다.")
        for m in dbg1:
            st.write("• " + m)
        _step_set(0, "fail", "목록 함수 없음")
        _log("prepared 목록 함수를 찾지 못했습니다.", "warn")

    with st.expander("이번에 인덱싱할 prepared 파일(예상)", expanded=False):
        st.write(f"총 {len(files_list)}건 (표시는 최대 400건)")
        if files_list:
            rows = []
            for rec in files_list[:400]:
                name = str(rec.get("name") or rec.get("path") or rec.get("file") or "")
                fid = str(rec.get("id") or rec.get("fileId") or "")
                rows.append({"name": name, "id": fid})
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("일치하는 파일이 없습니다.")

    # ── 실행 컨트롤 ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
    do_rebuild = c1.button(
        "🔁 강제 재인덱싱(HQ, prepared)",
        help="Drive prepared만 사용하여 인덱스를 새로 만듭니다.",
    )
    show_after = c2.toggle("인덱싱 결과 표시", value=True)
    auto_up = c3.toggle(
        "인덱싱 후 자동 ZIP 업로드",
        value=_all_gh_secrets(),
        help="GH/GITHUB 시크릿이 모두 있으면 기본 켜짐",
    )
    reset_view = c4.button("🧹 화면 초기화")

    if reset_view:
        _step_reset(step_names)
        _render_stepper()
        _render_status()
        st.session_state["_IDX_BAR"] = None
        st.session_state["_IDX_PH_BAR"].empty()
        st.session_state["_IDX_PH_LOG"].empty()
        _log("화면 상태를 초기화했습니다.")

    # ── 강제 인덱싱(HQ: prepared only) ────────────────────────────────────
    used_persist: Optional[Path] = None
    if do_rebuild:
        _step_reset(step_names)
        _render_stepper()
        _render_status()
        st.session_state["_IDX_BAR"] = None
        st.session_state["_IDX_PH_BAR"].empty()
        st.session_state["_IDX_PH_LOG"].empty()
        _log("인덱싱 시작")
        try:
            from src.rag import index_build as _idx

            _step_set(1, "run", "persist 확인 중")
            try:
                from src.rag.index_build import PERSIST_DIR as _pp
                used_persist = Path(str(_pp)).expanduser()
            except Exception:
                used_persist = Path.home() / ".maic" / "persist"
            _step_set(1, "ok", str(used_persist))
            _log(f"persist={used_persist}")

            _step_set(2, "run", "HQ 인덱싱 중")
            os.environ["MAIC_INDEX_MODE"] = "HQ"
            os.environ["MAIC_USE_PREPARED_ONLY"] = "1"
            _idx.rebuild_index()
            _step_set(2, "ok", "완료")
            _log("인덱싱 완료")

            cj = used_persist / "chunks.jsonl"
            if cj.exists() and cj.stat().st_size > 0:
                try:
                    _mark_ready_safe()
                except Exception:
                    try:
                        (used_persist / ".ready").write_text("ok", encoding="utf-8")
                    except Exception:
                        pass

            _step_set(3, "run", "prepared 소비 중")
            try:
                persist_for_seen = used_persist or _persist_dir_safe()
                chk, mark, dbg2 = _load_prepared_api()
                info: Dict[str, Any] = {}
                new_files: List[str] = []
                files_arg: Any = files_list or []
                if callable(chk):
                    try:
                        info = chk(persist_for_seen, files_arg) or {}
                    except TypeError:
                        try:
                            info = chk(persist_for_seen) or {}
                        except Exception:
                            info = {}
                    try:
                        new_files = list(info.get("files") or [])
                    except Exception:
                        new_files = []
                else:
                    for m in dbg2:
                        _log("• " + m, "warn")
                if new_files and callable(mark):
                    try:
                        mark(persist_for_seen, new_files)
                    except TypeError:
                        mark(new_files)
                    _log(f"소비(seen) {len(new_files)}건")
                _step_set(3, "ok", f"{len(new_files)}건")
            except Exception as e:
                _step_set(3, "fail", "소비 실패")
                _log(f"prepared 소비 실패: {e}", "err")

            _step_set(4, "run", "요약 계산")
            try:
                from src.rag.index_status import get_index_summary
                summary2 = get_index_summary(used_persist)
                note = (
                    f"files={summary2.total_files}, chunks={summary2.total_chunks}"
                )
                _step_set(4, "ok", note)
                _log(f"요약 {note}")
            except Exception:
                _step_set(4, "ok", "요약 모듈 없음")
                _log("요약 모듈 없음", "warn")

            if auto_up and _all_gh_secrets():
                _step_set(5, "run", "ZIP/Release 업로드")
                owner, repo_name = _resolve_owner_repo()
                token = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
                if owner and repo_name and token:
                    idx_dir = used_persist or _persist_dir_safe()
                    backup_dir = idx_dir / "backups"
                    z = _zip_index_dir(idx_dir, backup_dir)
                    tag = f"index-{int(time.time())}"
                    res = _upload_release_zip(
                        owner, repo_name, token, tag, z, name=tag, body="MAIC index"
                    )
                    if "_error" in res:
                        _step_set(5, "fail", res.get("_error", "error"))
                        if "detail" in res:
                            with st.expander("상세 오류"):
                                st.code(res["detail"])
                        _log(f"업로드 실패: {res.get('_error')}", "err")
                    else:
                        _step_set(5, "ok", "업로드 완료")
                        url = res.get("browser_download_url")
                        if url:
                            st.write(f"다운로드: {url}")
                        _log("업로드 완료")
                else:
                    _step_set(5, "skip", "시크릿 없음")
                    _log("시크릿 없어 업로드 생략", "warn")
            else:
                _step_set(5, "skip", "자동 업로드 꺼짐")
                _log("자동 업로드 꺼짐")

            st.success("강제 재인덱싱 완료 (prepared 전용)")
        except Exception as e:
            _step_set(2, "fail", "인덱싱 실패")
            _log(f"인덱싱 실패: {e}", "err")
            _errlog_safe(f"reindex failed: {e}", where="[admin-index.rebuild]")
            st.error("강제 재인덱싱 중 오류가 발생했어요.")
        finally:
            try:
                if used_persist is not None and st is not None:
                    st.session_state["_PERSIST_DIR"] = used_persist
            except Exception:
                pass

    # ── 인덱싱 후 요약 & 경로 불일치 진단 ──────────────────────────────────
    if show_after:
        try:
            from src.rag.index_build import PERSIST_DIR as _px
            idx_persist = Path(str(_px)).expanduser()
        except Exception:
            idx_persist = Path.home() / ".maic" / "persist"
        glb_persist = _persist_dir_safe()

        st.write(f"**Persist(Indexer):** `{str(idx_persist)}`")
        st.write(f"**Persist(Global):** `{str(glb_persist)}`")
        if str(idx_persist) != str(glb_persist):
            st.warning("Persist 경로가 서로 다릅니다. 설정/부팅 훅을 점검하세요.")

        summary: Optional["_IndexSummary"] = None
        try:
            from src.rag.index_status import get_index_summary
            summary = get_index_summary(idx_persist)
        except Exception:
            summary = None

        if summary:
            ready_txt = "Yes" if summary.ready else "No"
            st.caption(
                f"요약: ready={ready_txt} · files={summary.total_files} "
                f"· chunks={summary.total_chunks}"
            )
            if summary.sample_files:
                with st.expander("샘플 파일(최대 3개)", expanded=False):
                    rows = [{"path": s} for s in summary.sample_files]
                    st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            cj = idx_persist / "chunks.jsonl"
            rd = (idx_persist / ".ready").exists()
            if cj.exists():
                st.caption("요약 모듈 없음: chunks.jsonl 존재")
                if not rd:
                    st.info(".ready 파일이 없어 준비 상태가 미완성입니다.")
            else:
                st.info("`chunks.jsonl`이 아직 없어 결과를 표시할 수 없습니다.")

    # ── 라이브 로그 보기 ───────────────────────────────────────────────────
    with st.expander("실시간 로그 (최근 200줄)", expanded=False):
        buf: List[str] = st.session_state.get("_IDX_LOG", [])
        if buf:
            st.text("\n".join(buf))
        else:
            st.caption("표시할 로그가 없습니다.")

    # ── 수동 백업/업로드 UI ────────────────────────────────────────────────
    with st.expander("백업 / 업로드(Zip)", expanded=False):
        ow_r, rp_r = _resolve_owner_repo()
        token_r = _secret("GH_TOKEN") or _secret("GITHUB_TOKEN")
        owner = st.text_input("GitHub Owner", ow_r)
        repo_name = st.text_input("GitHub Repo", rp_r)
        token = st.text_input("GitHub Token", token_r)
        default_tag = f"index-{int(time.time())}"
        tag = st.text_input("Release Tag", default_tag)
        try:
            from src.rag.index_build import PERSIST_DIR as _px
            idx_persist2 = Path(str(_px)).expanduser()
        except Exception:
            idx_persist2 = Path.home() / ".maic" / "persist"
        local_dir = st.text_input(
            "Local Backup Dir", str((idx_persist2 / "backups").resolve())
        )

        c1, c2 = st.columns([1, 1])
        act_zip = c1.button("📦 로컬 ZIP 백업 만들기")
        act_up = c2.button("⬆ Releases에 업로드(Zip)")

        if act_zip:
            z = _zip_index_dir(idx_persist2, Path(local_dir))
            if z.exists() and z.stat().st_size > 0:
                st.success(f"ZIP 생성 완료: `{str(z)}`")
            else:
                st.error("ZIP 생성에 실패했습니다.")

        if act_up:
            if not owner or not repo_name or not token:
                st.error("Owner/Repo/Token을 입력해 주세요.")
            else:
                z = _zip_index_dir(idx_persist2, Path(local_dir))
                st.caption(f"업로드 대상 ZIP: `{z.name}`")
                res = _upload_release_zip(
                    owner, repo_name, token, tag, z, name=tag, body="MAIC index"
                )
                if "_error" in res:
                    st.error(f"업로드 실패: {res.get('_error')}")
                    if "detail" in res:
                        with st.expander("상세 오류"):
                            st.code(res["detail"])
                else:
                    st.success("업로드 성공")
                    browser = res.get("browser_download_url")
                    if browser:
                        st.write(f"다운로드: {browser}")
# ========================= [15] ADMIN: Index Panel — END =========================


# ========================= [16] Indexed Sources Panel — START ==========================
def _render_admin_indexed_sources_panel() -> None:
    """
    현재 인덱스(chunks.jsonl)를 읽어 문서 단위로 집계/표시.
    열: 제목 · 경로(source) · (고유)문서ID · 청크수 요약
    """
    import json
    from pathlib import Path
    from typing import Any, Dict, List

    if st is None or not _is_admin_view():
        return

    # --- PERSIST_DIR 결정 ---
    def _persist_dir() -> Path:
        try:
            from src.rag.index_build import PERSIST_DIR as IDX_DIR
            return Path(str(IDX_DIR)).expanduser()
        except Exception:
            pass
        try:
            from src.config import PERSIST_DIR as CFG_DIR
            return Path(str(CFG_DIR)).expanduser()
        except Exception:
            pass
        return Path.home() / ".maic" / "persist"

    persist = _persist_dir()
    chunks_path = persist / "chunks.jsonl"

    with st.container(border=True):
        st.subheader("📄 인덱싱된 파일 목록 (읽기 전용)")
        st.caption(f"경로: `{str(chunks_path)}`")

        # 파일 존재 확인
        if not chunks_path.exists():
            st.info("아직 인덱스가 없습니다. 먼저 인덱싱을 수행해 주세요.")
            return

        # ---- chunks.jsonl 집계(문서별) ----
        docs: Dict[str, Dict[str, Any]] = {}
        total_lines: int = 0
        parse_errors: int = 0

        try:
            with chunks_path.open("r", encoding="utf-8") as rf:
                for line in rf:
                    s = line.strip()
                    if not s:
                        continue
                    total_lines += 1
                    try:
                        obj = json.loads(s)
                    except Exception:
                        parse_errors += 1
                        continue
                    doc_id = str(obj.get("doc_id") or obj.get("source") or "")
                    title = str(obj.get("title") or "")
                    source = str(obj.get("source") or "")
                    if not doc_id:
                        continue
                    row = docs.setdefault(doc_id, {"doc_id": doc_id, "title": title, "source": source, "chunks": 0})
                    row["chunks"] += 1
        except Exception as e:
            _errlog(f"read chunks.jsonl failed: {e}", where="[admin-indexed-sources.read]", exc=e)
            st.error("인덱스 파일을 읽는 중 오류가 발생했어요.")
            return

        table: List[Dict[str, Any]] = list(docs.values())
        st.caption(f"총 청크 수: **{total_lines}** · 문서 수: **{len(table)}** (파싱오류 {parse_errors}건)")
        st.dataframe(
            [{"title": r["title"], "path": r["source"], "doc_id": r["doc_id"], "chunks": r["chunks"]} for r in table],
            hide_index=True,
            use_container_width=True,
        )
# ========================= [16] Indexed Sources Panel — END ==========================



# [17] main ===================================================================
def main():
    if st is None:
        print("Streamlit 환경이 아닙니다.")
        return
    _render_body()


if __name__ == "__main__":
    main()
