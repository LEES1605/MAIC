# [01] future import ==========================================================
from __future__ import annotations

# [02] imports & bootstrap ====================================================
import importlib
import importlib.util
import json
import os
import sys
import time
import traceback
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

# ===== [PATCH 01 / app.py / [04] 경로/상태 & 에러로그 / L071–L179] — START =====
# [04] 경로/상태 & 에러로그 =====================================================
def _persist_dir() -> Path:
    # 1) 인덱서 정의 경로
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


def _mark_ready() -> None:
    """준비 신호 파일(.ready) 생성."""
    try:
        (PERSIST_DIR / ".ready").write_text("ok", encoding="utf-8")
    except Exception:
        pass


def _is_brain_ready() -> bool:
    """인덱스 준비 여부(로컬 신호 기반) — 엄격 판정(SSOT).
    규칙: .ready 파일과 chunks.jsonl 파일이 모두 존재해야 준비(True).
    이렇게 해야 진단 패널(local_ok)과 진행선/배지 판단이 일치합니다.
    """
    # 세션에 공유된 경로가 있으면 우선 사용, 없으면 즉시 계산
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
        ready = (p / ".ready").exists()
        chunks = (p / "chunks.jsonl")
        chunks_ok = chunks.exists() and chunks.stat().st_size > 0
        return bool(ready and chunks_ok)
    except Exception:
        # 어떤 예외든 안전하게 미준비로 처리
        return False


def _get_brain_status() -> dict:
    """
    반환 예: {"code": "READY"|"SCANNING"|"RESTORE"|"MISSING", "source": "local|drive|github|"}
    UI 헤더 배지/진행선/진단 패널이 공통으로 참조하는 최상위 상태(SSOT)를 제공합니다.
    """
    try:
        if _is_brain_ready():
            return {"code": "READY", "source": "local"}
        # 필요시 추가 상태 결합(예: SCANNING/RESTORE)은 여기서 계산
        return {"code": "MISSING", "source": ""}
    except Exception:
        return {"code": "MISSING", "source": ""}


def _share_persist_dir_into_session(p: Path) -> None:
    """세션으로 persist 경로 주입."""
    try:
        if st is not None:
            st.session_state["_PERSIST_DIR"] = p
    except Exception:
        pass


_share_persist_dir_into_session(PERSIST_DIR)


def _errlog(msg: str, where: str = "", exc: Exception | None = None) -> None:
    """표준 에러 로깅(콘솔 + Streamlit 가능 시 캡션)."""
    try:
        prefix = f"{where} " if where else ""
        print(f"[ERR] {prefix}{msg}")
        if exc:
            traceback.print_exception(exc)
        if st is not None:
            with st.expander("자세한 오류 로그", expanded=False):
                st.code(f"{prefix}{msg}\n{traceback.format_exc() if exc else ''}")
    except Exception:
        pass
# ===== [PATCH 01 / app.py / [04] 경로/상태 & 에러로그 / L071–L179] — END =====


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


# [07] 헤더(배지·타이틀·⚙️ 한 줄, 타이틀 바로 뒤에 아이콘) ==========================
def _header():
    """
    - [배지] [LEES AI Teacher] [⚙️/로그아웃칩]을 '한 줄'에 배치.
    - ⚙️ 클릭 시 '바로 아래'에 로그인 폼이 펼쳐짐(새로고침/쿼리파람 없음).
    - 로그인 후엔 톱니 대신 '🚪 로그아웃' 칩이 즉시 표시.
    - 진행선은 항상 표시(완료도 보이도록) — [06]에서 처리.
    """
    if st is None:
        return

    ss = st.session_state
    ss.setdefault("_show_admin_login", False)

    # 상태 배지 텍스트/색상
    status = _get_brain_status()
    code = status["code"]
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
      #brand-inline{ display:flex; align-items:center; gap:.5rem; flex-wrap:nowrap; }
      .status-btn{ display:inline-block; border-radius:10px; padding:4px 10px; font-weight:700; font-size:13px;
                   border:1px solid transparent; white-space:nowrap; }
      .status-btn.green  { background:#E4FFF3; color:#0f6d53; border-color:#bff0df; }
      .status-btn.yellow { background:#FFF8E1; color:#8a6d00; border-color:#ffe099; }
      .status-btn.red    { background:#FFE8E6; color:#a1302a; border-color:#ffc7c2; }

      .brand-title{ font-size:clamp(42px, 6vw, 68px); font-weight:800; letter-spacing:.2px; line-height:1; color:#0B1B45;
                    text-shadow:0 1px 0 #fff, 0 2px 0 #e9eef9, 0 3px 0 #d2dbf2, 0 8px 14px rgba(0,0,0,.22); }

      /* ⚙️/로그아웃 칩 */
      .gear-btn, .logout-chip{
        display:inline-flex; align-items:center; justify-content:center;
        height:28px; min-width:28px; padding:0 10px; border-radius:14px; border:1px solid #e5e7eb;
        background:#f3f4f6; color:#111827; font-weight:700; cursor:pointer;
      }
      .gear-btn{ width:28px; padding:0; }
      .gear-btn:hover, .logout-chip:hover{ filter:brightness(.96); }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # 한 줄 렌더
    c1, c2, c3 = st.columns([0.0001, 0.0001, 0.0001], gap="small")
    with st.container():
        st.markdown('<div id="brand-inline">', unsafe_allow_html=True)
        with c1:
            st.markdown(f'<span class="status-btn {badge_class}">{badge_txt}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown('<span class="brand-title">LEES AI Teacher</span>', unsafe_allow_html=True)
        with c3:
            if ss.get("admin_mode"):
                if st.button("🚪 로그아웃", key="logout_now", help="관리자 로그아웃", use_container_width=False):
                    ss["admin_mode"] = False
                    ss["_show_admin_login"] = False
                    st.success("로그아웃")
                    st.rerun()
                st.markdown('<span class="logout-chip" style="display:none"></span>', unsafe_allow_html=True)
            else:
                if st.button("⚙️", key="open_admin_login", help="관리자 로그인", use_container_width=False):
                    ss["_show_admin_login"] = not ss.get("_show_admin_login", False)
        st.markdown("</div>", unsafe_allow_html=True)

    # 로그인 폼(제자리 토글)
    if not ss.get("admin_mode") and ss.get("_show_admin_login"):
        with st.container(border=True):
            pwd_set = (
                _from_secrets("ADMIN_PASSWORD", "")
                or _from_secrets("APP_ADMIN_PASSWORD", "")
                or ""
            )
            pw = st.text_input("관리자 비밀번호", type="password")
            cols = st.columns([1, 1, 4])
            with cols[0]:
                if st.button("로그인"):
                    if pw and pwd_set and pw == str(pwd_set):
                        ss["admin_mode"] = True
                        ss["_show_admin_login"] = False
                        st.success("로그인 성공")
                        st.rerun()
                    else:
                        st.error("비밀번호가 올바르지 않습니다.")
            with cols[1]:
                if st.button("닫기"):
                    ss["_show_admin_login"] = False
                    st.rerun()

    # 진행선(완료여도 항상 표시)
    _render_boot_progress_line()


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


# ===== [PATCH 02 / app.py / [09] 부팅 훅(오케스트레이터 오토플로우 호출) / L397–L643] — START =====
# [09] 부팅 훅(오케스트레이터 오토플로우 호출) ================================
def _set_brain_status(code: str, msg: str = "", source: str = "", attached: bool = False) -> None:
    """상태 배지/진행선 표시에 사용할 공통 상태(SSOT) 저장."""
    try:
        if st is None:
            return
        st.session_state.setdefault("brain_status", {})
        st.session_state["brain_status"].update(
            {"code": code, "message": msg, "source": source, "attached": attached}
        )
    except Exception:
        pass


def _quick_local_attach_only():
    """빠른 부팅: 네트워크 호출 없이 로컬 신호만 확인.
    규칙: .ready + chunks.jsonl(>0B) 동시 존재 시에만 READY로 승격.
    """
    if st is None:
        return False

    man = PERSIST_DIR / "manifest.json"  # 참고용(SSOT엔 불참여)
    chunks = PERSIST_DIR / "chunks.jsonl"
    ready = PERSIST_DIR / ".ready"

    try:
        chunks_ok = chunks.exists() and chunks.stat().st_size > 0
        if ready.exists() and chunks_ok:
            _set_brain_status("READY", "로컬 인덱스 연결됨(ready+chunks)", "local", attached=True)
            return True
    except Exception:
        pass

    _set_brain_status("MISSING", "인덱스 없음(관리자에서 '업데이트 점검' 필요)", "", attached=False)
    return False


def _render_boot_progress_line() -> None:
    """헤더 아래 진행선 UI 렌더(READY이면 가장 오른쪽 단계)."""
    try:
        if st is None:
            return
        bs = st.session_state.get("brain_status") or _get_brain_status()
        code = (bs.get("code") if isinstance(bs, dict) else None) or "MISSING"

        stages = ["LOCAL_CHECK", "RESTORE", "ATTACH", "READY"]
        active_idx = stages.index("READY") if code == "READY" else stages.index("ATTACH") if code == "ATTACH" else stages.index("LOCAL_CHECK")
        st.write(
            f":small_blue_diamond: 부팅 단계: "
            f"{' → '.join([f'**{s}**' if i <= active_idx else s for i, s in enumerate(stages)])}"
        )
    except Exception:
        pass


def _boot_orchestrator_auto() -> None:
    """앱 부팅 시 자동으로 수행되는 오케스트레이션."""
    try:
        # 1) 네트워크 호출 없이 로컬로만 빠르게 척도 확인
        if _quick_local_attach_only():
            return

        # 2) (선택) 로컬 미준비 → 관리 절차 유도(복구/인덱싱)
        _set_brain_status("MISSING", "로컬 인덱스 미준비", "", attached=False)
    except Exception as exc:
        _errlog("부팅 훅 실행 실패", where="[09]", exc=exc)
# ===== [PATCH 02 / app.py / [09] 부팅 훅(오케스트레이터 오토플로우 호출) / L397–L643] — END =====

# ======================= [10] 부팅/인덱스 준비 — START ========================
def _set_brain_status(code: str, msg: str, source: str = "", attached: bool = False):
    """세션 상태를 일관된 방식으로 세팅한다."""
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


def _quick_local_attach_only():
    """빠른 부팅: 네트워크 호출 없이 로컬 신호만 확인."""
    if st is None:
        return False
    
    man = PERSIST_DIR / "manifest.json"
    chunks = PERSIST_DIR / "chunks.jsonl"
    ready = PERSIST_DIR / ".ready"

    if (chunks.exists() and chunks.stat().st_size > 0) or (man.exists() and man.stat().st_size > 0) or ready.exists():
        _set_brain_status("READY", "로컬 인덱스 연결됨(빠른 부팅)", "local", attached=True)
        return True

    _set_brain_status("MISSING", "인덱스 없음(관리자에서 '업데이트 점검' 필요)", "", attached=False)
    return False


def _run_deep_check_and_attach():
    """관리자 버튼 클릭 시 실행되는 네트워크 검사+복구."""
    if st is None:
        return
    ss = st.session_state
    idx = _try_import("src.rag.index_build", ["quick_precheck", "diff_with_manifest"])
    rel = _try_import("src.backup.github_release", ["restore_latest"])
    quick = idx.get("quick_precheck")
    diff = idx.get("diff_with_manifest")
    restore_latest = rel.get("restore_latest")

    # 0) 로컬 먼저
    if _is_brain_ready():
        stats = {}
        changed = False
        if callable(diff):
            try:
                d = diff() or {}
                stats = d.get("stats") or {}
                total = int(stats.get("added", 0)) + int(stats.get("changed", 0)) + int(stats.get("removed", 0))
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
        try:
            _ = quick() or {}
        except Exception as e:
            _errlog(f"precheck 예외: {e}", where="[deep_check]")

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
                total = int(stats.get("added", 0)) + int(stats.get("changed", 0)) + int(stats.get("removed", 0))
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
    if mode in ("restore", "on"):
        rel = _try_import("src.backup.github_release", ["restore_latest"])
        fn = rel.get("restore_latest")
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
    if st is None:
        return
    import time as _time
    import traceback as _tb

    st.subheader("관리자 패널")

    # --- (A) 토글 UI: st.toggle 미지원 환경 대비 체크박스 폴백 ---
    toggle_key = "admin_orchestrator_open"
    if toggle_key not in st.session_state:
        st.session_state[toggle_key] = False

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
                return importlib.import_module(module_name), f"import:{module_name}"
            except Exception as e:
                tried_msgs.append(f"import:{module_name} → {e!r}")

        # 2) 파일 경로 폴백: 프로젝트 루트/앱 디렉터리 후보를 돌며 직접 로드
        roots = [Path("."), Path(__file__).resolve().parent]
        rels = [Path("src") / "ui_orchestrator.py", Path("ui_orchestrator.py")]
        for root in roots:
            for rel in rels:
                candidate = root / rel
                if candidate.exists():
                    try:
                        spec = importlib.util.spec_from_file_location("ui_orchestrator", candidate)
                        if spec is None or spec.loader is None:
                            raise ImportError(f"invalid spec/loader for {candidate}")
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules["ui_orchestrator"] = mod
                        spec.loader.exec_module(mod)
                        return mod, f"file:{candidate.as_posix()}"
                    except Exception as e:
                        tried_msgs.append(f"file:{candidate} → {e!r}")

        raise ImportError("ui_orchestrator not found", tried_msgs)

    load_start = _time.perf_counter()
    with st.spinner("진단 도구 모듈을 불러오는 중…"):
        try:
            mod, how = _import_orchestrator_with_fallback()
        except Exception as e:
            st.error("진단 도구 모듈을 불러오지 못했습니다.")
            with st.expander("오류 자세히 보기"):
                st.code("".join(_tb.format_exception(type(e), e, e.__traceback__)))
            return

    st.caption(f"· 모듈 로드 경로: `{how}`")

    # 3) 렌더링 (구현 유무 체크)
    render_fn = getattr(mod, "render_index_orchestrator_panel", None)
    if not callable(render_fn):
        st.error("ui_orchestrator.render_index_orchestrator_panel()를 찾을 수 없습니다.")
        try:
            names = sorted([n for n in dir(mod) if not n.startswith("_")])
            st.code("\n".join(names))
        except Exception:
            pass
        return

    try:
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

    prev_role = None
    for m in ss["chat"]:
        role = m.get("role", "assistant")
        if prev_role is not None and prev_role != role:
            st.markdown('<div class="turn-sep"></div>', unsafe_allow_html=True)
        _render_bubble(role, m.get("text", ""))
        prev_role = role

    # 스트리밍 자리
    ph = st.empty()

    # 메시지 영역 CLOSE(폼은 같은 ChatPane 내부)
    st.markdown("</div>", unsafe_allow_html=True)

    # 인-카드 입력폼 — Enter=전송, 화살표 버튼은 인풋 내부(절대배치, JS 없이)
    with st.form("inpane_chat_form", clear_on_submit=True):
        qtxt = st.text_input(
            "질문 입력",
            value="",
            placeholder="예) 분사구문이 뭐예요?  예) 이 문장 구조 분석해줘",
            label_visibility="collapsed",
            key="inpane_q",
        )
        send = st.form_submit_button("➤", type="secondary")

    # ChatPane CLOSE
    st.markdown("</div>", unsafe_allow_html=True)

    # 제출 처리(빈값/중복 가드)
    if send and not ss.get("_sending", False):
        question = (qtxt or "").strip()
        if not question:
            st.warning("질문을 입력해 주세요.")
            return

        ss["_sending"] = True
        ss["chat"].append({"id": f"u{int(time.time() * 1000)}", "role": "user", "text": question})

        # 증거/모드
        ev_notes = ss.get("__evidence_class_notes", "")
        ev_books = ss.get("__evidence_grammar_books", "")

        # 프롬프트 해석 (분리 모듈 우선)
        try:
            from src.prompting.resolve import resolve_prompts

            system_prompt, user_prompt, source = resolve_prompts(
                MODE_TOKEN, question, ev_notes, ev_books, cur_label, ss
            )
            ss["__prompt_source"] = source
        except Exception:
            # 안전 폴백: '맥락 요청 금지, 간단 답변부터' 원칙 유지
            ss["__prompt_source"] = "Fallback(Local)"
            if MODE_TOKEN == "문법설명":
                system_prompt = "모든 출력은 한국어. 장황한 배경설명 금지. 맥락요구 금지. 부족하면 추가질문 1~2개 제시."
                user_prompt = f"[질문]\n{question}\n- 한 줄 핵심 → 규칙 3~5개 → 예문 1개 → 필요한 추가질문"
            elif MODE_TOKEN == "문장구조분석":
                system_prompt = "모든 출력은 한국어. 불확실성은 %로. 맥락요구 금지."
                user_prompt = f"[문장]\n{question}\n- S/V/O/C/M 개요 → 성분 식별 → 단계적 설명 → 핵심 포인트"
            else:
                system_prompt = "모든 출력은 한국어. 맥락요구 금지."
                user_prompt = f"[지문]\n{question}\n- 한 줄 요지 → 구조 요약 → 핵심어 3–6개 + 이유"

        # LLM 호출(스트리밍 대응)
        try:
            from src.llm import providers as _prov

            call = getattr(_prov, "call_with_fallback", None)
        except Exception:
            call = None

        acc = ""

        def _emit(piece: str):
            nonlocal acc
            import html
            import re

            acc += str(piece)

            def esc(t: str) -> str:
                t = html.escape(t or "").replace("\n", "<br/>")
                return re.sub(r"  ", "&nbsp;&nbsp;", t)

            ph.markdown(
                '<div style="display:flex;justify-content:flex-start;margin:8px 0;">'
                '  <div style="max-width:88%;padding:10px 12px;border-radius:16px;border-top-left-radius:8px;'
                '              line-height:1.6;font-size:15px;box-shadow:0 1px 1px rgba(0,0,0,.05);white-space:pre-wrap;'
                '              position:relative;border:1px solid #BEE3FF;background:#EAF6FF;color:#0a2540;">'
                '    <span style="display:inline-block;margin:-2px 0 6px 0;padding:1px 8px;border-radius:999px;'
                '                 font-size:11px;font-weight:700;background:#DFF1FF;color:#0f5b86;'
                '                 border:1px solid #BEE3FF;">답변</span><br/>'
                + esc(acc)
                + "  </div>"
                "</div>",
                unsafe_allow_html=True,
            )

        text_final = ""
        try:
            import inspect

            if callable(call):
                sig = inspect.signature(call)
                params = sig.parameters.keys()
                kwargs: Dict[str, Any] = {}

                if "messages" in params:
                    kwargs["messages"] = [
                        {"role": "system", "content": system_prompt or ""},
                        {"role": "user", "content": user_prompt},
                    ]
                else:
                    if "prompt" in params:
                        kwargs["prompt"] = user_prompt
                    elif "user_prompt" in params:
                        kwargs["user_prompt"] = user_prompt
                    if "system_prompt" in params:
                        kwargs["system_prompt"] = system_prompt or ""
                    elif "system" in params:
                        kwargs["system"] = system_prompt or ""
                if "mode_token" in params:
                    kwargs["mode_token"] = MODE_TOKEN
                elif "mode" in params:
                    kwargs["mode"] = MODE_TOKEN
                if "temperature" in params:
                    kwargs["temperature"] = 0.2
                elif "temp" in params:
                    kwargs["temp"] = 0.2
                if "timeout_s" in params:
                    kwargs["timeout_s"] = 90
                elif "timeout" in params:
                    kwargs["timeout"] = 90
                if "extra" in params:
                    kwargs["extra"] = {"question": question, "mode_key": cur_label}

                supports_stream = (
                    ("stream" in params)
                    or ("on_token" in params)
                    or ("on_delta" in params)
                    or ("yield_text" in params)
                )
                if supports_stream:
                    if "stream" in params:
                        kwargs["stream"] = True
                    if "on_token" in params:
                        kwargs["on_token"] = _emit
                    if "on_delta" in params:
                        kwargs["on_delta"] = _emit
                    if "yield_text" in params:
                        kwargs["yield_text"] = _emit
                    res = call(**kwargs)
                    text_final = (res.get("text") if isinstance(res, dict) else acc) or acc
                else:
                    res = call(**kwargs)
                    text_final = res.get("text") if isinstance(res, dict) else str(res)
                    if not text_final:
                        text_final = "(응답이 비어있어요)"
                    _emit(text_final)
            else:
                text_final = "(오류) LLM 어댑터를 사용할 수 없습니다."
                _emit(text_final)
        except Exception as e:
            text_final = f"(오류) {type(e).__name__}: {e}"
            _emit(text_final)

        ss["chat"].append({"id": f"a{int(time.time() * 1000)}", "role": "assistant", "text": text_final})
        ss["_sending"] = False
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
        _quick_local_attach_only()
    except Exception as e:
        _errlog(f"quick attach failed: {e}", where="[render_body]", exc=e)

    # 5) 관리자 패널 + 업데이트 점검
    if _is_admin_view():
        _render_admin_panels()
        with st.container():
            if st.button(
                "🧭 업데이트 점검",
                help="클라우드와 로컬을 비교해 변경 사항을 확인합니다. 필요 시 재인덱싱을 권장합니다.",
                use_container_width=True,
            ):
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
